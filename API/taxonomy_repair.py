"""Repair malformed LLM taxonomy output before validation (issue #13).

Two passes, both pure (text/object in, object + repair list out), so they
are unit-testable without network access — same split as taxonomy_core.py:

1. parse_model_json: text -> object. Plain `json.loads` first; only if that
   fails, strip a ```json fence and anything outside the outermost `{...}`,
   then parse with `json5`. json5 is chosen over `json_repair` on purpose:
   it accepts exactly the defects the issue lists (trailing commas, unquoted
   keys, single quotes, comments) and nothing more — a truncated answer
   (observed: openrouter-dots, "Unterminated string") still fails, whereas
   json_repair would close the dangling string/objects and hand back an
   envelope with made-up ends. Unreadable text raises InvalidModelJSON.

2. repair_to_schema: object -> object closer to docs/taxonomy-schema.json.
   Walks the value alongside the JSON Schema (following $ref) and only
   rewrites a value that does NOT already match its schema type, and only
   when the fix is unambiguous:
     - "null" -> null on a nullable field; "" -> null on a nullable field
       that doesn't accept strings;
     - a string -> [string] where an array of strings is expected;
     - "82" / 82.0 -> 82 where an integer is expected;
     - "true"/"false" -> bool where a boolean is expected.
   Missing required fields, unknown properties, out-of-enum/out-of-range
   values, null on a non-nullable field... are left untouched, so validation
   still rejects them: fixing those would mean guessing.

Every rewrite is reported as a Repair (JSON path, before, after) so the
benchmark can tell a model that was right first time from one that was
rescued.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import json5

INVALID_JSON_EXCERPT_CHARS = 300

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)
_INT_RE = re.compile(r"^\s*-?\d+\s*$")


@dataclass
class Repair:
    path: str
    kind: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InvalidModelJSON(ValueError):
    """The model's text is not JSON even after syntax repair. A ValueError so
    the batch loops that already catch rejected envelopes keep going."""

    def __init__(self, message: str, excerpt: str):
        super().__init__(message)
        self.excerpt = excerpt


def parse_model_json(text: str) -> tuple[Any, list[Repair]]:
    try:
        return json.loads(text), []
    except json.JSONDecodeError:
        pass

    repairs: list[Repair] = []
    candidate = text
    fence = _FENCE_RE.match(candidate)
    if fence:
        candidate = fence.group(1)
        repairs.append(Repair("<root>", "strip_markdown_fence", None, None))
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start and (candidate[:start].strip() or candidate[end + 1:].strip()):
        repairs.append(Repair(
            "<root>", "strip_surrounding_text",
            {"before": candidate[:start].strip()[:80], "after": candidate[end + 1:].strip()[:80]}, None,
        ))
        candidate = candidate[start:end + 1]

    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            value = json5.loads(candidate)
        except ValueError as exc:
            raise InvalidModelJSON(
                f"model output is not valid JSON, even after repair: {exc}",
                excerpt=text[:INVALID_JSON_EXCERPT_CHARS],
            ) from exc
        repairs.append(Repair("<root>", "json5_syntax", None, None))
    return value, repairs


def _types(schema: dict) -> set[str]:
    t = schema.get("type")
    if t is None:
        return set()
    return {t} if isinstance(t, str) else set(t)


def _matches_type(value: Any, types: set[str]) -> bool:
    checks = {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }
    return any(checks.get(t, False) for t in types)


def _resolve(schema: dict, root: dict) -> dict:
    while "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return schema
        node: Any = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
    return schema


def _coerce_scalar(value: Any, types: set[str], schema: dict, root: dict) -> tuple[bool, Any, str]:
    """(changed, new_value, kind) for a value that doesn't match `types`."""
    if "null" in types and isinstance(value, str) and value.strip().lower() == "null":
        return True, None, "string_null_to_null"
    if "null" in types and value == "" and "string" not in types:
        return True, None, "empty_string_to_null"
    if "integer" in types:
        if isinstance(value, str) and _INT_RE.match(value):
            return True, int(value), "string_to_integer"
        if isinstance(value, float) and value.is_integer():
            return True, int(value), "float_to_integer"
    if "boolean" in types and isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return True, value.strip().lower() == "true", "string_to_boolean"
    if "array" in types and isinstance(value, str) and value:
        items = _resolve(schema.get("items", {}), root)
        if "string" in _types(items):
            return True, [value], "string_to_array"
    return False, value, ""


def _walk(value: Any, schema: dict, root: dict, path: list[str], repairs: list[Repair]) -> Any:
    schema = _resolve(schema, root)
    types = _types(schema)

    # A "null" string on a nullable field means null even though it is a
    # valid string — no chapter/character field legitimately says "null".
    if types and (not _matches_type(value, types)
                  or ("null" in types and isinstance(value, str) and value.strip().lower() == "null")):
        changed, new_value, kind = _coerce_scalar(value, types, schema, root)
        if changed:
            repairs.append(Repair("/".join(path) or "<root>", kind, value, new_value))
            value = new_value

    if isinstance(value, dict):
        props = schema.get("properties", {})
        return {k: _walk(v, props[k], root, path + [k], repairs) if k in props else v for k, v in value.items()}
    if isinstance(value, list) and "items" in schema:
        return [_walk(v, schema["items"], root, path + [str(i)], repairs) for i, v in enumerate(value)]
    return value


def repair_to_schema(value: Any, schema: dict) -> tuple[Any, list[Repair]]:
    repairs: list[Repair] = []
    return _walk(value, schema, schema, [], repairs), repairs

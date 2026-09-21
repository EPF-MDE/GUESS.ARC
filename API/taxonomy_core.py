"""Pure logic for the taxonomy tagging client (issue #5). No filesystem or
network access, so it can be unit tested directly against synthetic fixtures —
mirrors the test/sanity_checks.py split for the bronze/silver checks.
"""
from __future__ import annotations

import re
from typing import Any

import jsonschema

# Only the "## 1. Chapter taxonomy file" section of docs/taxonomy-schema.md is
# injected into the system prompt: sections 2-3 describe the Fights Index and
# Character Registry, which this ticket's per-chapter call neither produces
# nor needs (issue #5 explicitly puts both out of scope).
TAXONOMY_SECTION_RE = re.compile(r"^## 1\..*?(?=^## 2\.|\Z)", re.DOTALL | re.MULTILINE)

SYSTEM_PROMPT_PREAMBLE = (
    "You are a tagging engine for One Piece chapters. You will be given one "
    "entire chapter (its front-matter and every section) as plain text. "
    "Produce exactly one JSON object conforming to the schema you are given, "
    "filling in every field it requires. Never invent a fact that is not "
    "supported by the chapter text. Each `confidence` field is a 0-100 "
    "self-assessed certainty for that specific claim only, never for the "
    "chapter as a whole."
)


def extract_taxonomy_definition(schema_doc_text: str) -> str:
    """Pull the '## 1. Chapter taxonomy file' section out of taxonomy-schema.md's text."""
    match = TAXONOMY_SECTION_RE.search(schema_doc_text)
    if not match:
        raise ValueError("could not find a '## 1.' section in the taxonomy schema doc")
    return match.group(0).strip()


def build_system_prompt(taxonomy_definition: str) -> str:
    """Compose the system prompt, injecting the taxonomy definition under its own
    heading. A future taxonomy revision (new schema_version) flows through this
    injection point — never through a change to this function."""
    return (
        f"{SYSTEM_PROMPT_PREAMBLE}\n\n"
        "## DÉFINITION TAXONOMIE\n\n"
        f"{taxonomy_definition}\n"
    )


def validate_taxonomy_envelope(data: Any, schema: dict) -> list[str]:
    """Return human-readable errors for one taxonomy envelope against the v1 schema."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in error.path) or "<root>"
        errors.append(f"{path}: {error.message}")
    return errors


def taxonomy_output_filename(envelope: dict) -> str:
    """Filename for one validated envelope, keyed by chapter.number from the
    response — never by the position/order the chapter was sent in (issue #5),
    so a future batched provider can reuse this without rework."""
    try:
        number = envelope["chapter"]["number"]
    except (KeyError, TypeError) as exc:
        raise ValueError("envelope has no chapter.number to reassociate by") from exc
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise ValueError(f"chapter.number must be a positive integer, got {number!r}")
    return f"chapter_{number:04d}.json"

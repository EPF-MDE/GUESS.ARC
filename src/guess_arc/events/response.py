"""Lecture d'une réponse brute du modèle : bloc de réflexion retiré, JSON parsé et validé.

Gemma 4 peut faire précéder le JSON d'un bloc de réflexion vide, même mode
« thinking » désactivé ; il est retiré. Un bloc qui n'est pas vide rend la
réponse invalide : le modèle a réfléchi alors qu'il ne le devait pas.

La validation suit le schéma final du chapitre, avec les seuls mots-clés qu'il
emploie (`type`, `enum`, `required`, `additionalProperties`, `properties`,
`items`), sans dépendre de jsonschema. Le numéro de chapitre doit aussi être
celui qu'on a demandé.
"""

from __future__ import annotations

import json
import re

EMPTY_THINKING_RE = re.compile(
    r"^\s*(?:<think>\s*</think>|<thought>\s*</thought>|<\|channel>thought\s*<channel\|>)")

JSON_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int,
}


class InvalidResponse(ValueError):
    pass


def strip_thinking(text: str) -> str:
    return EMPTY_THINKING_RE.sub("", text, count=1)


def _validate(value, schema: dict, where: str) -> None:
    expected = JSON_TYPES[schema["type"]]
    # En Python, un booléen est aussi un entier.
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        raise InvalidResponse(f"{where} : {schema['type']} attendu")
    if "enum" in schema and value not in schema["enum"]:
        raise InvalidResponse(f"{where} : {value!r} hors de l'enum")
    if expected is dict:
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise InvalidResponse(f"{where} : champ {key!r} manquant")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{where}.{key}")
            elif schema.get("additionalProperties") is False:
                raise InvalidResponse(f"{where} : champ {key!r} non prévu")
    if expected is list and "items" in schema:
        for i, item in enumerate(value):
            _validate(item, schema["items"], f"{where}[{i}]")


def parse_response(text: str, schema: dict, chapter: int) -> dict:
    try:
        document = json.loads(strip_thinking(text))
    except json.JSONDecodeError as e:
        raise InvalidResponse(f"JSON invalide : {e}") from None
    _validate(document, schema, "$")
    if document["chapter"] != chapter:
        raise InvalidResponse(f"chapitre {document['chapter']} au lieu de {chapter}")
    return document

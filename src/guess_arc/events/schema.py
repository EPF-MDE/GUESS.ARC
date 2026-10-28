"""Schéma JSON de la réponse du modèle, commun à tous les chapitres.

Le schéma de base est versionné (`SCHEMA_VERSION`) ; le schéma final d'un
chapitre n'en diffère que par l'enum des noms des participants, où sont
injectés les noms autorisés du chapitre.

Mots-clés limités à `type`, `enum`, `required` et `additionalProperties` (plus
`properties` et `items` pour la structure) : ni `null`, ni `pattern`, ni
`minItems`, que la génération contrainte du serveur ne suit pas toujours. Les
limites de longueur (preuve ≤ 20 mots, description ≤ 25 mots) sont donc dans le
prompt système.

Les champs d'un événement sont dans l'ordre où le modèle les écrit : la preuve
d'abord, puis la section source, et seulement ensuite le type, afin qu'il
classe à partir du texte et non de sa mémoire de One Piece.
"""

from __future__ import annotations

import copy

from .taxonomy import LLM_EVENT_TYPES

SOURCES = ["long_summary", "short_summary", "chapter_notes"]
ROLES = ["agent", "target", "other"]
STATUSES = ["single", "start", "ongoing", "end"]


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def base_schema() -> dict:
    """Schéma de base : l'enum des noms des participants est vide."""
    participant = _object({
        "name": {"type": "string", "enum": []},
        "role": {"type": "string", "enum": ROLES},
    })
    event = _object({
        "evidence": {"type": "string"},
        "source": {"type": "string", "enum": SOURCES},
        "type": {"type": "string", "enum": list(LLM_EVENT_TYPES)},
        "description": {"type": "string"},
        "participants": {"type": "array", "items": participant},
        "location": {"type": "string"},
        "status": {"type": "string", "enum": STATUSES},
        "in_flashback": {"type": "boolean"},
    })
    return _object({
        "chapter": {"type": "integer"},
        "events": {"type": "array", "items": event},
        "unlisted_entities": {"type": "array", "items": {"type": "string"}},
    })


def chapter_schema(allowed_names: list[str]) -> dict:
    """Schéma final d'un chapitre : les noms autorisés dans l'enum des participants."""
    schema = copy.deepcopy(base_schema())
    participant = schema["properties"]["events"]["items"]["properties"]["participants"]["items"]
    participant["properties"]["name"]["enum"] = list(allowed_names)
    return schema


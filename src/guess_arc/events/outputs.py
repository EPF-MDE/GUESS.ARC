"""Écriture de data/event/out/events_NNNN.json : les événements d'un chapitre.

    {"meta": {...}, "events": [{"id": …, "origin": …, "type": …, …}, …]}

Pour l'instant, seuls les événements d'origine `wiki` y figurent ; la fusion
avec l'origine `llm` complétera le même fichier.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .silver import SilverChapter
from .versions import ENTITIES_VERSION, TAXONOMY_VERSION
from .wiki import WikiEvent


def event_id(chapter: int, origin: str, type_: str, participants: list[str]) -> str:
    """Stable d'une exécution à l'autre : un événement par (type, participants) et par chapitre."""
    key = json.dumps(sorted(participants), ensure_ascii=False)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"{chapter:04d}-{origin}-{type_}-{digest}"


def wiki_record(chapter: int, e: WikiEvent) -> dict:
    return {
        "id": event_id(chapter, "wiki", e.type, [e.name]),
        "origin": "wiki",
        "type": e.type,
        "description": e.description,
        "participants": [{"name": e.name, "role": e.role}],
        "location": "",
        "status": "single",
        "in_flashback": e.in_flashback,
        "evidence": "",
        "source": "characters",
    }


def render_output(ch: SilverChapter, wiki: list[WikiEvent]) -> str:
    document = {
        "meta": {
            "chapter": ch.number,
            "revision_id": ch.revision_id,
            "taxonomy_version": TAXONOMY_VERSION,
            "entities_version": ENTITIES_VERSION,
            # Origines déjà passées sur ce fichier : tant que `llm` manque, le
            # chapitre reste à extraire par le modèle.
            "origins": ["wiki"],
        },
        "events": [wiki_record(ch.number, e) for e in wiki],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write_output(ch: SilverChapter, wiki: list[WikiEvent], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"events_{ch.number:04d}.json"
    path.write_text(render_output(ch, wiki), encoding="utf-8")
    return path

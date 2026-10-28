"""Écriture de data/event/in/events_NNNN.md : le prompt utilisateur exact.

Le front-matter dit d'où vient le prompt (`revision_id` de la silver,
versions), ce que le préparsing a retiré (`flags`) et quels noms le modèle peut
donner aux participants (`allowed_names`, injectés dans le schéma) ; le corps
est envoyé tel quel au modèle.
"""

from __future__ import annotations

import json
from pathlib import Path

from .entities import EntityBlock
from .preparse import Preparsed
from . import versions


def render_user_prompt(p: Preparsed, entities: EntityBlock) -> str:
    notes = [f"- {n}" for n in p.notes] or ["- none"]
    return "\n".join([
        f'CHAPTER {p.number} — "{p.title}" — Arc: {p.arc}',
        "",
        *entities.render(),
        "",
        "=== SHORT SUMMARY ===",
        p.short_summary,
        "",
        "=== LONG SUMMARY ===",
        p.long_summary,
        "",
        "=== CHAPTER NOTES ===",
        *notes,
    ]) + "\n"


def estimated_tokens(text: str) -> int:
    """Estimation sans tokenizer : environ 4 caractères par token en anglais."""
    return len(text) // 4


def render_input(p: Preparsed, entities: EntityBlock) -> str:
    names = entities.allowed_names
    lines = [
        "---",
        f"chapter: {p.number}",
        f"revision_id: {p.revision_id if p.revision_id is not None else ''}".rstrip(),
        f'entities_version: "{versions.ENTITIES_VERSION}"',
        f'prompt_version: "{versions.PROMPT_VERSION}"',
        f'schema_version: "{versions.SCHEMA_VERSION}"',
        "flags:",
        *(f"  {name}: {count}" for name, count in p.flags.items()),
        "allowed_names:" + ("" if names else " []"),
        *(f"  - {json.dumps(name, ensure_ascii=False)}" for name in names),
        "---",
    ]
    return "\n".join(lines) + "\n" + render_user_prompt(p, entities)


def write_input(p: Preparsed, entities: EntityBlock, in_dir: Path) -> Path:
    in_dir.mkdir(parents=True, exist_ok=True)
    path = in_dir / f"events_{p.number:04d}.md"
    path.write_text(render_input(p, entities), encoding="utf-8")
    return path

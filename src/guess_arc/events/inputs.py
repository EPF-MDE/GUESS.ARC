"""Écriture de data/event/in/events_NNNN.md : le prompt utilisateur exact.

Le front-matter dit d'où vient le prompt (`revision_id` de la silver,
versions) et ce que le préparsing a retiré (`flags`) ; le corps est envoyé
tel quel au modèle.
"""

from __future__ import annotations

from pathlib import Path

from .preparse import Preparsed
from .versions import ENTITIES_VERSION, PROMPT_VERSION


def render_user_prompt(p: Preparsed) -> str:
    notes = [f"- {n}" for n in p.notes] or ["- none"]
    return "\n".join([
        f'CHAPTER {p.number} — "{p.title}" — Arc: {p.arc}',
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


def render_input(p: Preparsed) -> str:
    lines = [
        "---",
        f"chapter: {p.number}",
        f"revision_id: {p.revision_id if p.revision_id is not None else ''}".rstrip(),
        f'entities_version: "{ENTITIES_VERSION}"',
        f'prompt_version: "{PROMPT_VERSION}"',
        "flags:",
        *(f"  {name}: {count}" for name, count in p.flags.items()),
        "---",
    ]
    return "\n".join(lines) + "\n" + render_user_prompt(p)


def write_input(p: Preparsed, in_dir: Path) -> Path:
    in_dir.mkdir(parents=True, exist_ok=True)
    path = in_dir / f"events_{p.number:04d}.md"
    path.write_text(render_input(p), encoding="utf-8")
    return path

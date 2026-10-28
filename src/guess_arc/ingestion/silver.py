"""Écriture de la couche silver : un .md par chapitre, front-matter YAML + résumés."""

from __future__ import annotations

from pathlib import Path

from .parser import Chapter


def yaml_escape(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_markdown(ch: Chapter) -> str:
    lines = [
        "---",
        f"chapter: {ch.number}",
        f"title: {yaml_escape(ch.title or '')}",
        f"jname: {yaml_escape(ch.jname or '')}",
        f"arc: {yaml_escape(ch.arc or '')}",
        f"revision_id: {ch.revision_id}",
        f"revised_at: {yaml_escape(ch.revised_at or '')}",
        f"complete: {str(ch.complete).lower()}",
        f"character_count: {len(ch.characters)}",
        "characters:",
    ]
    for c in ch.characters:
        lines += [
            f"  - name: {yaml_escape(c['name'])}",
            f"    faction: {yaml_escape(c['faction'] or '')}",
            f"    on_panel: {str(c['on_panel']).lower()}",
            f"    appearance: [{', '.join(c['appearance'])}]",
        ]
    lines += [
        "source: https://onepiece.fandom.com/wiki/Chapter_%d" % ch.number,
        "license: CC BY-SA",
        "---",
        "",
        f"# Chapter {ch.number} — {ch.title or ''}".rstrip(" —"),
        "",
        "## Short Summary",
        "",
        ch.short_summary or "_(absent)_",
        "",
        "## Long Summary",
        "",
        ch.long_summary or "_(absent)_",
        "",
        "## Chapter Notes",
        "",
    ]
    lines += [f"- {n}" for n in ch.notes] or ["_(absentes)_"]
    return "\n".join(lines) + "\n"


def write_markdown(ch: Chapter, silver_dir: Path) -> Path:
    silver_dir.mkdir(parents=True, exist_ok=True)
    path = silver_dir / f"chapter_{ch.number:04d}.md"
    path.write_text(render_markdown(ch), encoding="utf-8")
    return path

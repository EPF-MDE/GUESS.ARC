"""Lecture d'un chapitre de la silver (`data/silver/chapter_NNNN.md`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)
# Marqueurs écrits par guess_arc.ingestion.silver quand une section est vide.
ABSENT = {"_(absent)_", "_(absentes)_"}


@dataclass
class SilverChapter:
    number: int
    title: str
    arc: str
    revision_id: int | None
    complete: bool
    short_summary: str
    long_summary: str
    notes: list[str] = field(default_factory=list)


def _yaml_unescape(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = re.sub(r"\\(.)", r"\1", value[1:-1])
    return value


def _field(front_matter: str, name: str) -> str:
    match = re.search(rf"^{name}:[ \t]*(.*)$", front_matter, re.MULTILINE)
    return _yaml_unescape(match.group(1)) if match else ""


def _sections(body: str) -> dict[str, str]:
    heads = list(SECTION_RE.finditer(body))
    out = {}
    for head, nxt in zip(heads, heads[1:] + [None]):
        text = body[head.end():nxt.start() if nxt else len(body)].strip()
        out[head.group(1).strip()] = "" if text in ABSENT else text
    return out


def read_chapter(path: Path) -> SilverChapter:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if match is None:
        raise ValueError(f"{path.name} : front-matter absent")
    front = match.group(1)
    sections = _sections(text[match.end():])
    revision_id = _field(front, "revision_id")
    return SilverChapter(
        number=int(_field(front, "chapter")),
        title=_field(front, "title"),
        arc=_field(front, "arc"),
        revision_id=int(revision_id) if revision_id.isdigit() else None,
        complete=_field(front, "complete") == "true",
        short_summary=sections.get("Short Summary", ""),
        long_summary=sections.get("Long Summary", ""),
        notes=[line[2:] for line in sections.get("Chapter Notes", "").splitlines()
               if line.startswith("- ")],
    )

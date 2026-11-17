"""La couche silver : un .md par chapitre, front-matter YAML + résumés.

`write_markdown` l'écrit, `read_chapter` la relit en SilverChapter : c'est le
lecteur que partagent les étapes suivantes, pour qu'aucune ne dépende du format
des fichiers (`validation` en contrôle seulement le texte brut).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .parser import Chapter

# Ce que le writer met à la place d'un résumé vide, et d'une liste de notes vide.
ABSENT = "_(absent)_"
ABSENT_NOTES = "_(absentes)_"
SECTIONS = ("Short Summary", "Long Summary", "Chapter Notes")
REQUIRED_FIELDS = ("chapter", "arc", "revision_id", "complete")


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
        ch.short_summary or ABSENT,
        "",
        "## Long Summary",
        "",
        ch.long_summary or ABSENT,
        "",
        "## Chapter Notes",
        "",
    ]
    lines += [f"- {n}" for n in ch.notes] or [ABSENT_NOTES]
    return "\n".join(lines) + "\n"


def write_markdown(ch: Chapter, silver_dir: Path) -> Path:
    silver_dir.mkdir(parents=True, exist_ok=True)
    path = silver_dir / f"chapter_{ch.number:04d}.md"
    path.write_text(render_markdown(ch), encoding="utf-8")
    return path


@dataclass(frozen=True)
class SilverChapter:
    """Un chapitre silver relu. Un résumé absent est un texte vide, des notes
    absentes une liste vide, un texte facultatif absent du front-matter est vide."""
    number: int
    arc: str
    revision_id: int
    complete: bool
    title: str = ""
    jname: str = ""
    revised_at: str = ""
    character_count: int | None = None  # tel que déclaré ; None s'il manque
    characters: list[dict] = field(default_factory=list)  # name, faction, on_panel
    short_summary: str = ""
    long_summary: str = ""
    notes: list[str] = field(default_factory=list)


FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FIELD_RE = re.compile(r"^(\w+):[ \t]*(.*?)[ \t]*$")
CHARACTER_RE = re.compile(r"^  - name:[ \t]*(.*?)[ \t]*$")
CHARACTER_FIELD_RE = re.compile(r"^    (\w+):[ \t]*(.*?)[ \t]*$")
HEADING_RE = re.compile(r"^## (.+?)[ \t]*$", re.MULTILINE)
ESCAPE_RE = re.compile(r'\\(["\\])')


def _unquote(value: str) -> str:
    """L'inverse de `yaml_escape` ; une valeur sans guillemets est rendue telle quelle."""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return ESCAPE_RE.sub(r"\1", value[1:-1])
    return value


def _boolean(value: str, name: str, path: Path) -> bool:
    if value not in ("true", "false"):
        raise ValueError(f"{path.name} : champ '{name}' invalide ({value!r}, attendu true ou false)")
    return value == "true"


def _integer(value: str, name: str, path: Path) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{path.name} : champ '{name}' invalide ({value!r}, attendu un entier)") from None


def _front_matter(header: str, path: Path) -> tuple[dict[str, str], list[dict]]:
    """Les champs scalaires du front-matter, et la liste `characters`."""
    fields: dict[str, str] = {}
    characters: list[dict] = []
    for line in header.split("\n"):
        if match := CHARACTER_RE.match(line):
            characters.append({"name": _unquote(match.group(1)), "faction": "", "on_panel": False})
        elif (match := CHARACTER_FIELD_RE.match(line)) and characters:
            key, value = match.groups()
            characters[-1][key] = _boolean(value, f"characters.{key}", path) if key == "on_panel" else _unquote(value)
        elif match := FIELD_RE.match(line):
            fields[match.group(1)] = _unquote(match.group(2))
    return fields, characters


def _sections(body: str) -> dict[str, str]:
    """Chaque titre `## ...` associé au texte qui le suit jusqu'au titre suivant."""
    parts = HEADING_RE.split(body)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _notes(section: str) -> list[str]:
    if section == ABSENT_NOTES:
        return []
    return [line[2:] for line in section.split("\n") if line.startswith("- ")]


def read_chapter(path: Path) -> SilverChapter:
    """Relit un fichier écrit par `write_markdown`.

    ValueError, qui cite le fichier, si le front-matter, l'un des champs
    chapter, arc, revision_id et complete, ou l'une des sections manque, ou si
    un champ n'a pas le type attendu."""
    text = path.read_text(encoding="utf-8")  # les fins de ligne \r\n y deviennent \n
    front = FRONT_MATTER_RE.match(text)
    if front is None:
        raise ValueError(f"{path.name} : front-matter absent")
    fields, characters = _front_matter(front.group(1), path)
    for name in REQUIRED_FIELDS:
        if name not in fields:
            raise ValueError(f"{path.name} : champ '{name}' absent du front-matter")
    found = _sections(text[front.end():])
    for name in SECTIONS:
        if name not in found:
            raise ValueError(f"{path.name} : section '{name}' absente")

    count = fields.get("character_count")
    return SilverChapter(
        number=_integer(fields["chapter"], "chapter", path),
        arc=fields["arc"],
        revision_id=_integer(fields["revision_id"], "revision_id", path),
        complete=_boolean(fields["complete"], "complete", path),
        title=fields.get("title", ""),
        jname=fields.get("jname", ""),
        revised_at=fields.get("revised_at", ""),
        character_count=None if count is None else _integer(count, "character_count", path),
        characters=characters,
        short_summary="" if found["Short Summary"] == ABSENT else found["Short Summary"],
        long_summary="" if found["Long Summary"] == ABSENT else found["Long Summary"],
        notes=_notes(found["Chapter Notes"]),
    )

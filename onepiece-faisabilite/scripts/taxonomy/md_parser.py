"""Lecture des fichiers silver `chapter_NNNN.md` (front-matter YAML + sections Markdown).

Chaque fichier a la forme :

    ---
    chapter: 1
    characters:
      - name: "Shanks"
        faction: "Red Hair Pirates"
        on_panel: true
    ---
    # Chapter 1 — ...
    ## Short Summary
    ...
    ## Long Summary
    ...
    ## Chapter Notes
    - note factuelle
    - Shanks
    - Gold Roger (flashback)

La section `Chapter Notes` mélange en réalité deux choses : des puces factuelles
(événements du chapitre) et, à la suite, la liste des personnages déjà présente
dans le front-matter (parfois annotée `(flashback)`, `(cover)`, ...). On sépare
les deux en comparant chaque puce aux noms de personnages connus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# Annotation entre parenthèses en fin de puce, ex. "Gold Roger (flashback)"
NOTE_ANNOTATION_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<annotation>[^)]+)\)\s*$")


@dataclass
class Chapter:
    """Un chapitre silver, front-matter + texte découpé par section."""

    chapter_id: str
    title: str
    arc: str
    characters: list[dict] = field(default_factory=list)
    short_summary: str = ""
    long_summary: str = ""
    note_bullets: list[str] = field(default_factory=list)
    character_annotations: list[tuple[str, str]] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Texte libre concaténé (résumés + notes factuelles), pour l'extraction NLP."""
        parts = [self.short_summary, self.long_summary, "\n".join(self.note_bullets)]
        return "\n\n".join(p for p in parts if p)


def _read_text(path: Path) -> str:
    """Lit un fichier en utf-8, avec repli latin-1 en cas d'erreur d'encodage."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _split_sections(body: str) -> dict[str, str]:
    """Découpe le corps Markdown en {nom_de_section: contenu}."""
    matches = list(SECTION_RE.finditer(body))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def _split_notes(notes_raw: str, known_names: set[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Sépare les puces de `Chapter Notes` : événements factuels vs liste de personnages.

    Une puce est classée "personnage" si son texte (annotation entre parenthèses
    exclue) correspond exactement à un nom de personnage connu du front-matter.
    """
    factual: list[str] = []
    char_annotations: list[tuple[str, str]] = []
    for line in notes_raw.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        text = line[1:].strip()
        m = NOTE_ANNOTATION_RE.match(text)
        if m and m.group("name") in known_names:
            char_annotations.append((m.group("name"), m.group("annotation")))
        elif text in known_names:
            char_annotations.append((text, ""))
        else:
            factual.append(text)
    return factual, char_annotations


def parse_chapter(path: Path) -> Chapter:
    """Parse un fichier silver en objet `Chapter`."""
    raw = _read_text(path)
    m = FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"front-matter introuvable dans {path}")
    front = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    sections = _split_sections(body)

    characters = front.get("characters") or []
    known_names = {c["name"] for c in characters if "name" in c}
    factual_notes, char_annotations = _split_notes(sections.get("chapter notes", ""), known_names)

    return Chapter(
        chapter_id=str(front.get("chapter", path.stem)),
        title=str(front.get("title", "")),
        arc=str(front.get("arc", "")),
        characters=characters,
        short_summary=sections.get("short summary", ""),
        long_summary=sections.get("long summary", ""),
        note_bullets=factual_notes,
        character_annotations=char_annotations,
    )


def iter_chapters(input_dir: Path):
    """Itère les chapitres d'un dossier silver, triés par numéro de chapitre."""
    paths = sorted(input_dir.glob("chapter_*.md"))
    for path in paths:
        try:
            yield parse_chapter(path)
        except Exception as exc:  # fichier corrompu : on logue et on continue
            print(f"[md_parser] échec du parsing de {path.name} : {exc}")

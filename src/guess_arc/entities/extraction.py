"""Extraction déterministe des Entities : bronze -> Scenes -> Mentions -> Registry(t).

Fonctions pures uniquement : aucune lecture ni écriture. Seul `extract_entities`
est public ; Scenes et Mentions restent internes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from guess_arc.ingestion.parser import section

LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]*)?\]\]")
# Lignes d'un paragraphe qui ne sont pas du récit : sous-titres (===Day 1===),
# titres en gras isolés ('''Level 2, the Beast Hell''') et images seules.
NON_PROSE_LINE_RE = re.compile(
    r"^\s*(?:=+.*=+|'''(?:(?!''').)+'''|\[\[(?:File|Image):.*\]\])\s*$", re.I
)
# Liens qui ne pointent pas vers un article du wiki (images, catégories, Wikipédia).
NON_ARTICLE_PREFIXES = {"file", "image", "category", "template", "wikipedia", "w"}


@dataclass(frozen=True)
class Reference:
    """Tout ce qui vient de l'extérieur, déjà chargé (datasets, catégories du
    wiki, Disguises, overrides de type, mots communs). Vide tant que l'extraction
    ne repose que sur les liens : d'ici là, tout lien d'article est une Mention,
    Concepts compris, un Disguise est résolu dès le premier chapitre (ADR 0002)
    et une redirection reste un Canonical name distinct de sa page cible."""


@dataclass(frozen=True)
class RegistryRow:
    """État d'une Entity dans Registry(t) pour valid_from <= t <= valid_to.

    valid_to à None : l'état vaut encore au dernier chapitre extrait.
    """
    canonical_name: str
    valid_from: int
    valid_to: int | None
    first_chapter_seen: int
    last_chapter_seen: int
    mention_count: int


@dataclass(frozen=True)
class QualityReport:
    scenes_per_chapter: dict[int, int]


@dataclass(frozen=True)
class Extraction:
    registry: list[RegistryRow]
    quality: QualityReport

    def registry_at(self, t: int) -> list[RegistryRow]:
        return [
            row for row in self.registry
            if row.valid_from <= t and (row.valid_to is None or t <= row.valid_to)
        ]


@dataclass(frozen=True)
class _Scene:
    chapter: int
    wikitext: str


@dataclass(frozen=True)
class _Mention:
    canonical_name: str
    chapter: int


def _canonical_name(target: str) -> str | None:
    """Cible d'un lien -> titre de la page d'article, ou None hors articles."""
    # Préfixe de namespace ou d'interwiki seulement : 'Ryu Ryu no Mi, Model: X'
    # est un article dont le titre contient un ':'.
    prefix = target.lstrip(":").split(":", 1)[0].strip().lower()
    if ":" in target and prefix in NON_ARTICLE_PREFIXES:
        return None
    # [[Page#Section]] et [[Page/Sous-page]] désignent l'Entity de la page parente.
    title = target.split("#", 1)[0].split("/", 1)[0].strip()
    if not title:  # [[#Section]] : ancre dans la page courante
        return None
    # Le wiki ignore la casse de la première lettre : [[pirate]] -> Pirate.
    return title[0].upper() + title[1:]


def _scenes(chapter: int, long_summary: str) -> list[_Scene]:
    """Un paragraphe du Long Summary = une Scene, une fois ôtées les lignes hors récit."""
    scenes = []
    for paragraph in re.split(r"\n\s*\n", long_summary):
        prose = "\n".join(
            line for line in paragraph.splitlines() if not NON_PROSE_LINE_RE.match(line)
        ).strip()
        if prose:
            scenes.append(_Scene(chapter, prose))
    return scenes


def _mentions(scene: _Scene) -> list[_Mention]:
    return [
        _Mention(name, scene.chapter)
        for m in LINK_RE.finditer(scene.wikitext)
        if (name := _canonical_name(m.group(1))) is not None
    ]


def _registry(mentions: list[_Mention]) -> list[RegistryRow]:
    # Une ligne par Entity et par chapitre où elle est mentionnée : c'est là
    # que last_chapter_seen et mention_count changent.
    counts: dict[str, dict[int, int]] = {}
    for m in mentions:
        per_chapter = counts.setdefault(m.canonical_name, {})
        per_chapter[m.chapter] = per_chapter.get(m.chapter, 0) + 1

    rows = []
    for name, per_chapter in sorted(counts.items()):
        chapters = sorted(per_chapter)
        total = 0
        for i, ch in enumerate(chapters):
            total += per_chapter[ch]
            rows.append(RegistryRow(
                canonical_name=name,
                valid_from=ch,
                valid_to=chapters[i + 1] - 1 if i + 1 < len(chapters) else None,
                first_chapter_seen=chapters[0],
                last_chapter_seen=ch,
                mention_count=total,
            ))
    return rows


def extract_entities(chapters: list[dict], reference: Reference) -> Extraction:
    """Bronze déjà en mémoire -> Registry(t) publiable."""
    scenes_per_chapter = {}
    mentions = []
    for rec in sorted(chapters, key=lambda r: r["number"]):
        scenes = _scenes(rec["number"], section(rec["wikitext"], "Long Summary"))
        scenes_per_chapter[rec["number"]] = len(scenes)
        mentions += [m for scene in scenes for m in _mentions(scene)]
    return Extraction(
        registry=_registry(mentions),
        quality=QualityReport(scenes_per_chapter=scenes_per_chapter),
    )

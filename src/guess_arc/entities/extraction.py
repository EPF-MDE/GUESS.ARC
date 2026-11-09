"""Extraction déterministe des Entities : bronze -> Scenes -> Mentions -> Registry(t).

Fonctions pures uniquement : aucune lecture ni écriture. Seul `extract_entities`
est public ; Scenes et Mentions restent internes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from guess_arc.ingestion.parser import ARC_RE, parse_characters, parse_groups, section

LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")
# Texte de lien à nettoyer avant d'en faire un Alias : gras/italique, guillemets
# englobants, apostrophe typographique, ponctuation finale et possessif
# ("Luffy's" -> "Luffy", "Shanks'" -> "Shanks").
WIKI_EMPHASIS_RE = re.compile(r"'{2,}")
QUOTES = {'"': '"', "“": "”"}
POSSESSIVE_RE = re.compile(r"(?:'s|(?<=s)')$")
# Lignes d'un paragraphe qui ne sont pas du récit : sous-titres (===Day 1===),
# titres en gras isolés ('''Level 2, the Beast Hell''') et images seules.
NON_PROSE_LINE_RE = re.compile(
    r"^\s*(?:=+.*=+|'''(?:(?!''').)+'''|\[\[(?:File|Image):.*\]\])\s*$", re.I
)
# Liens qui ne pointent pas vers un article du wiki (images, catégories, Wikipédia).
NON_ARTICLE_PREFIXES = {"file", "image", "category", "template", "wikipedia", "w"}
# Sections dont les liens pipés sont lus pour les Disguise candidates : la CharTable
# et les notes nomment souvent un Disguise que le Long Summary ne lie jamais
# (["Lucy"] -> Sabo n'apparaît que là).
DISGUISE_SECTIONS = ("Long Summary", "Characters", "Chapter Notes")


@dataclass(frozen=True)
class Reference:
    """Tout ce qui vient de l'extérieur, déjà chargé (datasets, catégories du
    wiki, Disguises, overrides de type, mots communs). Tant que l'extraction
    ne repose que sur les liens, tout lien d'article est une Mention, Concepts
    compris, un Disguise est résolu dès le premier chapitre (ADR 0002) et une
    redirection reste un Canonical name distinct de sa page cible.

    common_words : mots en minuscules (pronoms, déterminants) ; un texte de lien
    qui commence par l'un d'eux n'est pas un Alias ("Their mother").
    """
    common_words: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RegistryRow:
    """État d'une Entity dans Registry(t) pour valid_from <= t <= valid_to.

    valid_to à None : l'état vaut encore au dernier chapitre extrait.
    aliases : Aliases déjà utilisés au chapitre valid_from, triés (ADR 0002).
    """
    canonical_name: str
    aliases: tuple[str, ...]
    valid_from: int
    valid_to: int | None
    first_chapter_seen: int
    last_chapter_seen: int
    mention_count: int


@dataclass(frozen=True)
class QualityReport:
    """recall_proxy : part des Characters ayant une Appearance dans la CharTable
    qui ont aussi au moins une Mention dans le Long Summary du même chapitre
    (None sans aucune Appearance). Ratio global, et par arc."""
    scenes_per_chapter: dict[int, int]
    recall_proxy: float | None
    recall_proxy_per_arc: dict[str, float]


@dataclass(frozen=True)
class DisguiseCandidate:
    """Alias qui ressemble au nom d'une autre personne que son Character.

    Liste à relire par un humain : il confirme les vrais Disguises et remplit
    revelation, le chapitre où le lecteur apprend la vraie identité.
    """
    alias: str
    canonical_name: str
    link_count: int
    first_chapter: int
    last_chapter: int
    revelation: int | None = None


@dataclass(frozen=True)
class Extraction:
    registry: list[RegistryRow]
    quality: QualityReport
    disguise_candidates: list[DisguiseCandidate]

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
    alias: str | None


@dataclass(frozen=True)
class _CastEntry:
    """Présence d'un Character (Appearance, Recall ou Cover appearance) ou d'un
    Group (en-tête de faction lié) dans la CharTable d'un chapitre. Pas une Mention."""
    canonical_name: str
    chapter: int
    appearance: bool


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


def _alias(target: str, canonical_name: str, text: str | None,
           common_words: frozenset[str]) -> str | None:
    """Texte d'un lien pipé -> Alias de l'Entity, s'il ressemble à un nom."""
    # Le texte d'un lien vers une sous-page ou une section nomme cette partie
    # ("Gear 5"), pas l'Entity parente.
    if text is None or "#" in target or "/" in target:
        return None
    text = WIKI_EMPHASIS_RE.sub("", text).replace("’", "'").strip()
    if text[:1] in QUOTES and text.endswith(QUOTES[text[0]]):
        text = text[1:-1].strip()
    text = POSSESSIVE_RE.sub("", text.rstrip(",;:")).strip()
    if not text or not text[0].isupper() or text == canonical_name:
        return None
    if text.split()[0].strip(".,;:").lower() in common_words:
        return None
    return text


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


def _mentions(scene: _Scene, common_words: frozenset[str]) -> list[_Mention]:
    # Le lien reste une Mention même quand son texte n'est pas un Alias.
    return [
        _Mention(name, scene.chapter, _alias(m.group(1), name, m.group(2), common_words))
        for m in LINK_RE.finditer(scene.wikitext)
        if (name := _canonical_name(m.group(1))) is not None
    ]


def _cast(chapter: int, char_section: str) -> list[_CastEntry]:
    """CharTable -> Characters présents et Groups des en-têtes liés."""
    entries = []
    for c in parse_characters(char_section):
        name = _canonical_name(c["name"])
        annotations = " ".join(c["annotations"])
        # Une présence "mentioned" ou "dream" n'est ni une Appearance, ni un
        # Recall, ni une Cover appearance.
        if name is not None and (c["on_panel"] or "flashback" in annotations
                                 or "cover" in annotations):
            entries.append(_CastEntry(name, chapter, appearance=c["on_panel"]))
    entries += [
        _CastEntry(name, chapter, appearance=False)
        for group in parse_groups(char_section)
        if (name := _canonical_name(group)) is not None
    ]
    return entries


def _recall_proxy(cast: list[_CastEntry], mentions: list[_Mention],
                  arcs: dict[int, str]) -> tuple[float | None, dict[str, float]]:
    mentioned = {(m.canonical_name, m.chapter) for m in mentions}
    hits: dict[str, list[bool]] = {}
    for e in cast:
        if e.appearance:
            hits.setdefault(arcs[e.chapter], []).append((e.canonical_name, e.chapter) in mentioned)
    every = [hit for arc_hits in hits.values() for hit in arc_hits]
    overall = sum(every) / len(every) if every else None
    return overall, {arc: sum(h) / len(h) for arc, h in sorted(hits.items())}


def _registry(mentions: list[_Mention], cast: list[_CastEntry]) -> list[RegistryRow]:
    # Une ligne par Entity et par chapitre où elle est vue (Mention ou CharTable) :
    # c'est là que last_chapter_seen et mention_count changent.
    counts: dict[str, dict[int, int]] = {}
    alias_first_use: dict[str, dict[str, int]] = {}
    for m in mentions:
        per_chapter = counts.setdefault(m.canonical_name, {})
        per_chapter[m.chapter] = per_chapter.get(m.chapter, 0) + 1
        if m.alias is not None:
            first_use = alias_first_use.setdefault(m.canonical_name, {})
            first_use[m.alias] = min(first_use.get(m.alias, m.chapter), m.chapter)
    for e in cast:
        counts.setdefault(e.canonical_name, {}).setdefault(e.chapter, 0)

    rows = []
    for name, per_chapter in sorted(counts.items()):
        first_use = alias_first_use.get(name, {})
        chapters = sorted(per_chapter)
        total = 0
        for i, ch in enumerate(chapters):
            total += per_chapter[ch]
            # Un Alias commence toujours sur une ligne : sa première utilisation
            # est une Mention, donc un chapitre où l'état de l'Entity change.
            rows.append(RegistryRow(
                canonical_name=name,
                aliases=tuple(sorted(a for a, first in first_use.items() if first <= ch)),
                valid_from=ch,
                valid_to=chapters[i + 1] - 1 if i + 1 < len(chapters) else None,
                first_chapter_seen=chapters[0],
                last_chapter_seen=ch,
                mention_count=total,
            ))
    return rows


def _name_tokens(name: str) -> set[str]:
    return set(re.findall(r"\w+", name.lower()))


def _disguise_candidates(chapters: list[dict], common_words: frozenset[str]) -> list[DisguiseCandidate]:
    """Aliases sans aucun mot commun avec leur Canonical name, Characters seulement.

    Liste de relecture hors ligne, pas Registry(t) : elle lit tout le corpus d'un
    coup, d'où un Character reconnu à sa présence dans n'importe quelle CharTable.
    """
    characters: set[str] = set()
    link_chapters: dict[tuple[str, str], list[int]] = {}
    for rec in chapters:
        wikitext = rec["wikitext"]
        characters |= {
            name for c in parse_characters(section(wikitext, "Characters"))
            if (name := _canonical_name(c["name"])) is not None
        }
        for heading in DISGUISE_SECTIONS:
            for m in LINK_RE.finditer(section(wikitext, heading)):
                name = _canonical_name(m.group(1))
                if name is None:
                    continue
                alias = _alias(m.group(1), name, m.group(2), common_words)
                # "Robin" -> Nico Robin est un simple Alias ; "Miss All Sunday" ne
                # partage aucun mot avec Nico Robin.
                if alias and _name_tokens(alias).isdisjoint(_name_tokens(name)):
                    link_chapters.setdefault((alias, name), []).append(rec["number"])

    candidates = [
        DisguiseCandidate(alias, name, len(chs), min(chs), max(chs))
        for (alias, name), chs in link_chapters.items()
        if name in characters
    ]
    return sorted(candidates, key=lambda c: (-c.link_count, c.alias, c.canonical_name))


def extract_entities(chapters: list[dict], reference: Reference) -> Extraction:
    """Bronze déjà en mémoire -> Registry(t) publiable + Disguise candidates à relire."""
    scenes_per_chapter = {}
    arcs = {}
    mentions = []
    cast = []
    for rec in sorted(chapters, key=lambda r: r["number"]):
        number, wikitext = rec["number"], rec["wikitext"]
        scenes = _scenes(number, section(wikitext, "Long Summary"))
        scenes_per_chapter[number] = len(scenes)
        arc = ARC_RE.search(wikitext)
        arcs[number] = arc.group(1) if arc else "Unknown"
        mentions += [m for scene in scenes for m in _mentions(scene, reference.common_words)]
        cast += _cast(number, section(wikitext, "Characters"))
    recall_proxy, recall_proxy_per_arc = _recall_proxy(cast, mentions, arcs)
    return Extraction(
        registry=_registry(mentions, cast),
        quality=QualityReport(
            scenes_per_chapter=scenes_per_chapter,
            recall_proxy=recall_proxy,
            recall_proxy_per_arc=recall_proxy_per_arc,
        ),
        disguise_candidates=_disguise_candidates(chapters, reference.common_words),
    )

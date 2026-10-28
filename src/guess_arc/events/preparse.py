"""Préparsing : un chapitre de la silver -> le texte lu par le modèle.

Deux étapes, dans cet ordre :

1. normaliser chaque texte (entités HTML, espaces insécables et invisibles,
   restes de balisage wiki, espaces multiples), pour que la preuve citée par le
   modèle se retrouve ensuite telle quelle dans le texte ;
2. retirer les notes éditoriales (début ou fin d'arc, anime, volume, SBS) et
   les notes de couverture (les cover stories sont exclues en v1), en comptant
   chaque suppression dans `flags`.

Les règles de retrait ont été écrites sur la silver réelle (voir
`plan_extraction_evenements.md`, §2.2). Elles retirent la note entière : une
note qui mêle un fait du chapitre et une couverture est perdue, c'est assumé.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from .silver import SilverChapter

# --- Normalisation -----------------------------------------------------------

FILE_RE = re.compile(r"\[\[(?:File|Image):[^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*\]\]",
                     re.IGNORECASE)
LINK_RE = re.compile(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
# Texte barré : la version corrigée suit, on ne garde qu'elle (« <s>3D</s>2Y »).
STRUCK_RE = re.compile(r"<s>.*?</s>", re.IGNORECASE | re.DOTALL)
BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
SPACES_RE = re.compile(r"[  -   　\t]")
INVISIBLE_RE = re.compile(r"[​-‍⁠﻿]")


def normalize(text: str) -> str:
    text = html.unescape(text)
    text = FILE_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)
    while TEMPLATE_RE.search(text):
        text = TEMPLATE_RE.sub("", text)
    text = STRUCK_RE.sub("", text)
    text = BREAK_RE.sub(" ", text)
    text = TAG_RE.sub("", text)
    text = re.sub(r"\[\[|\]\]|\{\{|\}\}|'{2,}", "", text)
    text = SPACES_RE.sub(" ", text)
    text = INVISIBLE_RE.sub("", text)
    # Un modèle retiré laisse souvent une espace devant la ponctuation.
    text = re.sub(r" +([.,;:!?])", r"\1", text)
    lines = [re.sub(r" {2,}", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --- Notes à retirer ---------------------------------------------------------

EDITORIAL_RE = re.compile(
    r"|".join([
        # place du chapitre dans l'arc, la saga ou la série
        r"\b(first|last|final) chapter (of|in)\b.*\b(arc|saga|series)\b",
        r"\bmarks the (start|end|beginning) of\b.*\b(act|arc|saga|half)\b",
        r"\bact of the\b.*\barc begins\b",
        # anime (mais pas « anime-only », qui qualifie un personnage)
        r"\banime\b(?!-only)",
        r"\bOne Piece Opening\b",
        # éditions : magazine, volume relié, Viz
        r"\bvolume \d+",
        r"\b(volume|magazine|jump) (release|version|re-release)\b",
        r"\bshou?nen jump\b",
        r"\bviz\b",
        r"\bSBS\b",
    ]),
    re.IGNORECASE,
)

COVER_RE = re.compile(
    r"|".join([
        # « a cover story for » : alibi, pas une couverture
        r"\bcover[ -]?(story|stories|page|pages|art|arc|mini-story)\b(?! for\b)",
        r"\bcoverstory\b",
        r"\b(the|chapter|chapter's) cover\b(?![ -]up)",
        r"\bcolou?r spread\b",
        # début ou fin d'une cover story désignée par son seul titre
        r"\b(first|last|final) chapter of\b(?!.*\b(arc|saga|series)\b)",
    ]),
    re.IGNORECASE,
)

# Ordre de priorité : une note qui relève des deux catégories compte une fois.
NOTE_RULES = (
    ("editorial_notes_removed", EDITORIAL_RE),
    ("cover_notes_removed", COVER_RE),
)


@dataclass
class Preparsed:
    number: int
    title: str
    arc: str
    revision_id: int | None
    short_summary: str
    long_summary: str
    notes: list[str]
    flags: dict[str, int] = field(default_factory=dict)


def preparse(ch: SilverChapter) -> Preparsed:
    flags = {name: 0 for name, _ in NOTE_RULES}
    notes = []
    for note in map(normalize, ch.notes):
        if not note:
            continue
        rule = next((name for name, regex in NOTE_RULES if regex.search(note)), None)
        if rule:
            flags[rule] += 1
        else:
            notes.append(note)
    return Preparsed(
        number=ch.number,
        title=normalize(ch.title),
        arc=normalize(ch.arc),
        revision_id=ch.revision_id,
        short_summary=normalize(ch.short_summary),
        long_summary=normalize(ch.long_summary),
        notes=notes,
        flags=flags,
    )

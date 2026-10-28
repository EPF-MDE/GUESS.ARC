"""Fuites du futur : passages qui parlent de la suite de l'histoire.

Une expression régulière repère les candidats (une phrase des résumés, une note
entière) ; un humain tranche dans un fichier de relecture versionné
(`review/future_leaks.json`), une entrée par candidat :

    {"chapter": 97, "section": "long_summary", "passage": "…", "decision": "remove"}

`decision` vaut `remove` (retiré du texte), `keep` (laissé) ou `null` (pas encore
relu : laissé). Un passage est reconnu à son texte exact après normalisation :
si la silver change, il redevient un candidat à relire.

L'expression vient de `plan_extraction_evenements.md`, §2.2-4. Elle ignore les
ellipses du récit (« 10 years later, Luffy sets out to sea »).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

LEAK_RE = re.compile(
    r"\b(would (later|eventually|go on to)|will later|later (be )?revealed"
    r"|later in the series|in (a )?later chapters?|in the future|foreshadow\w*"
    r"|(is|was) later)\b",
    re.IGNORECASE,
)

DECISIONS = ("remove", "keep", None)
# Sections où l'on cherche, dans l'ordre de la liste des candidats.
SECTIONS = ("short_summary", "long_summary", "notes")

# Fin de phrase : ponctuation, guillemet ou parenthèse fermants éventuels, espace,
# puis une majuscule, un chiffre ou un guillemet ouvrant.
SENTENCE_END_RE = re.compile(r"[.!?]+[\"'”’)]*(?= +[A-Z0-9\"'“‘(])")
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "lt", "jr", "sr", "vs", "no", "vol", "ch"}


@dataclass(frozen=True)
class Candidate:
    chapter: int
    section: str
    passage: str
    decision: str | None = None

    @property
    def key(self) -> tuple[int, str, str]:
        return (self.chapter, self.section, self.passage)


def split_sentences(paragraph: str) -> list[str]:
    sentences, start = [], 0
    for match in SENTENCE_END_RE.finditer(paragraph):
        words = paragraph[start:match.start()].split()
        if words and words[-1].lstrip("\"'“‘(").lower() in ABBREVIATIONS:
            continue
        sentences.append(paragraph[start:match.end()].strip())
        start = match.end()
    sentences.append(paragraph[start:].strip())
    return [s for s in sentences if s]


def load_review(path: Path) -> dict[tuple[int, str, str], str | None]:
    """Décisions de relecture ; un fichier absent ne contient aucune décision."""
    if not path.exists():
        return {}
    decisions = {}
    for entry in json.loads(path.read_text(encoding="utf-8")):
        c = Candidate(int(entry["chapter"]), entry["section"], entry["passage"],
                      entry.get("decision"))
        if c.section not in SECTIONS or c.decision not in DECISIONS:
            raise ValueError(f"{path.name} : entrée invalide {entry}")
        decisions[c.key] = c.decision
    return decisions


def write_candidates(candidates: list[Candidate], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(c) for c in candidates], ensure_ascii=False, indent=2)
                    + "\n", encoding="utf-8")


class LeakFilter:
    """Repère les candidats d'un chapitre et retire ceux que la relecture retient."""

    def __init__(self, chapter: int, decisions: dict[tuple[int, str, str], str | None]):
        self.chapter = chapter
        self.decisions = decisions
        self.found: list[Candidate] = []
        self.removed = 0

    def _record_and_keep(self, section: str, passage: str) -> bool:
        """Note le passage s'il est candidat ; faux s'il faut le retirer."""
        if not LEAK_RE.search(passage):
            return True
        key = (self.chapter, section, passage)
        c = Candidate(*key, self.decisions.get(key))
        self.found.append(c)
        if c.decision == "remove":
            self.removed += 1
            return False
        return True

    def filter_summary(self, section: str, text: str) -> str:
        paragraphs = []
        for paragraph in text.split("\n\n"):
            sentences = split_sentences(paragraph)
            kept = [s for s in sentences if self._record_and_keep(section, s)]
            if len(kept) == len(sentences):
                paragraphs.append(paragraph)
            elif kept:
                paragraphs.append(" ".join(kept))
        return "\n\n".join(paragraphs)

    def filter_notes(self, notes: list[str]) -> list[str]:
        return [n for n in notes if self._record_and_keep("notes", n)]

    @property
    def candidates(self) -> list[Candidate]:
        return sorted(self.found, key=lambda c: SECTIONS.index(c.section))


def stale_decisions(decisions: dict[tuple[int, str, str], str | None],
                    candidates: list[Candidate], chapters: set[int]) -> int:
    """Décisions prises sur les chapitres traités qui ne désignent plus aucun candidat.

    Le texte de la silver a changé : le passage est à relire sous sa nouvelle forme.
    """
    found = {c.key for c in candidates}
    return sum(1 for key, decision in decisions.items()
               if decision is not None and key[0] in chapters and key not in found)

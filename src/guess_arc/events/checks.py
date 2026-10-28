"""Contrôles des événements `llm` : ils mesurent la qualité de l'extracteur.

Chaque événement du modèle reçoit des `checks` ; un événement en échec est
marqué, jamais supprimé : le filtrage se fait au moment de consommer le dataset.

- `evidence_found` : la preuve figure dans le texte d'entrée du chapitre, après
  normalisation des espaces et des guillemets (« ’ » vaut « ' », « “ » vaut « " ») ;
- `future_leak` : la description cite un personnage qui n'apparaît qu'après le
  chapitre t (pas encore présenté, fiche datée d'un chapitre ultérieur), ou
  emploie « later », « will » ou « future ».

`unlisted_entities` reçoit le même contrôle de fuite, pour tout le chapitre
(`unlisted_checks`). Enfin, les événements identiques (boucle de répétition à
température 0) sont dédoublonnés et comptés.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

QUOTES = str.maketrans({c: "'" for c in "’‘‚‛′`´"} | {c: '"' for c in "“”„‟″«»"})
SPACES_RE = re.compile(r"\s+")
FUTURE_WORDS_RE = re.compile(r"\b(?:later|will|future)\b", re.IGNORECASE)


def normalized(text: str) -> str:
    return SPACES_RE.sub(" ", text.translate(QUOTES)).strip()


def deduplicated(events: list[dict]) -> tuple[list[dict], int]:
    """Événements dans l'ordre, sans les copies exactes d'un événement précédent,
    et le nombre de copies retirées."""
    kept = []
    for e in events:
        if e not in kept:
            kept.append(e)
    return kept, len(events) - len(kept)


@dataclass(frozen=True)
class ChapterChecks:
    text: str                                   # texte d'entrée du chapitre
    future_names: Callable[[str], list[str]]    # personnages futurs cités dans un texte
    _normalized_text: str = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_normalized_text", normalized(self.text))

    def event_checks(self, e: dict) -> dict:
        evidence = normalized(e["evidence"])
        return {
            "evidence_found": bool(evidence) and evidence in self._normalized_text,
            "future_leak": bool(FUTURE_WORDS_RE.search(e["description"])
                                or self.future_names(e["description"])),
        }

    def unlisted_checks(self, names: list[str]) -> dict:
        return {"future_leak": any(self.future_names(name) for name in names)}

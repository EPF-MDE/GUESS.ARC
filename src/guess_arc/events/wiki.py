"""Événements d'origine `wiki` : déduits des apparitions, sans appel au modèle.

Calculés sur la séquence ordonnée des chapitres de la silver, en ne lisant
jamais un chapitre postérieur à celui qu'on traite :

- `first_appearance` : premier chapitre où le personnage est présenté (présent à
  l'image ou montré en flashback ; une mention, une couverture, y compris un
  flashback en couverture, ou un rêve ne comptent pas) ;
- `return` : premier chapitre de l'arc courant où le personnage est présent à
  l'image, s'il était absent à l'image de tout l'arc précédent et avait été
  présenté avant le début de l'arc courant. L'ordre des arcs suit la première
  occurrence de leur label. Une absence prolongée à l'intérieur d'un arc n'est
  pas un retour (assumé en v1) ;
- `defeat` : un par annotation K.O., sauf en couverture (les cover stories sont
  exclues en v1).

« Présent à l'image » est le champ `on_panel` de la silver.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .silver import Appearance, SilverChapter


@dataclass(frozen=True)
class WikiEvent:
    type: str
    name: str
    role: str
    description: str
    in_flashback: bool


def _first_appearance(a: Appearance) -> WikiEvent:
    in_flashback = not a.on_panel
    description = f"{a.name} appears for the first time" + (
        ", in a flashback." if in_flashback else ".")
    return WikiEvent("first_appearance", a.name, "agent", description, in_flashback)


def _return(a: Appearance, previous_arc: str) -> WikiEvent:
    return WikiEvent("return", a.name, "agent",
                     f"{a.name} returns after being absent for the whole {previous_arc}.",
                     False)


def _defeat(a: Appearance) -> WikiEvent:
    description = f"{a.name} is knocked out" + (" in a flashback." if a.in_flashback else ".")
    return WikiEvent("defeat", a.name, "target", description, a.in_flashback)


def wiki_events(chapters: Iterable[SilverChapter]) -> dict[int, list[WikiEvent]]:
    """Événements `wiki` de chaque chapitre, chapitres donnés dans l'ordre."""
    arcs: list[str] = []                      # labels, par première occurrence
    on_panel: dict[str, set[str]] = {}        # arc -> présents à l'image jusqu'ici
    presented_before: dict[str, set[str]] = {}  # arc -> présentés avant son début
    presented_so_far: set[str] = set()
    out = {}
    for ch in chapters:
        if ch.arc not in on_panel:
            arcs.append(ch.arc)
            on_panel[ch.arc] = set()
            presented_before[ch.arc] = set(presented_so_far)
        index = arcs.index(ch.arc)
        previous_arc = arcs[index - 1] if index > 0 else None
        firsts, returns, defeats = [], [], []
        for a in ch.characters:
            if a.presented and a.name not in presented_so_far:
                firsts.append(_first_appearance(a))
            if (a.on_panel and previous_arc is not None
                    and a.name in presented_before[ch.arc]
                    and a.name not in on_panel[previous_arc]
                    and a.name not in on_panel[ch.arc]):
                returns.append(_return(a, previous_arc))
            if "ko" in a.annotations and "cover" not in a.annotations:
                defeats.append(_defeat(a))
        for a in ch.characters:
            if a.presented:
                presented_so_far.add(a.name)
            if a.on_panel:
                on_panel[ch.arc].add(a.name)
        out[ch.number] = firsts + returns + defeats
    return out

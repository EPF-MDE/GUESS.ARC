"""Entités « sans futur » : le bloc ENTITIES du prompt et les noms autorisés.

Les fiches viennent de `data/Entité/` (v0). Elles sont écrites avec le recul
(« Son of Dragon » au chapitre 1) : on n'en envoie que les champs sans futur
(`plan_extraction_evenements.md`, §3.3) :

- personnages : nom, alias, race, étapes du `journey` datées d'un chapitre ≤ t ;
- fruits du démon : nom (et nom anglais) ;
- îles : nom et mer.

Seules les entités du chapitre t sont envoyées : les personnages de la table qui
ne sont pas en couverture, plus ceux dont un nom ou un alias est cité dans le
texte ; les fruits et les îles cités dans le texte. Filtre de temps : un
personnage n'est envoyé qu'une fois apparu, c'est-à-dire présenté dans un
chapitre ≤ t de la silver ou dont la fiche date la première apparition
(« Chapter N ») d'un chapitre ≤ t.

Table d'alias : nom complet, nom sans crochets ni parenthèses, contenu des
crochets et des parenthèses (« Cutty Flam [Franky] »), puis dernier mot du nom
(« Luffy ») s'il n'est ni le dernier mot d'un autre personnage, ni un alias
d'un autre, ni un chiffre ou une initiale (« Baby 5 », « Ivan X »). Un alias
partagé par deux fiches n'est pas utilisé. Les noms sont comparés après
normalisation de la casse, des accents, des apostrophes et de la ponctuation.

Dans le texte, un nom n'est reconnu que s'il commence par une majuscule
(« King », pas « the king ») ; « Zoro's » vaut « Zoro ». Un nom d'un seul mot
plus souvent écrit en minuscules qu'avec une majuscule en milieu de phrase,
dans les chapitres ≤ t, est un mot courant et n'est pas cherché seul (« One »
de « One Piece » n'est pas Page One ; « Law » reste Trafalgar Law).

Un personnage de la table absent des fiches est envoyé sous son nom de la
silver, sans autre champ.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .preparse import normalize
from .silver import SilverChapter

APOSTROPHE_RE = re.compile(r"['’‘`´]")
POSSESSIVE_RE = re.compile(r"['’]s\b")
WORD_RE = re.compile(r"\w+")
# Ce qui précède un mot en début de phrase : rien, ou une ponctuation de fin de
# phrase, un guillemet, une parenthèse ouvrante, puis des espaces.
SENTENCE_START_RE = re.compile(r"(^|[.!?:\"“”(\n])\s*$")
BRACKETED_RE = re.compile(r"\[([^\]]*)\]|\(([^)]*)\)")
CHAPTER_RE = re.compile(r"^Chapter (\d+)$")


def _strip_accents_and_apostrophes(text: str) -> str:
    text = unicodedata.normalize("NFKD", APOSTROPHE_RE.sub("", text))
    return "".join(c for c in text if not unicodedata.combining(c))


def name_key(name: str) -> str:
    """Forme de comparaison : « Kin'emon » et « kinemon » donnent la même clé."""
    return " ".join(WORD_RE.findall(_strip_accents_and_apostrophes(name).casefold()))


def mentioned_keys(text: str, max_words: int) -> set[str]:
    """Clés de toutes les suites de 1 à `max_words` mots du texte qui commencent par
    une majuscule ou un chiffre, avec et sans le « 's » possessif."""
    keys = set()
    for variant in (text, POSSESSIVE_RE.sub("", text)):
        words = WORD_RE.findall(_strip_accents_and_apostrophes(variant))
        for i, word in enumerate(words):
            if not (word[0].isupper() or word[0].isdigit()):
                continue
            for n in range(1, max_words + 1):
                if i + n <= len(words):
                    keys.add(" ".join(words[i:i + n]).casefold())
    return keys


# --- Fiches ------------------------------------------------------------------

@dataclass(frozen=True)
class Character:
    name: str
    race: str = ""
    # Alias affichés, dans l'ordre : nom de base, parenthèses, crochets, dernier mot.
    aliases: tuple[str, ...] = ()
    first_chapter: int | None = None
    journey: tuple[tuple[str, int], ...] = ()   # (lieu, chapitre), étapes datées seules

    def card(self, chapter: int) -> str:
        parts = []
        if self.aliases:
            parts.append("aliases: " + ", ".join(self.aliases))
        if self.race:
            parts.append(f"race: {self.race}")
        steps = [f"{place} (ch. {n})" for place, n in self.journey if n <= chapter]
        if steps:
            parts.append("journey: " + ", ".join(steps))
        return f"- {self.name}" + (f" ({'; '.join(parts)})" if parts else "")


@dataclass(frozen=True)
class Fruit:
    name: str
    english: str = ""

    def card(self) -> str:
        return f"- {self.name}" + (f" ({self.english})" if self.english else "")


@dataclass(frozen=True)
class Island:
    name: str
    sea: str = ""

    def card(self) -> str:
        return f"- {self.name}" + (f" ({self.sea})" if self.sea else "")


def _chapter(value: str | None) -> int | None:
    match = CHAPTER_RE.match((value or "").strip())
    return int(match.group(1)) if match else None


def _base_and_bracketed(name: str) -> tuple[str, list[str]]:
    matches = list(BRACKETED_RE.finditer(name))
    # Parenthèses d'abord, puis crochets : « Bentham (Bon Clay) [Mr. 2] ».
    bracketed = [m.group(2).strip() for m in matches if m.group(2)]
    bracketed += [m.group(1).strip() for m in matches if m.group(1)]
    base = re.sub(r"\s+", " ", BRACKETED_RE.sub(" ", name)).strip()
    return base, [b for b in bracketed if b]


def _read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


@dataclass
class Entities:
    characters: list[Character] = field(default_factory=list)
    fruits: list[Fruit] = field(default_factory=list)
    islands: list[Island] = field(default_factory=list)
    # Clé d'un alias non ambigu -> personnage.
    aliases: dict[str, Character] = field(default_factory=dict)
    fruit_keys: dict[Fruit, set[str]] = field(default_factory=dict)
    island_keys: dict[Island, set[str]] = field(default_factory=dict)
    max_words: int = 1

    @classmethod
    def load(cls, entity_dir: Path) -> Entities:
        """Fiches de `entity_dir` ; un fichier absent ne contient aucune fiche."""
        raw = _read(entity_dir / "characters.json")
        names = [entry["name"].strip() for entry in raw]
        split = [_base_and_bracketed(name) for name in names]

        owners: dict[str, set[int]] = defaultdict(set)    # alias complet -> fiches
        for i, (name, (base, bracketed)) in enumerate(zip(names, split)):
            for alias in (name, base, *bracketed):
                owners[name_key(alias)].add(i)
        last_words: dict[str, set[int]] = defaultdict(set)
        for i, (base, _) in enumerate(split):
            if len(base.split()) > 1:
                last_words[name_key(base.split()[-1])].add(i)

        entities = cls()
        for i, (entry, name, (base, bracketed)) in enumerate(zip(raw, names, split)):
            shown = [base, *bracketed]
            last = base.split()[-1] if len(base.split()) > 1 else ""
            # Ni chiffre ni initiale : « Baby 5 », « Ivan X ».
            if (len(last) >= 3 and last.isalpha() and last_words[name_key(last)] == {i}
                    and name_key(last) not in owners):
                shown.append(last)
            aliases, seen = [], {name_key(name)}
            for alias in shown:
                if name_key(alias) not in seen:
                    seen.add(name_key(alias))
                    aliases.append(alias)
            journey = tuple(
                (step.get("location", "").strip(), n)
                for step in entry.get("journey") or []
                if (n := _chapter(step.get("chapter") or step.get("Chapter"))) is not None
            )
            c = Character(name, (entry.get("race") or "").strip(), tuple(aliases),
                          _chapter(entry.get("first_appearance_arc")), journey)
            entities.characters.append(c)
            for key in seen:
                if owners.get(key, {i}) == {i}:
                    entities.aliases[key] = c

        for entry in _read(entity_dir / "devil_fruits.json"):
            fruit = Fruit(entry["name"].strip(), (entry.get("english") or "").strip())
            entities.fruits.append(fruit)
            entities.fruit_keys[fruit] = {name_key(n) for n in (fruit.name, fruit.english) if n}
        for entry in _read(entity_dir / "islands.json"):
            sea = (entry.get("location") or "").strip()
            island = Island(entry["name"].strip(), "" if sea == "Unknown" else sea)
            entities.islands.append(island)
            entities.island_keys[island] = {name_key(island.name)}

        keys = [*entities.aliases, *(k for ks in entities.fruit_keys.values() for k in ks),
                *(k for ks in entities.island_keys.values() for k in ks)]
        entities.max_words = max((len(k.split()) for k in keys), default=1)
        return entities

    def resolve(self, name: str) -> Character:
        """Fiche d'un nom de la table des personnages, ou une fiche réduite à ce nom."""
        return self.aliases.get(name_key(name)) or Character(name)


# --- Sélection par chapitre --------------------------------------------------

@dataclass
class EntityBlock:
    chapter: int
    characters: list[Character]
    fruits: list[Fruit]
    islands: list[Island]

    @property
    def allowed_names(self) -> list[str]:
        """Noms autorisés pour les participants : ceux des personnages envoyés."""
        return [c.name for c in self.characters]

    def render(self) -> list[str]:
        def section(title: str, cards: list[str]) -> list[str]:
            return [f"{title}:", *(cards or ["- none"])]
        return [
            "ENTITIES (use these exact names):",
            *section("Characters", [c.card(self.chapter) for c in self.characters]),
            *section("Devil Fruits mentioned", [f.card() for f in self.fruits]),
            *section("Places mentioned", [i.card() for i in self.islands]),
        ]


class EntitySelector:
    """Choisit les entités de chaque chapitre ; les chapitres sont observés dans l'ordre."""

    def __init__(self, entities: Entities):
        self.entities = entities
        self.presented: set[str] = set()   # personnages présentés jusqu'ici
        # Mots lus jusqu'ici : en minuscules, et avec une majuscule hors début de phrase.
        self.lowercase: Counter[str] = Counter()
        self.capitalized: Counter[str] = Counter()

    def observe(self, ch: SilverChapter) -> None:
        for a in ch.characters:
            if a.presented:
                self.presented.add(self.entities.resolve(a.name).name)
        text = _strip_accents_and_apostrophes(
            normalize("\n".join([ch.short_summary, ch.long_summary, *ch.notes])))
        for match in WORD_RE.finditer(text):
            word = match.group()
            if word[0].islower():
                self.lowercase[word] += 1
            elif not SENTENCE_START_RE.search(text[max(0, match.start() - 4):match.start()]):
                self.capitalized[word.casefold()] += 1

    def _common_word(self, key: str) -> bool:
        """Un nom d'un seul mot surtout écrit en minuscules (« one », « house ») n'est pas
        cherché seul dans le texte : « One Piece » ne désigne pas Page One."""
        return " " not in key and self.lowercase[key] > self.capitalized[key]

    def _appeared(self, c: Character, chapter: int) -> bool:
        return c.name in self.presented or (
            c.first_chapter is not None and c.first_chapter <= chapter)

    def _cited(self, mentioned: set[str]) -> list[Character]:
        """Personnages dont un nom ou un alias figure parmi les clés `mentioned`, dans
        l'ordre des fiches."""
        cited = {self.entities.aliases[k].name for k in mentioned & self.entities.aliases.keys()
                 if not self._common_word(k)}
        return [c for c in self.entities.characters if c.name in cited]

    def future_names(self, chapter: int, text: str) -> list[str]:
        """Personnages cités dans `text` qui n'apparaissent qu'après le chapitre
        `chapter`, déjà observé : pas encore apparus, et dont la fiche date la
        première apparition. Sans date, rien ne dit que le personnage est futur.
        `text` entier vaut aussi pour un nom, même écrit en minuscules."""
        mentioned = mentioned_keys(text, self.entities.max_words) | {name_key(text)}
        return [c.name for c in self._cited(mentioned)
                if c.first_chapter is not None and not self._appeared(c, chapter)]

    def select(self, ch: SilverChapter, text: str) -> EntityBlock:
        """Entités du chapitre `ch`, déjà observé ; `text` est le texte envoyé au modèle."""
        chosen: dict[str, Character] = {}
        for a in ch.characters:
            c = self.entities.resolve(a.name)
            if "cover" not in a.annotations and self._appeared(c, ch.number):
                chosen.setdefault(c.name, c)
        mentioned = mentioned_keys(text, self.entities.max_words)
        for c in self._cited(mentioned):
            if self._appeared(c, ch.number):
                chosen.setdefault(c.name, c)
        return EntityBlock(
            chapter=ch.number,
            characters=list(chosen.values()),
            fruits=[f for f in self.entities.fruits if self.entities.fruit_keys[f] & mentioned],
            islands=[i for i in self.entities.islands
                     if self.entities.island_keys[i] & mentioned],
        )

"""Extraction de candidats de tags à partir d'un texte libre (anglais).

Deux modes :
  - "spacy"  : NER + lemmatisation via un modèle spaCy anglais (en_core_web_md,
    repli en_core_web_sm). Utilisé pour perso/lieu (entités nommées) et pour
    améliorer la détection des verbes/noms d'événements (lemmes).
  - "regex"  : repli sans dépendance, utilisé si spaCy ou ses modèles ne sont
    pas installables (pas d'accès réseau). Séquences de mots capitalisés pour
    les entités, recherche de mots-clés pour les événements/relations/objets.

Dans les deux modes, la détection des objets (fruits du démon, poneglyphes,
armes, navires, trésors) et des relations/événements par mots-clés est
identique : elle ne dépend pas de spaCy, seule la détection perso/lieu change.

Ce module est partagé par `01_extract_candidates.py` (corpus complet) et
`04_tag_text.py` (un texte isolé, résumé prédit à la main compris) : le même
code d'extraction doit tourner dans les deux cas pour que les tags soient
comparables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Lexiques (anglais -> tag canonique en français, comme demandé dans la spec)
# --------------------------------------------------------------------------

# Verbes et noms d'événements narratifs. Les clés sont des formes de surface
# anglaises (déjà à plusieurs inflexions pour le mode regex) ou des lemmes
# (mode spaCy, qui normalise automatiquement les inflexions des verbes).
EVENT_LEXICON: dict[str, str] = {
    # combat
    "fight": "combat", "fights": "combat", "fought": "combat", "fighting": "combat",
    "battle": "combat", "battles": "combat", "battled": "combat", "clash": "combat",
    "clashes": "combat", "clashed": "combat", "duel": "combat", "duels": "combat",
    "brawl": "combat", "confrontation": "combat", "attack": "combat", "attacks": "combat",
    "attacked": "combat", "strikes": "combat", "struck": "combat",
    # révélation
    "reveal": "révélation", "reveals": "révélation", "revealed": "révélation",
    "revelation": "révélation", "discover": "révélation", "discovers": "révélation",
    "discovered": "révélation", "learns": "révélation", "learned": "révélation",
    "exposes": "révélation", "exposed": "révélation", "realizes": "révélation",
    "realizing": "révélation",
    # flashback
    "flashback": "flashback", "flashbacks": "flashback", "recalls": "flashback",
    "recalled": "flashback", "remembers": "flashback", "remembered": "flashback",
    "memory": "flashback", "memories": "flashback",
    # alliance
    "ally": "alliance", "allies": "alliance", "allied": "alliance",
    "alliance": "alliance", "teams up": "alliance", "join forces": "alliance",
    "joins forces": "alliance",
    # trahison
    "betray": "trahison", "betrays": "trahison", "betrayed": "trahison",
    "betrayal": "trahison", "double-cross": "trahison",
    # mort
    "dies": "mort", "die": "mort", "died": "mort", "death": "mort",
    "killed": "mort", "kills": "mort", "kill": "mort", "perishes": "mort",
    "perished": "mort", "slain": "mort",
    # capture
    "capture": "capture", "captures": "capture", "captured": "capture",
    "captive": "capture", "imprisoned": "capture", "imprison": "capture",
    "seized": "capture", "caught": "capture",
    # évasion
    "escape": "évasion", "escapes": "évasion", "escaped": "évasion",
    "flee": "évasion", "flees": "évasion", "fled": "évasion",
    "breaks free": "évasion", "break free": "évasion", "breakout": "évasion",
    # éveil de pouvoir
    "awaken": "éveil de pouvoir", "awakens": "éveil de pouvoir",
    "awakened": "éveil de pouvoir", "awakening": "éveil de pouvoir",
    "unlocks": "éveil de pouvoir", "unlocked": "éveil de pouvoir",
    "transforms": "éveil de pouvoir", "transformation": "éveil de pouvoir",
}

# Relations entre deux personnages : mot déclencheur -> tag canonique.
REL_LEXICON: dict[str, str] = {
    "ally": "alliance", "allies": "alliance", "allied": "alliance", "alliance": "alliance",
    "rival": "rivalité", "rivals": "rivalité", "rivalry": "rivalité",
    "enemy": "rivalité", "enemies": "rivalité", "nemesis": "rivalité", "foe": "rivalité",
    "brother": "filiation", "sister": "filiation", "father": "filiation",
    "mother": "filiation", "son": "filiation", "daughter": "filiation",
    "sibling": "filiation", "family": "filiation", "parent": "filiation",
    "friend": "amitié", "friends": "amitié", "friendship": "amitié", "comrade": "amitié",
    "betray": "trahison", "betrays": "trahison", "betrayed": "trahison", "betrayal": "trahison",
    "crew": "camaraderie", "crewmate": "camaraderie", "crewmember": "camaraderie",
    "marry": "mariage", "marriage": "mariage", "wed": "mariage",
    "mentor": "mentorat", "apprentice": "mentorat", "master": "mentorat",
    "disciple": "mentorat", "teacher": "mentorat", "student": "mentorat",
}

# Mots-clés déclenchant une détection d'objet (fruits, poneglyphes, armes, navires, trésors).
OBJECT_TRIGGERS: list[str] = [
    "devil fruit", "no mi", "poneglyph", "road poneglyph", "treasure",
    "sword", "blade", "saber", "katana", "cutlass", "cannon", "pistol",
    "gun", "rifle", "spear", "hammer", "staff", "whip", "claw", "dial",
    "log pose", "den den mushi", "ship", "vessel", "galleon", "brig",
    "submarine", "map", "vivre card", "eternal pose",
]

# Mots à ignorer en tête de séquence capitalisée (mode regex, perso/lieu).
STOPWORDS_LEADING = {
    "The", "A", "An", "His", "Her", "Their", "Its", "This", "That", "These",
    "Those", "He", "She", "They", "It", "As", "When", "While", "After",
    "Before", "Meanwhile", "However", "Chapter",
}

# Suffixes typiques d'un lieu, pour distinguer perso/lieu en mode regex.
PLACE_HINTS = {
    "island", "village", "kingdom", "sea", "ocean", "bay", "port", "archipelago",
    "town", "city", "country", "empire", "forest", "mountain", "grove", "cape",
    "kuri", "paradise", "blue", "line", "land", "isle", "harbor", "harbour",
}

# Séquence de mots capitalisés (avec particules "no"/"de"/"the" possibles au
# milieu, pour capter des noms comme "Gomu Gomu no Mi" ou "Going Merry").
PROPER_NOUN_RE = re.compile(
    r"\b[A-Z][a-zA-Z'\-]+(?:\s+(?:no|de|the|of)\s+[A-Z][a-zA-Z'\-]+"
    r"|\s+[A-Z][a-zA-Z'\-]+)*\b"
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Candidate:
    category_guess: str
    raw_term: str
    context_snippet: str


def load_nlp():
    """Charge un modèle spaCy anglais si possible. Retourne (nlp, mode)."""
    try:
        import spacy
    except ImportError:
        print("[extraction] spaCy indisponible -> mode regex de repli.")
        return None, "regex"

    for model_name in ("en_core_web_md", "en_core_web_sm"):
        try:
            nlp = spacy.load(model_name)
            print(f"[extraction] mode spaCy ({model_name}).")
            return nlp, f"spacy:{model_name}"
        except OSError:
            continue

    print("[extraction] aucun modèle spaCy installé -> mode regex de repli.")
    return None, "regex"


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _is_valid_proper_noun(term: str) -> bool:
    """Écarte les faux positifs : mot de tête générique (début de phrase) ou trop court."""
    words = term.split()
    return len(term) >= 3 and bool(words) and words[0] not in STOPWORDS_LEADING


def _nearest_proper_noun(sentence: str, start: int, end: int) -> str | None:
    """Cherche la séquence capitalisée la plus proche d'un déclencheur (avant, sinon après)."""
    before_matches = [
        m for m in PROPER_NOUN_RE.finditer(sentence[:start]) if _is_valid_proper_noun(m.group(0))
    ]
    if before_matches:
        return before_matches[-1].group(0).strip()
    after_match = PROPER_NOUN_RE.search(sentence[end:])
    if after_match and _is_valid_proper_noun(after_match.group(0)):
        return after_match.group(0).strip()
    return None


def _find_object_candidates(sentence: str) -> list[Candidate]:
    """Détecte les objets par mots déclencheurs, indépendamment de spaCy."""
    low = sentence.lower()
    found = []
    for trigger in OBJECT_TRIGGERS:
        idx = low.find(trigger)
        if idx == -1:
            continue
        raw_term = _nearest_proper_noun(sentence, idx, idx + len(trigger)) or trigger
        found.append(Candidate("objet", raw_term, sentence))
    return found


def _find_event_candidates(sentence: str, nlp_doc=None) -> list[Candidate]:
    """Détecte les événements narratifs par lemme (spaCy) ou mot-clé (regex)."""
    found = []
    if nlp_doc is not None:
        for token in nlp_doc:
            key = token.lemma_.lower()
            if key in EVENT_LEXICON:
                found.append(Candidate("event", EVENT_LEXICON[key], sentence))
    else:
        low = sentence.lower()
        for keyword, tag in EVENT_LEXICON.items():
            if re.search(rf"\b{re.escape(keyword)}\b", low):
                found.append(Candidate("event", tag, sentence))
    return found


def _find_rel_candidates(sentence: str, person_names: list[str]) -> list[Candidate]:
    """Détecte une relation si >=2 personnages + mot déclencheur dans la phrase."""
    if len(set(person_names)) < 2:
        return []
    low = sentence.lower()
    found = []
    for keyword, tag in REL_LEXICON.items():
        if re.search(rf"\b{re.escape(keyword)}\b", low):
            found.append(Candidate("rel", tag, sentence))
    return found


def _guess_place_or_person(term: str) -> str:
    """Heuristique perso/lieu en mode regex, à partir de mots-clés de lieu."""
    low = term.lower()
    if any(hint in low for hint in PLACE_HINTS):
        return "lieu"
    return "perso"


class PersonLookup:
    """Ensemble de noms de personnages connus, pour corriger perso/lieu.

    En_core_web_sm n'a jamais vu de noms propres One Piece pendant son
    entraînement : il se rabat sur des heuristiques de forme (mot court,
    consonance japonaise -> GPE/LOC/FAC) qui étiquettent à tort en "lieu"
    des personnages comme "Zoro" ou "Katakuri" (leur nom complet,
    "Roronoa Zoro", "Charlotte Katakuri", est lui correctement reconnu comme
    PERSON — cf. faisabilite-etat-de-lart.md). On corrige donc après coup :
    toute entité taguée lieu qui correspond à un nom connu (entier ou un de
    ses mots, ex. "Zoro" dans "Roronoa Zoro") est recatégorisée en "perso".
    """

    def __init__(self, names: set[str] | None = None) -> None:
        self.full_names: set[str] = set()
        self.tokens: set[str] = set()
        if names:
            self.add_many(names)

    def add_many(self, names: set[str]) -> None:
        for name in names:
            low = name.strip().lower()
            if not low:
                continue
            self.full_names.add(low)
            self.tokens.update(low.split())

    def matches(self, term: str) -> bool:
        low = term.strip().lower()
        return low in self.full_names or low in self.tokens


def _extract_spacy(text: str, nlp, persons: PersonLookup | None = None) -> list[Candidate]:
    candidates: list[Candidate] = []
    doc = nlp(text)
    for sent in doc.sents:
        sentence = sent.text.strip()
        if not sentence:
            continue
        person_names = []
        for ent in sent.ents:
            if ent.label_ == "PERSON":
                candidates.append(Candidate("perso", ent.text, sentence))
                person_names.append(ent.text)
            elif ent.label_ in ("GPE", "LOC", "FAC"):
                if persons and persons.matches(ent.text):
                    candidates.append(Candidate("perso", ent.text, sentence))
                    person_names.append(ent.text)
                else:
                    candidates.append(Candidate("lieu", ent.text, sentence))
        candidates.extend(_find_object_candidates(sentence))
        candidates.extend(_find_event_candidates(sentence, nlp_doc=sent))
        candidates.extend(_find_rel_candidates(sentence, person_names))
    return candidates


def _extract_regex(text: str, persons: PersonLookup | None = None) -> list[Candidate]:
    candidates: list[Candidate] = []
    for sentence in _split_sentences(text):
        person_names = []
        for m in PROPER_NOUN_RE.finditer(sentence):
            term = m.group(0).strip()
            if not _is_valid_proper_noun(term):
                continue
            category = _guess_place_or_person(term)
            if category == "lieu" and persons and persons.matches(term):
                category = "perso"
            candidates.append(Candidate(category, term, sentence))
            if category == "perso":
                person_names.append(term)
        candidates.extend(_find_object_candidates(sentence))
        candidates.extend(_find_event_candidates(sentence, nlp_doc=None))
        candidates.extend(_find_rel_candidates(sentence, person_names))
    return candidates


def extract_candidates(
    text: str, nlp=None, persons: PersonLookup | None = None
) -> list[Candidate]:
    """Point d'entrée unique : extrait tous les candidats d'un texte libre.

    `nlp` est un modèle spaCy déjà chargé (ou None pour forcer le mode regex).
    `persons` est un `PersonLookup` optionnel de noms de personnages connus
    (ex. le front-matter du chapitre, ou la taxonomie déjà construite), pour
    corriger les entités "lieu" qui sont en réalité des personnages.
    """
    if not text or not text.strip():
        return []
    if nlp is not None:
        return _extract_spacy(text, nlp, persons=persons)
    return _extract_regex(text, persons=persons)

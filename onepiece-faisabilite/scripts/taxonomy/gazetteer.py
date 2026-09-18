"""Résolution de noms canoniques via les redirections du wiki Fandom One Piece.

Le clustering par embedding sémantique (cf. 03_cluster_taxonomy.py) chaîne à
tort des noms propres One Piece qui n'ont rien à voir entre eux : le modèle
d'embedding, hors-vocabulaire sur ces noms, capture une ressemblance de
surface/phonétique et non leur sens (ex. "Onigashima"/"Earth" ont une
similarité cosinus de 0.79 alors qu'ils sont sans rapport, quand "the Grand
Line"/"Laugh Tale" — fortement liés dans l'histoire — n'en ont que 0.21).
Aucun réglage de seuil ne corrige cet effet de chaînage.

Le wiki Fandom, lui, encode une vérité terrain gratuite et fiable, sur deux
plans :
  - chaque alias/surnom d'un personnage, lieu ou objet est une page de
    redirection vers sa page canonique (ex. "Zoro" -> "Roronoa Zoro") ;
  - chaque page appartient à des catégories (ex. "Category:Fighting Styles",
    "Category:Locations") qui disent son VRAI type, indépendamment de la
    catégorie devinée par spaCy à l'extraction (ex. "Kaido" est étiqueté
    "lieu" par en_core_web_sm alors que ses catégories wiki disent
    "Category:Humans" -> un personnage).

On interroge donc `action=query&redirects=1&prop=categories` (même API que
`onepiece_ingest.py`) pour résoudre chaque candidat vers son nom canonique et
son vrai type avant de clusteriser : le clustering par embedding ne sert plus
que de repli pour ce que le wiki ne couvre pas.

Certaines attaques nommées (ex. "Rotisserie Strike", un coup de Sanji) n'ont
même aucune page à elles : ni redirection ni catégorie ne peuvent alors les
trouver. `fetch_technique_names` mine le contenu des sous-pages de style de
combat du wiki (Category:Fighting Style Subpages, ex. "Black Leg
Style/Diable Jambe"), où ces attaques sont listées en tableau, pour les
rattraper malgré tout.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests

API = "https://onepiece.fandom.com/api.php"
UA = "OnePieceTagPrediction/0.1 (projet academique; contact: morotti.maxime@gmail.com)"
BATCH = 50  # limite MediaWiki pour un utilisateur anonyme (cf. onepiece_ingest.py)

# spaCy inclut parfois un article ("the Gasu Gasu no Mi") ou un possessif
# ("Dracule Mihawk's") dans le texte de l'entité qu'il extrait ; le titre wiki,
# lui, n'a ni l'un ni l'autre ("Gasu Gasu no Mi", "Dracule Mihawk"). Une
# requête sur la forme brute échoue alors silencieusement (page absente) et
# le terme retombe dans le clustering par embedding en repli, avec le même
# effet de chaînage qu'on cherche justement à éviter (ex. "Dracule Mihawk's"
# et "Monkey D. Dragon's" finissaient chaînés ensemble). On retente donc,
# pour ces formes, la résolution sur la variante sans article/possessif.
_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.I)
_TRAILING_POSSESSIVE_RE = re.compile(r"[’']s$")


def normalized_candidate(term: str) -> str | None:
    """Variante d'un terme sans article en tête ni possessif en fin, à
    retenter si la forme brute échoue. None si le terme n'a ni l'un ni l'autre.
    """
    normalized = _TRAILING_POSSESSIVE_RE.sub("", _LEADING_ARTICLE_RE.sub("", term)).strip()
    return normalized if normalized and normalized != term else None


@dataclass
class Resolution:
    canonical: str | None  # nom de page wiki, ou None si absent du wiki
    wiki_category: str | None  # type déduit des catégories wiki, ou None si indéterminé
    family: str | None = None  # catégorie de famille wiki (ex. "Shimotsuki Family"), ou None


# Mots-clés des catégories wiki (sans le préfixe "Category:") qui trahissent
# le vrai type d'une page, testés par ordre de priorité : la première règle
# dont un mot-clé apparaît (en mot entier) dans une des catégories l'emporte.
# "pouvoir" est un type absent de la taxonomie d'origine (techniques, styles
# de combat, Haki...) ; "groupe" aussi (équipages, organisations) : tous deux
# n'existaient pas avant que le wiki permette de les distinguer de perso/lieu.
# "objet" était un fourre-tout (fruits du démon, navires, épées, poneglyphes,
# trésors mélangés). Les sous-types ci-dessous ont été vérifiés par de vraies
# requêtes API (action=query&titles=...&prop=categories) sur des pages
# connues avant d'être codés, jamais devinés :
#   - fruit : "Gomu Gomu no Mi"/"Mera Mera no Mi"/"Yami Yami no Mi" portent
#     Paramecia/Zoan/Logia (jamais le libellé générique "Devil Fruits" lui-même) ;
#   - arme : "Wado Ichimonji"/"Enma"/"Kiribachi" portent Swords/Blades, "Art of
#     Weather/Clima-Tact" porte Polearms, "Usopp Tactics/Kabuto" porte
#     "Projectile Weapons" -> le mot "Weapons" seul couvre déjà ce dernier cas ;
#   - navire : "Going Merry"/"Thousand Sunny"/"Noah" portent toutes "...Ships" ;
#   - poneglyphe : il n'existe qu'UNE SEULE page pour le concept ("Poneglyph"),
#     tous les poneglyphes nommés (Rio, Road...) y redirigent. Sa catégorie
#     "Artifacts" est aussi celle d'objets sans rapport (One Piece le trésor,
#     Pluton, Noah, le chapeau de paille...), donc pas assez fine seule ; sa
#     catégorie "Literature" est, elle, partagée avec Newspaper/Logbook/Comic
#     Strips, pas assez fine non plus. Seule l'INTERSECTION des deux
#     catégories identifie spécifiquement Poneglyph parmi tout ce qui a été
#     vérifié par requête API -> règle "toutes ces catégories" (all_of), pas
#     "au moins une" (any_of) comme les autres règles.
# Le reste de "Artifacts" (trésors : One Piece, chapeau de paille, Tamatebako,
# Roulette...) retombe dans le "objet" générique, faute de catégorie wiki
# dédiée au trésor (Category:Treasures n'existe pas sur ce wiki).
_CATEGORY_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("pouvoir", ("Fighting Styles", "Rokushiki", "Named Techniques", "Named Attacks", "Techniques"), ()),
    ("fruit", ("Paramecia", "Zoan", "Logia", "Devil Fruits"), ()),
    ("arme", ("Weapons", "Swords", "Blades", "Polearms"), ()),
    ("navire", ("Ships", "Vessels"), ()),
    ("poneglyphe", (), ("Literature", "Artifacts")),
    ("objet", ("Artifacts", "Treasures"), ()),
    (
        "lieu",
        (
            "Locations", "Islands", "Oceans", "Seas", "Territories", "Countries", "Towns",
            "Cities", "Kingdoms", "Archipelagos", "Regions", "Villages",
        ),
        (),
    ),
    ("groupe", ("Crews", "Groups"), ()),
    ("perso", ("Characters", "Humans", "Users", "Residents", "Combatants"), ()),
]


def classify_categories(categories: list[str]) -> str | None:
    """Déduit le vrai type d'un terme à partir des catégories wiki de sa page.

    Une catégorie contenant le mot "Users" (ex. "Armament Haki Users",
    "Mythical Zoan Devil Fruit Users") désigne toujours un PERSONNAGE qui
    utilise X, jamais X lui-même : elle est donc ignorée pour les règles
    autres que "perso", sans quoi un personnage utilisateur d'un fruit Zoan
    serait classé "objet" à cause du seul mot "Zoan" (cas réel : Kaidou).

    Chaque règle teste soit "au moins un" de ses mots-clés (`any_of`), soit
    "tous" (`all_of`, ex. poneglyphe) : la première règle qui matche l'emporte.
    """
    names = [c.removeprefix("Category:") for c in categories]
    for tag, any_of, all_of in _CATEGORY_RULES:
        pool = names if tag == "perso" else [n for n in names if "Users" not in n]

        def _has(kw: str) -> bool:
            return any(re.search(rf"\b{re.escape(kw)}\b", name) for name in pool)

        if all_of and all(_has(kw) for kw in all_of):
            return tag
        if any_of and any(_has(kw) for kw in any_of):
            return tag
    return None


# Vérifié par de vraies requêtes API sur plusieurs personnages : Roronoa Zoro
# porte "Category:Shimotsuki Family", Sanji "Category:Vinsmoke Family", Luffy
# et Ace tous deux "Category:Dadan Family" (famille d'accueil, pas de sang,
# mais bien une vraie catégorie de famille partagée). Chaque catégorie de
# famille se nomme "Category:<Nom> Family" (singulier) ; les catégories méta
# au pluriel qui les regroupent ("Category:Families", "Category:Non-Canon
# Families"...) n'ont pas cet exact suffixe et sont donc naturellement
# exclues par le motif, sans liste d'exclusion à maintenir à la main.
_FAMILY_CATEGORY_RE = re.compile(r"^.+ Family$")


def extract_family(categories: list[str]) -> str | None:
    """Catégorie de famille wiki d'un personnage (ex. "Shimotsuki Family"), ou None.

    Sert à vérifier une relation de filiation entre deux personnages : s'ils
    partagent la même famille, la relation est réelle et pas seulement
    déduite d'un mot-clé ("father", "brother"...) trouvé près de leurs deux
    noms dans une phrase, sans savoir s'ils sont effectivement apparentés.
    """
    for c in categories:
        name = c.removeprefix("Category:")
        if _FAMILY_CATEGORY_RE.match(name):
            return name
    return None


# Une attaque nommée (ex. "Rotisserie Strike", un coup de Sanji) n'a souvent
# aucune page à elle : elle n'est listée que dans un tableau de sa sous-page
# de style de combat ("Black Leg Style/Diable Jambe"), sous
# Category:Fighting Style Subpages. Ni redirects=1 ni prop=categories ne
# peuvent la trouver puisqu'elle n'est tout simplement pas une page. On mine
# donc le contenu de ces sous-pages : chaque technique y est listée comme
# {{Nihongo|'''Nom'''|kanji|romaji|...}} (ou {{Nihongo2|...}}, même syntaxe).
_TECHNIQUE_SUBPAGES_CATEGORY = "Category:Fighting Style Subpages"
_TECHNIQUE_NAME_RE = re.compile(r"\{\{Nihongo2?\|'''([^']+)'''")


def fetch_technique_names(cache_path: Path, delay: float = 0.3) -> dict[str, str]:
    """{nom en minuscules: nom tel qu'affiché sur le wiki} pour toute
    technique listée dans une sous-page de style de combat.

    Persisté sur disque comme le reste du gazetteer : régénéré seulement si
    le cache est absent (les sous-pages listées changent rarement).
    """
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    session = requests.Session()
    session.headers["User-Agent"] = UA

    subpages: list[str] = []
    cmcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": _TECHNIQUE_SUBPAGES_CATEGORY,
            "cmlimit": "max",
            "format": "json",
            "formatversion": "2",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        r = session.get(API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        subpages.extend(m["title"] for m in data["query"]["categorymembers"])
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break

    names: dict[str, str] = {}
    for start in range(0, len(subpages), BATCH):
        batch = subpages[start : start + BATCH]
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        }
        r = session.get(API, params=params, timeout=30)
        r.raise_for_status()
        for page in r.json().get("query", {}).get("pages", []):
            for rev in page.get("revisions", []):
                content = rev["slots"]["main"]["content"]
                for name in _TECHNIQUE_NAME_RE.findall(content):
                    name = name.strip()
                    names.setdefault(name.lower(), name)
        if start + BATCH < len(subpages):
            time.sleep(delay)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(names, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return names


class WikiGazetteer:
    """Résout une liste de termes vers leur nom canonique de page wiki et leur type.

    Le cache est persisté sur disque (`cache_path`), au niveau des données
    brutes (canonique + catégories wiki), pas du type déduit : affiner
    `classify_categories` n'invalide donc pas le cache. Un terme déjà résolu
    (ou confirmé absent du wiki) lors d'un run précédent n'est jamais
    réinterrogé, ce qui garde les runs suivants rapides et épargne l'API.
    """

    def __init__(self, cache_path: Path, delay: float = 0.3):
        self.cache_path = cache_path
        self.delay = delay
        self.cache: dict[str, dict] = {}
        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            # Les entrées d'un ancien format de cache (terme -> str|null, avant
            # l'ajout des catégories) n'ont pas les données nécessaires : on
            # les laisse de côté, elles seront réinterrogées.
            self.cache = {k: v for k, v in raw.items() if isinstance(v, dict)}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _fetch_batch(self, titles: list[str]) -> dict[str, dict]:
        params = {
            "action": "query",
            "titles": "|".join(titles),
            "redirects": "1",
            "prop": "categories",
            "cllimit": "max",
            "clshow": "!hidden",
            "format": "json",
            "formatversion": "2",
        }
        data = None
        for attempt in range(4):
            try:
                r = self.session.get(API, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()["query"]
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    print(f"[gazetteer] échec définitif sur ce lot ({exc!r}), laissé non résolu.")
                    return {t: {"canonical": None, "categories": []} for t in titles}
                wait = 2 ** attempt
                print(f"[gazetteer] retry dans {wait}s ({exc})")
                time.sleep(wait)

        # Applique d'abord la normalisation MediaWiki (casse/espaces), puis la
        # redirection, dans l'ordre où l'API les documente.
        resolved = {t: t for t in titles}
        for entry in data.get("normalized", []):
            for t in resolved:
                if resolved[t] == entry["from"]:
                    resolved[t] = entry["to"]
        for entry in data.get("redirects", []):
            for t in resolved:
                if resolved[t] == entry["from"]:
                    resolved[t] = entry["to"]

        pages_by_title = {p["title"]: p for p in data.get("pages", [])}
        out: dict[str, dict] = {}
        for t in titles:
            page = pages_by_title.get(resolved[t])
            if page is None or page.get("missing"):
                out[t] = {"canonical": None, "categories": []}
            else:
                cats = [c["title"] for c in page.get("categories", [])]
                out[t] = {"canonical": resolved[t], "categories": cats}
        return out

    def resolve_many(self, terms: list[str]) -> dict[str, Resolution]:
        """Résout une liste de termes (avec cache). Ne réinterroge que les inconnus.

        Retourne {terme: Resolution}. `canonical` est None si le terme est
        absent du wiki (laissé au clustering par embedding en repli).
        `wiki_category` est None si les catégories de la page ne permettent
        pas de trancher (le category_guess d'origine est alors conservé). Les
        termes contenant "|" (séparateur de lot MediaWiki) sont ignorés sans
        requête.
        """
        unique = sorted({t for t in terms if t and t.strip() and "|" not in t})
        normalized_of = {t: normalized_candidate(t) for t in unique}

        query_targets = set(unique)
        query_targets.update(n for n in normalized_of.values() if n)
        to_query = sorted(t for t in query_targets if t not in self.cache)

        for start in range(0, len(to_query), BATCH):
            batch = to_query[start : start + BATCH]
            resolved = self._fetch_batch(batch)
            self.cache.update(resolved)
            if start + BATCH < len(to_query):
                time.sleep(self.delay)

        if to_query:
            self.save()

        result: dict[str, Resolution] = {}
        for t in unique:
            entry = self.cache.get(t, {"canonical": None, "categories": []})
            if not entry.get("canonical") and normalized_of.get(t):
                alt = self.cache.get(normalized_of[t])
                if alt and alt.get("canonical"):
                    entry = alt
            result[t] = Resolution(
                canonical=entry.get("canonical"),
                wiki_category=classify_categories(entry.get("categories", [])),
                family=extract_family(entry.get("categories", [])),
            )
        return result

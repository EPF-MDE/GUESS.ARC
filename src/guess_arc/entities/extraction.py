"""Extraction déterministe des Entities : bronze -> Scenes -> Mentions -> Registry(t).

Fonctions pures uniquement : aucune lecture ni écriture. Seul `extract_entities`
est public ; Scenes et Mentions restent internes.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

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
    redirection reste un Canonical name distinct de sa page cible, sauf si
    redirects la rattache à sa cible.

    common_words : mots en minuscules (pronoms, déterminants) ; un texte de lien
    qui commence par l'un d'eux n'est pas un Alias ("Their mother").
    characters, islands, devil_fruits : entrées brutes des datasets de reference/.
    Seuls leurs noms servent (Entity type) ; leurs attributs d'état (affiliation,
    status, bounty, current_ruler...) décrivent la fin de l'histoire et n'entrent
    jamais dans Registry(t) (ADR 0002).
    concepts : Canonical names des Concepts et des Titles, exclus de Registry(t),
    en plus de ceux que leurs catégories du wiki désignent (_excluded_by_category).
    disguises : Disguises confirmés à la main, avec leur chapitre de Revelation.
    wiki_categories : Canonical name -> catégories de sa page sur le wiki (cache).
    type_overrides : Canonical name -> Entity type, tenu à la main ; l'emporte
    sur les datasets et les catégories.
    redirects : titre d'une redirection du wiki -> Canonical name de sa page cible,
    tenu à la main ; le titre de la redirection devient un Alias de la cible.
    """
    common_words: frozenset[str] = frozenset()
    characters: tuple[dict, ...] = ()
    islands: tuple[dict, ...] = ()
    devil_fruits: tuple[dict, ...] = ()
    concepts: frozenset[str] = frozenset()
    wiki_categories: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    type_overrides: Mapping[str, str] = field(default_factory=dict)
    redirects: Mapping[str, str] = field(default_factory=dict)
    disguises: tuple[Disguise, ...] = ()


@dataclass(frozen=True)
class Disguise:
    """Disguise confirmé à la main : avant revelation, alias est une Entity à part
    entière ; à partir de revelation, il devient un Alias de canonical_name."""
    alias: str
    canonical_name: str
    revelation: int


@dataclass(frozen=True)
class RegistryRow:
    """État d'une Entity dans Registry(t) pour valid_from <= t <= valid_to.

    valid_to à None : l'état vaut encore au dernier chapitre extrait.
    catalog : titre de la page catalogue du wiki dont l'Entity est une entrée
    ("Animal Species" pour Bananawani), None sinon ; fixe pour toute l'histoire.
    aliases : Aliases déjà utilisés au chapitre valid_from, triés (ADR 0002).
    """
    canonical_name: str
    entity_type: str
    catalog: str | None
    aliases: tuple[str, ...]
    valid_from: int
    valid_to: int | None
    first_chapter_seen: int
    last_chapter_seen: int
    mention_count: int


@dataclass(frozen=True)
class SuspiciousAlias:
    """Forme de surface dont les Alias matches tombent sur un Character hors du Cast."""
    alias: str
    canonical_name: str
    matches: int
    outside_cast: int


@dataclass(frozen=True)
class TopEntity:
    canonical_name: str
    entity_type: str
    mention_count: int


@dataclass(frozen=True)
class ExcludedName:
    canonical_name: str
    categories: list[str]


@dataclass(frozen=True)
class UnknownEntity:
    canonical_name: str
    mention_count: int


@dataclass(frozen=True)
class QualityReport:
    """recall_proxy : part des Characters ayant une Appearance dans la CharTable
    qui ont aussi au moins une Mention dans le Long Summary du même chapitre
    (None sans aucune Appearance). Ratio global, et par arc.

    precision_proxy : part des Mentions par Alias match de Characters dont le
    Character est dans le Cast du chapitre (Appearance, Recall ou Cover appearance).
    suspicious_aliases : les 20 formes qui tombent le plus souvent hors du Cast.
    unknown_mention_share : part des Mentions dont l'Entity est typée Unknown.
    excluded_by_category : nombre de Canonical names rencontrés dans le corpus et
    écartés de Registry(t) par leurs catégories du wiki (Titles et Concepts).
    excluded_by_category_names : ces mêmes noms, triés, avec les catégories du wiki
    qui ont décidé de leur exclusion, à relire (override, concepts.txt, redirects).
    unknown_entities : toutes les Entities typées Unknown, des plus mentionnées aux
    moins mentionnées, à typer à la main ou à écarter.
    top_entities : les 50 Entities les plus mentionnées, avec leur type, pour une
    vérification manuelle rapide.
    """
    scenes_per_chapter: dict[int, int]
    recall_proxy: float | None
    recall_proxy_per_arc: dict[str, float]
    mentions_by_source: dict[str, int]
    precision_proxy: float | None
    suspicious_aliases: list[SuspiciousAlias]
    unknown_mention_share: float | None
    top_entities: list[TopEntity]
    excluded_by_category: int
    excluded_by_category_names: list[ExcludedName]
    unknown_entities: list[UnknownEntity]


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
class Scene:
    """Scene numérotée d'un chapitre, à partir de 1 dans l'ordre du Long Summary."""
    number: int
    text: str


@dataclass(frozen=True)
class Participant:
    """Entity autorisée comme Participant d'un Event au chapitre t, avec son état
    dans Registry(t) : un Disguise non encore révélé est un Participant à part."""
    canonical_name: str
    entity_type: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ChapterContext:
    """Tout ce que l'extracteur d'Events sait du chapitre t.

    participants : Entities ayant au moins une Mention dans le chapitre, plus
    les Characters de son Cast, triés par Canonical name.
    """
    chapter: int
    scenes: tuple[Scene, ...]
    participants: tuple[Participant, ...]


@dataclass(frozen=True)
class Extraction:
    registry: list[RegistryRow]
    quality: QualityReport
    disguise_candidates: list[DisguiseCandidate]
    chapter_contexts: dict[int, ChapterContext] = field(default_factory=dict)
    # Pages parentes, sous-pages liées et entrées de catalogue dont les catégories
    # du wiki manquent au cache : à demander au wiki, puis à extraire de nouveau.
    pages_without_categories: frozenset[str] = frozenset()

    def chapter_context(self, t: int) -> ChapterContext:
        return self.chapter_contexts[t]

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
    """source : "link" (lien du wiki) ou "alias_match" (occurrence non liée).
    alias : Alias fourni par un lien pipé ; surface : texte trouvé par Alias match."""
    canonical_name: str
    chapter: int
    alias: str | None
    source: str = "link"
    surface: str | None = None
    catalog: str | None = None


@dataclass(frozen=True)
class _CastEntry:
    """Présence d'un Character (Appearance, Recall ou Cover appearance) ou d'un
    Group (en-tête de faction lié) dans la CharTable d'un chapitre. Pas une Mention."""
    canonical_name: str
    chapter: int
    appearance: bool
    group: bool = False
    alias: str | None = None  # texte affiché ('*[[Denjiro|Kyoshiro]]' -> Kyoshiro)
    catalog: str | None = None


def _page_title(title: str) -> str:
    """Titre tel que le wiki le lit : '_' vaut une espace, première lettre en capitale
    ([[pirate]] -> Pirate)."""
    title = title.replace("_", " ").strip()
    return title[:1].upper() + title[1:]


def _canonical_name(target: str) -> str | None:
    """Cible d'un lien -> titre de la page parente, ou None hors articles."""
    # Préfixe de namespace ou d'interwiki seulement : 'Ryu Ryu no Mi, Model: X'
    # est un article dont le titre contient un ':'.
    prefix = target.lstrip(":").split(":", 1)[0].strip().lower()
    if ":" in target and prefix in NON_ARTICLE_PREFIXES:
        return None
    # [[Page#Section]] et [[Page/Sous-page]] mènent à la page parente.
    title = _page_title(target.split("#", 1)[0].split("/", 1)[0])
    return title or None  # [[#Section]] : ancre dans la page courante


@dataclass(frozen=True)
class _Target:
    """Entity désignée par un lien. own : le lien nomme l'Entity elle-même, pas une
    de ses parties, donc son texte peut en être un Alias. catalog : page catalogue
    dont l'Entity est une entrée."""
    canonical_name: str
    own: bool
    catalog: str | None = None


# Catégorie du wiki des pages qui listent des choses distinctes, une par section
# (Animal Species, Foods). Les redirections vers une de ces sections (News Coo)
# en héritent aussi.
LISTS_CATEGORY = "Lists"


def _parts_of_pages(chapters: list[dict]) -> tuple[frozenset[str], frozenset[str]]:
    """Liens vers une partie de page -> (pages parentes, sous-pages liées).

    Leurs catégories du wiki décident d'un catalogue (parente) ou d'une chose à
    part (sous-page) : ce sont les pages dont _link_target a besoin.
    """
    parents, subpages = set(), set()
    for rec in chapters:
        for m in LINK_RE.finditer(rec["wikitext"]):
            parent = _canonical_name(m.group(1))
            page_part, has_section, _ = m.group(1).partition("#")
            page = _page_title(page_part)
            if parent is None or (page == parent and not has_section):
                continue
            parents.add(parent)
            if page != parent:
                subpages.add(page)
    return frozenset(parents), frozenset(subpages)


def _catalogs(parents: frozenset[str],
              wiki_categories: Mapping[str, tuple[str, ...]]) -> frozenset[str]:
    """Pages catalogues : rangées dans Lists et liées au moins une fois vers une
    section ou une sous-page. Une redirection vers une entrée (News Coo) porte les
    mêmes catégories mais n'est jamais liée ainsi : elle reste l'entrée elle-même.
    Lu sur tout le corpus : c'est un fait de structure du wiki, pas de l'histoire."""
    return frozenset(p for p in parents if LISTS_CATEGORY in wiki_categories.get(p, ()))


def _is_catalog_entry(categories: tuple[str, ...]) -> bool:
    """Un nom de section est une entrée s'il n'a pas de page sur le wiki, ou si sa
    page redirige dans le catalogue (Lists, ou "Animal Species Subpages" pour une
    sous-page). Sinon la section porte le titre d'une page à part : un intertitre
    (#Arabasta, les animaux d'Arabasta) ou une homonyme (#Candy, pas le Character
    Candy). Le lien ne désigne alors aucune Entity sûre : pas de fusion."""
    return (not categories or LISTS_CATEGORY in categories
            or any(c.endswith("Subpages") for c in categories))


def _link_target(target: str, wiki_categories: Mapping[str, tuple[str, ...]],
                 catalogs: frozenset[str]) -> _Target | None:
    """Cible d'un lien -> Entity désignée, ou None si le lien n'en désigne aucune.

    Un lien vers une section d'un catalogue (sur sa page ou une de ses sous-pages)
    désigne l'entrée, nommée par la section comme les redirections du wiki
    ([[Animal Species/Arabasta Saga#Bananawani]] -> Bananawani) ; le catalogue
    lui-même n'est pas une Entity. Une sous-page dont les catégories du wiki
    donnent un Entity type est une chose à part (Vegapunk/Lilith) ; sinon une
    sous-page ou une section est une partie de sa page parente
    ([[Gomu Gomu no Mi/Gear 5 Techniques]]).
    """
    parent = _canonical_name(target)
    if parent is None:
        return None
    page_part, has_section, section_part = target.partition("#")
    if parent in catalogs:
        entry = section_part.replace("_", " ").strip()
        if not entry or not _is_catalog_entry(wiki_categories.get(entry, ())):
            return None
        return _Target(entry, own=True, catalog=parent)
    page = _page_title(page_part)
    if page != parent and _category_type(wiki_categories.get(page, ())) is not None:
        return _Target(page, own=not has_section)
    return _Target(parent, own=page == parent and not has_section)


Resolve = Callable[[str], "_Target | None"]


UNKNOWN = "Unknown"


def _dataset_names(raw: str) -> tuple[set[str], set[str]]:
    """Nom d'un dataset -> (noms principaux, épithète entre crochets).

    "Edward Newgate [Whitebeard]" -> ({"Edward Newgate"}, {"Whitebeard"})
    "Bentham (Bon Clay) [Mr. 2]"  -> ({"Bentham (Bon Clay)", "Bentham"}, {"Mr. 2"})
    " Ope Ope no Mi (Awakened)"   -> ({"Ope Ope no Mi (Awakened)", "Ope Ope no Mi"}, set())
    """
    name = raw.strip()
    bracket = re.search(r"\s*\[([^\]]*)\]\s*$", name)
    if bracket:
        name = name[:bracket.start()].strip()
    names = {name, re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()}
    return names - {""}, ({bracket.group(1).strip()} - {""}) if bracket else set()


def _lexicon(reference: Reference) -> tuple[dict[str, str], dict[str, str]]:
    """Datasets -> (Canonical name -> Entity type, nom anglais -> Canonical name).

    Un nom présent dans deux datasets avec deux types différents ("Sphinx",
    Character et île) reste Unknown. L'épithète entre crochets d'un Character
    ("Scien [Queen]") ne sert que si aucun dataset n'a ce nom en principal.
    """
    primary: dict[str, set[str]] = {}
    epithets: dict[str, set[str]] = {}
    resolve: dict[str, str] = {}
    for entity_type, entries in (("Character", reference.characters),
                                 ("Place", reference.islands),
                                 ("Devil Fruit", reference.devil_fruits)):
        for entry in entries:
            names, bracketed = _dataset_names(entry["name"])
            for name in names:
                primary.setdefault(name, set()).add(entity_type)
            for name in bracketed:
                epithets.setdefault(name, set()).add(entity_type)
            # Un Devil Fruit est aussi désigné par son nom anglais (Chop-Chop Fruit).
            english = (entry.get("english") or "").strip()
            if entity_type == "Devil Fruit" and english:
                resolve[english] = min(names, key=len)
    types = {n: ts.pop() for n, ts in epithets.items() if len(ts) == 1 and n not in primary}
    types.update({n: ts.pop() for n, ts in primary.items() if len(ts) == 1})
    return types, resolve


ENTITY_TYPES = frozenset({"Character", "Group", "Place", "Ship", "Devil Fruit", "Weapon",
                          "Object", UNKNOWN})
# Catégories du wiki -> Entity type, dans l'ordre de priorité : une page porte
# souvent plusieurs catégories, la première règle qui en reconnaît une l'emporte.
# - Devil Fruit avant Character : "Devil Fruits with Multiple Users" (Gomu Gomu no Mi).
# - Place avant Group : un pays est aussi un régime (Wano Country : Locations, Regimes).
# - Character avant Group : une personne appartient à des groupes, l'inverse est rare.
# Les catégories de notions (Fighting Styles, Races and Tribes, Events) ne donnent
# aucun type : l'Entity reste Unknown.
CATEGORY_RULES = (
    ("Devil Fruit", re.compile(
        r"^(Paramecia|Zoan|Logia|Mythical Zoan|Ancient Zoan|Shown Devil Fruits)$|\bDevil Fruits\b")),
    ("Ship", re.compile(r"\bShips\b")),
    ("Weapon", re.compile(r"\b(Swords|Blades|Weapons|Polearms|Guns)\b")),
    ("Place", re.compile(
        r"(Locations|Islands|Kingdoms|Towns and Cities|Villages|Landmarks|Buildings|Castles"
        r"|Prisons|Oceans|Bases|Bars and Restaurants|Seas|Territories|Regions)$")),
    ("Character", re.compile(
        r"Characters$|^Characters Aged|^Humans$|Users$|Swordsmen$|^Talking Animals$|^Children$"
        r"|(Captains|Officers|Ministers|Prisoners|Slaves|Residents|Cooks|Staff|Antagonists"
        r"|Hybrids)$")),
    ("Group", re.compile(
        r"(Groups|Crews|Fleets|Families|Regimes|Organizations|Alliance|Military Forces)$")),
    ("Object", re.compile(
        r"(Technology|Artifacts|Literature|Substances|Minerals|Animal Species|Vehicles"
        r"|Sea Trains|By-Products|Plants|Creations)$")),
)


# Catégories du wiki des pages de rangs, de titres (Rear Admiral, Shogun) et de
# métiers génériques (Cook, Bounty Hunter) : un Title ou un Concept, jamais une Entity.
TITLE_CATEGORIES = frozenset({"Positions", "Occupations"})
# Catégorie du wiki des termes de l'univers (Jolly Roger, Epithet, Map, Sky Island) :
# un Concept, sauf quand une autre catégorie en fait un Group (Worst Generation).
TERMS_CATEGORY = "Terms"


def _category_type(categories: tuple[str, ...]) -> str | None:
    for entity_type, rule in CATEGORY_RULES:
        if any(rule.search(c) for c in categories):
            return entity_type
    return None


def _excluded_by_category(categories: tuple[str, ...]) -> bool:
    """Title ou Concept d'après les catégories du wiki de sa page."""
    if TITLE_CATEGORIES.intersection(categories):
        return True
    return TERMS_CATEGORY in categories and _category_type(categories) != "Group"


def _entity_types(names: set[str], dataset_types: dict[str, str], reference: Reference,
                  entry_catalogs: Mapping[str, str]) -> dict[str, str]:
    """Un seul type par Entity : override > datasets > catégories du wiki >
    catégories de son catalogue > Unknown."""
    bad = {n: t for n, t in reference.type_overrides.items() if t not in ENTITY_TYPES}
    if bad:
        raise ValueError(f"Entity type inconnu dans les overrides : {bad}")
    types = {}
    for name in names:
        catalog = entry_catalogs.get(name)
        types[name] = (
            reference.type_overrides.get(name)
            or dataset_types.get(name)
            or _category_type(reference.wiki_categories.get(name, ()))
            or (catalog and _category_type(reference.wiki_categories.get(catalog, ())))
            or UNKNOWN
        )
    return types


def _alias(target: _Target, text: str | None, common_words: frozenset[str]) -> str | None:
    """Texte d'un lien pipé -> Alias de l'Entity, s'il ressemble à un nom."""
    # Le texte d'un lien vers une partie de page ("Gear 5") nomme cette partie,
    # pas l'Entity parente.
    if text is None or not target.own:
        return None
    canonical_name = target.canonical_name
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


def _mentions(scene: _Scene, resolve: Resolve, common_words: frozenset[str]) -> list[_Mention]:
    # Le lien reste une Mention même quand son texte n'est pas un Alias.
    return [
        _Mention(target.canonical_name, scene.chapter, _alias(target, m.group(2), common_words),
                 catalog=target.catalog)
        for m in LINK_RE.finditer(scene.wikitext)
        if (target := resolve(m.group(1))) is not None
    ]


def _cast(chapter: int, char_section: str, resolve: Resolve) -> list[_CastEntry]:
    """CharTable -> Characters présents et Groups des en-têtes liés."""
    entries = []
    for c in parse_characters(char_section):
        target = resolve(c["name"])
        annotations = " ".join(c["annotations"])
        # Une présence "mentioned" ou "dream" n'est ni une Appearance, ni un
        # Recall, ni une Cover appearance.
        if target is not None and (c["on_panel"] or "flashback" in annotations
                                   or "cover" in annotations):
            alias = _alias(target, c["label"], frozenset())
            entries.append(_CastEntry(target.canonical_name, chapter, appearance=c["on_panel"],
                                      alias=alias, catalog=target.catalog))
    entries += [
        _CastEntry(target.canonical_name, chapter, appearance=False, group=True,
                   catalog=target.catalog)
        for group in parse_groups(char_section)
        if (target := resolve(group)) is not None
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


def _alias_first_use(mentions: list[_Mention]) -> dict[str, dict[str, int]]:
    """Canonical name -> {Alias: chapitre de sa première utilisation}."""
    first_use: dict[str, dict[str, int]] = {}
    for m in mentions:
        if m.alias is not None:
            per_alias = first_use.setdefault(m.canonical_name, {})
            per_alias[m.alias] = min(per_alias.get(m.alias, m.chapter), m.chapter)
    return first_use


def _alias_matches(chapter: int, scenes: list[_Scene], linked: list[_Mention],
                   alias_first_use: dict[str, dict[str, int]]) -> list[_Mention]:
    """Occurrences non liées des Entities liées dans ce chapitre.

    Le wiki ne lie une Entity qu'à sa première occurrence dans la page. On cherche
    donc, sensible à la casse, le Canonical name et les Aliases déjà datés au
    chapitre (ADR 0002) de chaque Entity liée dans le même chapitre.
    """
    owners: dict[str, set[str]] = {}
    for name in {m.canonical_name for m in linked}:
        dated = [a for a, first in alias_first_use.get(name, {}).items() if first <= chapter]
        for form in [name, *dated]:
            owners.setdefault(form, set()).add(name)
    # Une forme partagée par deux Entities liées ("Lucy") ne désigne personne de sûr.
    forms = {form: names.pop() for form, names in owners.items() if len(names) == 1}
    if not forms:
        return []
    # Formes longues d'abord : "Monkey D. Luffy" avant "Luffy".
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(forms, key=len, reverse=True))) + r")(?!\w)"
    )
    matches = []
    for scene in scenes:
        # Les liens sont déjà des Mentions : on les blanchit, longueur conservée.
        text = LINK_RE.sub(lambda m: " " * len(m.group(0)), scene.wikitext).replace("’", "'")
        matches += [
            _Mention(forms[m.group(0)], chapter, alias=None, source="alias_match",
                     surface=m.group(0))
            for m in pattern.finditer(text)
        ]
    return matches


def _precision_proxy(mentions: list[_Mention], cast: list[_CastEntry]
                     ) -> tuple[float | None, list[SuspiciousAlias]]:
    characters = {e.canonical_name for e in cast if not e.group}
    in_cast = {(e.canonical_name, e.chapter) for e in cast if not e.group}
    per_form: dict[tuple[str, str], list[bool]] = {}
    for m in mentions:
        if m.source == "alias_match" and m.canonical_name in characters:
            per_form.setdefault((m.surface, m.canonical_name), []).append(
                (m.canonical_name, m.chapter) in in_cast
            )
    every = [hit for hits in per_form.values() for hit in hits]
    precision = sum(every) / len(every) if every else None
    suspicious = [
        SuspiciousAlias(form, name, len(hits), hits.count(False))
        for (form, name), hits in per_form.items() if not all(hits)
    ]
    suspicious.sort(key=lambda s: (-s.outside_cast, -s.outside_cast / s.matches, s.alias))
    return precision, suspicious[:20]


def _registry(mentions: list[_Mention], cast: list[_CastEntry],
              alias_first_use: dict[str, dict[str, int]], types: dict[str, str],
              catalogs: Mapping[str, str], disguises: tuple[Disguise, ...]) -> list[RegistryRow]:
    # Une ligne par Entity et par chapitre où son état change : chapitre où elle
    # est vue (Mention ou CharTable), et Revelation d'un de ses Disguises.
    counts: dict[str, dict[int, int]] = {}
    for m in mentions:
        per_chapter = counts.setdefault(m.canonical_name, {})
        per_chapter[m.chapter] = per_chapter.get(m.chapter, 0) + 1
    for e in cast:
        counts.setdefault(e.canonical_name, {}).setdefault(e.chapter, 0)

    # À sa Revelation, un Disguise s'arrête et rejoint son Canonical name :
    # Mentions et chapitres vus du Disguise s'ajoutent alors à l'Entity.
    ends = {d.alias: d.revelation - 1 for d in disguises}
    merges: dict[str, dict[int, dict[int, int]]] = {}
    for d in disguises:
        # Plusieurs Disguises peuvent rejoindre la même Entity au même chapitre.
        at_revelation = merges.setdefault(d.canonical_name, {}).setdefault(d.revelation, {})
        for ch, n in counts.get(d.alias, {}).items():
            at_revelation[ch] = at_revelation.get(ch, 0) + n
    merges = {name: {r: c for r, c in by_r.items() if c} for name, by_r in merges.items()}

    rows = []
    for name in sorted(set(counts) | set(merges)):
        own = counts.get(name, {})
        merged = merges.get(name, {})
        steps = sorted(set(own) | set(merged))
        total, first, last = 0, None, None
        for i, ch in enumerate(steps):
            seen = [ch] if ch in own else []
            total += own.get(ch, 0)
            if ch in merged:
                total += sum(merged[ch].values())
                seen += list(merged[ch])
            first = min(seen) if first is None else min(first, *seen)
            last = max(seen) if last is None else max(last, *seen)
            rows.append(RegistryRow(
                canonical_name=name,
                # Un seul type, fixe pour toute l'histoire (ADR 0002).
                entity_type=types.get(name, UNKNOWN),
                catalog=catalogs.get(name),
                # Un Alias commence toujours sur une ligne : sa première utilisation
                # est une Mention, ou la Revelation pour un Disguise.
                aliases=tuple(sorted(a for a, f in alias_first_use.get(name, {}).items()
                                     if f <= ch)),
                valid_from=ch,
                valid_to=steps[i + 1] - 1 if i + 1 < len(steps) else ends.get(name),
                first_chapter_seen=first,
                last_chapter_seen=last,
                mention_count=total,
            ))
    return rows


def _name_tokens(name: str) -> set[str]:
    return set(re.findall(r"\w+", name.lower()))


def _disguise_candidates(chapters: list[dict], resolve: Resolve,
                         common_words: frozenset[str]) -> list[DisguiseCandidate]:
    """Aliases sans aucun mot commun avec leur Canonical name, Characters seulement.

    Liste de relecture hors ligne, pas Registry(t) : elle lit tout le corpus d'un
    coup, d'où un Character reconnu à sa présence dans n'importe quelle CharTable.
    """
    characters: set[str] = set()
    link_chapters: dict[tuple[str, str], list[int]] = {}
    for rec in chapters:
        wikitext = rec["wikitext"]
        characters |= {
            target.canonical_name for c in parse_characters(section(wikitext, "Characters"))
            if (target := resolve(c["name"])) is not None
        }
        for heading in DISGUISE_SECTIONS:
            for m in LINK_RE.finditer(section(wikitext, heading)):
                target = resolve(m.group(1))
                if target is None:
                    continue
                name = target.canonical_name
                alias = _alias(target, m.group(2), common_words)
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


# Liens qui ne s'affichent pas comme du texte dans la page.
HIDDEN_LINK_PREFIXES = {"file", "image", "category"}
# Notes de bas de page : elles citent souvent des volumes ou des SBS postérieurs
# au chapitre (ADR 0002).
REF_RE = re.compile(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>", re.I | re.S)
HTML_TAG_RE = re.compile(r"</?[a-z][^>]*>", re.I)
BERRY_RE = re.compile(r"\{\{\s*[Bb]\s*\}\}")
# Modèles sans paramètre restants : mise en page ({{-}}), rien à lire.
BARE_TEMPLATE_RE = re.compile(r"\{\{[^{}|]*\}\}")


def _rendered_text(wikitext: str) -> str:
    """Wikitexte d'une Scene -> texte lu par le lecteur : chaque lien devient son
    texte affiché, sans sa cible ; images, catégories, notes, balises HTML et
    modèles de mise en page disparaissent, {{B}} devient le symbole du Berry."""
    wikitext = REF_RE.sub("", wikitext)
    wikitext = BARE_TEMPLATE_RE.sub("", BERRY_RE.sub("฿", wikitext))
    wikitext = HTML_TAG_RE.sub("", wikitext)

    def render(m: re.Match) -> str:
        target, text = m.group(1), m.group(2)
        if target.lstrip(":").split(":", 1)[0].strip().lower() in HIDDEN_LINK_PREFIXES:
            return ""
        return target if text is None else text

    # Une légende d'image peut contenir des liens : on rend de l'intérieur vers l'extérieur.
    while (rendered := LINK_RE.sub(render, wikitext)) != wikitext:
        wikitext = rendered
    # Une image ôtée en milieu de phrase laisse deux espaces.
    return re.sub(r"[ \t]{2,}", " ", WIKI_EMPHASIS_RE.sub("", wikitext)).strip()


def _chapter_contexts(scenes: dict[int, list[_Scene]], mentions: list[_Mention],
                      cast: list[_CastEntry], registry: list[RegistryRow]
                      ) -> dict[int, ChapterContext]:
    allowed: dict[int, set[str]] = {n: set() for n in scenes}
    for m in mentions:
        allowed[m.chapter].add(m.canonical_name)
    # Cast seulement : ni Recall, ni Cover appearance, ni en-tête de Group.
    for e in cast:
        if e.appearance:
            allowed[e.chapter].add(e.canonical_name)
    rows_by_name: dict[str, list[RegistryRow]] = {}
    for row in registry:
        rows_by_name.setdefault(row.canonical_name, []).append(row)

    def participant(name: str, t: int) -> Participant:
        row = next(r for r in rows_by_name[name]
                   if r.valid_from <= t and (r.valid_to is None or t <= r.valid_to))
        return Participant(row.canonical_name, row.entity_type, row.aliases)

    return {
        t: ChapterContext(
            chapter=t,
            scenes=tuple(Scene(i, _rendered_text(scene.wikitext))
                         for i, scene in enumerate(scenes[t], start=1)),
            participants=tuple(participant(name, t) for name in sorted(names)),
        )
        for t, names in allowed.items()
    }


def extract_entities(chapters: list[dict], reference: Reference) -> Extraction:
    """Bronze déjà en mémoire -> Registry(t) publiable + Disguise candidates à relire."""
    dataset_types, resolve = _lexicon(reference)

    parents, subpages = _parts_of_pages(chapters)
    catalogs = _catalogs(parents, reference.wiki_categories)

    def link_target(target: str) -> _Target | None:
        return _link_target(target, reference.wiki_categories, catalogs)

    excluded_by_category: set[str] = set()

    def keep(name: str) -> bool:
        # Concepts et Titles ne sont jamais des Entities : liste manuelle d'abord,
        # puis catégories du wiki, sauf si un override de type garde le nom.
        if name in reference.concepts:
            return False
        if (name not in reference.type_overrides
                and _excluded_by_category(reference.wiki_categories.get(name, ()))):
            excluded_by_category.add(name)
            return False
        return True

    def kept(item) -> bool:
        # Les entrées d'un catalogue exclu (Marine Ranks, un Title) le sont aussi.
        return keep(item.canonical_name) and (item.catalog is None or keep(item.catalog))

    revelations = {(d.canonical_name, d.alias): d.revelation for d in reference.disguises}

    def resolved(item):
        # [[Eleven Supernovas]] désigne la page Worst Generation : sans texte de
        # lien, le titre de la redirection est l'Alias employé.
        target = reference.redirects.get(item.canonical_name)
        if target is not None:
            item = dataclasses.replace(item, canonical_name=target,
                                       alias=item.alias or item.canonical_name)
        name = resolve.get(item.canonical_name)
        item = dataclasses.replace(item, canonical_name=name) if name else item
        # Avant sa Revelation, un lien [[Denjiro|Kyoshiro]] désigne Kyoshiro : le
        # lecteur ne sait pas encore que c'est Denjiro (ADR 0002).
        revelation = revelations.get((item.canonical_name, item.alias))
        if revelation is not None and item.chapter < revelation:
            item = dataclasses.replace(item, canonical_name=item.alias, alias=None)
        return item

    scenes_by_chapter = {}
    arcs = {}
    linked: dict[int, list[_Mention]] = {}
    cast = []
    for rec in sorted(chapters, key=lambda r: r["number"]):
        number, wikitext = rec["number"], rec["wikitext"]
        scenes = _scenes(number, section(wikitext, "Long Summary"))
        scenes_by_chapter[number] = scenes
        arc = ARC_RE.search(wikitext)
        arcs[number] = arc.group(1) if arc else "Unknown"
        linked[number] = [
            m for s in scenes for m in map(resolved, _mentions(s, link_target, reference.common_words))
            if kept(m)
        ]
        cast += [e for e in map(resolved, _cast(number, section(wikitext, "Characters"), link_target))
                 if kept(e)]

    # Les Aliases sont datés sur tous les liens avant de servir à l'Alias match.
    link_mentions = [m for ms in linked.values() for m in ms]
    alias_first_use = _alias_first_use(link_mentions)
    # Un Disguise devient un Alias de son Canonical name à sa Revelation.
    for d in reference.disguises:
        alias_first_use.setdefault(d.canonical_name, {})[d.alias] = d.revelation
    mentions = link_mentions + [
        m for number, scenes in scenes_by_chapter.items()
        for m in _alias_matches(number, scenes, linked[number], alias_first_use)
    ]

    # Une entrée prend le catalogue de ses liens (le premier par ordre alphabétique
    # si plusieurs catalogues la listent), et son type quand rien d'autre n'en donne.
    entry_catalogs: dict[str, str] = {}
    for item in [*link_mentions, *cast]:
        if item.catalog is not None:
            current = entry_catalogs.get(item.canonical_name, item.catalog)
            entry_catalogs[item.canonical_name] = min(current, item.catalog)
    types = _entity_types({m.canonical_name for m in mentions} | {e.canonical_name for e in cast},
                          dataset_types, reference, entry_catalogs)
    for d in reference.disguises:  # les Disguises ne concernent que des Characters
        if d.alias in types:
            types[d.alias] = "Character"
    mention_totals: dict[str, int] = {}
    for m in mentions:
        mention_totals[m.canonical_name] = mention_totals.get(m.canonical_name, 0) + 1
    top_entities = [
        TopEntity(name, types[name], count)
        for name, count in sorted(mention_totals.items(), key=lambda kv: (-kv[1], kv[0]))[:50]
    ]

    recall_proxy, recall_proxy_per_arc = _recall_proxy(cast, mentions, arcs)
    precision_proxy, suspicious_aliases = _precision_proxy(mentions, cast)
    registry = _registry(mentions, cast, alias_first_use, types, entry_catalogs,
                         reference.disguises)
    return Extraction(
        registry=registry,
        quality=QualityReport(
            scenes_per_chapter={n: len(s) for n, s in scenes_by_chapter.items()},
            recall_proxy=recall_proxy,
            recall_proxy_per_arc=recall_proxy_per_arc,
            mentions_by_source={
                source: sum(m.source == source for m in mentions)
                for source in ("link", "alias_match")
            },
            precision_proxy=precision_proxy,
            suspicious_aliases=suspicious_aliases,
            unknown_mention_share=(
                sum(types[m.canonical_name] == UNKNOWN for m in mentions) / len(mentions)
                if mentions else None
            ),
            top_entities=top_entities,
            excluded_by_category=len(excluded_by_category),
            excluded_by_category_names=[
                ExcludedName(name, list(reference.wiki_categories.get(name, ())))
                for name in sorted(excluded_by_category)
            ],
            unknown_entities=[
                UnknownEntity(name, mention_totals.get(name, 0))
                for name in sorted((n for n, t in types.items() if t == UNKNOWN),
                                   key=lambda n: (-mention_totals.get(n, 0), n))
            ],
        ),
        disguise_candidates=_disguise_candidates(chapters, link_target, reference.common_words),
        chapter_contexts=_chapter_contexts(scenes_by_chapter, mentions, cast, registry),
        pages_without_categories=(parents | subpages | set(entry_catalogs))
        - set(reference.wiki_categories),
    )

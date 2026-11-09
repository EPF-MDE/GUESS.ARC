"""Extraction déterministe des Entities : bronze -> Scenes -> Mentions -> Registry(t).

Fonctions pures uniquement : aucune lecture ni écriture. Seul `extract_entities`
est public ; Scenes et Mentions restent internes.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
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
    redirection reste un Canonical name distinct de sa page cible.

    common_words : mots en minuscules (pronoms, déterminants) ; un texte de lien
    qui commence par l'un d'eux n'est pas un Alias ("Their mother").
    characters, islands, devil_fruits : entrées brutes des datasets de reference/.
    Seuls leurs noms servent (Entity type) ; leurs attributs d'état (affiliation,
    status, bounty, current_ruler...) décrivent la fin de l'histoire et n'entrent
    jamais dans Registry(t) (ADR 0002).
    concepts : Canonical names des Concepts et des Titles, exclus de Registry(t).
    disguises : Disguises confirmés à la main, avec leur chapitre de Revelation.
    wiki_categories : Canonical name -> catégories de sa page sur le wiki (cache).
    type_overrides : Canonical name -> Entity type, tenu à la main ; l'emporte
    sur les datasets et les catégories.
    """
    common_words: frozenset[str] = frozenset()
    characters: tuple[dict, ...] = ()
    islands: tuple[dict, ...] = ()
    devil_fruits: tuple[dict, ...] = ()
    concepts: frozenset[str] = frozenset()
    wiki_categories: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    type_overrides: Mapping[str, str] = field(default_factory=dict)
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
    aliases : Aliases déjà utilisés au chapitre valid_from, triés (ADR 0002).
    """
    canonical_name: str
    entity_type: str
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
class QualityReport:
    """recall_proxy : part des Characters ayant une Appearance dans la CharTable
    qui ont aussi au moins une Mention dans le Long Summary du même chapitre
    (None sans aucune Appearance). Ratio global, et par arc.

    precision_proxy : part des Mentions par Alias match de Characters dont le
    Character est dans le Cast du chapitre (Appearance, Recall ou Cover appearance).
    suspicious_aliases : les 20 formes qui tombent le plus souvent hors du Cast.
    unknown_mention_share : part des Mentions dont l'Entity est typée Unknown.
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
    """source : "link" (lien du wiki) ou "alias_match" (occurrence non liée).
    alias : Alias fourni par un lien pipé ; surface : texte trouvé par Alias match."""
    canonical_name: str
    chapter: int
    alias: str | None
    source: str = "link"
    surface: str | None = None


@dataclass(frozen=True)
class _CastEntry:
    """Présence d'un Character (Appearance, Recall ou Cover appearance) ou d'un
    Group (en-tête de faction lié) dans la CharTable d'un chapitre. Pas une Mention."""
    canonical_name: str
    chapter: int
    appearance: bool
    group: bool = False
    alias: str | None = None  # texte affiché ('*[[Denjiro|Kyoshiro]]' -> Kyoshiro)


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


def _category_type(categories: tuple[str, ...]) -> str | None:
    for entity_type, rule in CATEGORY_RULES:
        if any(rule.search(c) for c in categories):
            return entity_type
    return None


def _entity_types(names: set[str], dataset_types: dict[str, str],
                  reference: Reference) -> dict[str, str]:
    """Un seul type par Entity : override > datasets > catégories du wiki > Unknown."""
    bad = {n: t for n, t in reference.type_overrides.items() if t not in ENTITY_TYPES}
    if bad:
        raise ValueError(f"Entity type inconnu dans les overrides : {bad}")
    types = {}
    for name in names:
        types[name] = (
            reference.type_overrides.get(name)
            or dataset_types.get(name)
            or _category_type(reference.wiki_categories.get(name, ()))
            or UNKNOWN
        )
    return types


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
            alias = _alias(c["name"], name, c["label"], frozenset())
            entries.append(_CastEntry(name, chapter, appearance=c["on_panel"], alias=alias))
    entries += [
        _CastEntry(name, chapter, appearance=False, group=True)
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
              disguises: tuple[Disguise, ...]) -> list[RegistryRow]:
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
    dataset_types, resolve = _lexicon(reference)

    def keep(name: str) -> bool:
        # Concepts et Titles ne sont jamais des Entities.
        return name not in reference.concepts

    revelations = {(d.canonical_name, d.alias): d.revelation for d in reference.disguises}

    def resolved(item):
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
            m for s in scenes for m in map(resolved, _mentions(s, reference.common_words))
            if keep(m.canonical_name)
        ]
        cast += [e for e in map(resolved, _cast(number, section(wikitext, "Characters")))
                 if keep(e.canonical_name)]

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

    types = _entity_types({m.canonical_name for m in mentions} | {e.canonical_name for e in cast},
                          dataset_types, reference)
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
    return Extraction(
        registry=_registry(mentions, cast, alias_first_use, types, reference.disguises),
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
        ),
        disguise_candidates=_disguise_candidates(chapters, reference.common_words),
    )

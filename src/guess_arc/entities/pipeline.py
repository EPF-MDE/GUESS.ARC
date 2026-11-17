"""
One Piece — extraction des Entities, du bronze à Registry(t) dans la gold.

Gold (data/gold/entities/) : registry.jsonl (une ligne par Entity et par changement, datée par
valid_from / valid_to), chapter_context.jsonl (une ligne par chapitre : Scenes
numérotées et Participants autorisés, pour l'extracteur d'Events),
registry_quality.json (rapport qualité) et disguise_candidates.csv (Disguises
possibles, à relire par un humain).

Usage :
    python -m guess_arc.entities
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
from dataclasses import asdict
from pathlib import Path

from guess_arc import paths
from guess_arc.ingestion.pipeline import load_bronze

from .extraction import (ChapterContext, Disguise, DisguiseCandidate, Extraction, Participant,
                         Reference, Scene, extract_entities)
from .wiki_categories import load_category_cache, update_category_cache


def write_gold(extraction: Extraction, gold_dir: Path) -> Path:
    gold_dir.mkdir(parents=True, exist_ok=True)
    registry_path = gold_dir / "registry.jsonl"
    with registry_path.open("w", encoding="utf-8") as fh:
        for row in sorted(extraction.registry, key=lambda r: (r.valid_from, r.canonical_name)):
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    with (gold_dir / CHAPTER_CONTEXT).open("w", encoding="utf-8") as fh:
        for t in sorted(extraction.chapter_contexts):
            fh.write(json.dumps(asdict(extraction.chapter_context(t)), ensure_ascii=False) + "\n")
    (gold_dir / "registry_quality.json").write_text(
        json.dumps(asdict(extraction.quality), indent=2), encoding="utf-8"
    )
    write_disguise_candidates(extraction, gold_dir / "disguise_candidates.csv")
    return registry_path


CHAPTER_CONTEXT = "chapter_context.jsonl"


def read_chapter_contexts(path: Path) -> dict[int, ChapterContext]:
    """chapter_context.jsonl -> contexte de chaque chapitre, sans relancer l'extraction."""
    contexts = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            contexts[row["chapter"]] = ChapterContext(
                chapter=row["chapter"],
                scenes=tuple(Scene(**s) for s in row["scenes"]),
                participants=tuple(
                    Participant(p["canonical_name"], p["entity_type"], tuple(p["aliases"]))
                    for p in row["participants"]
                ),
            )
    return contexts


def write_disguise_candidates(extraction: Extraction, path: Path) -> None:
    """Liste à relire : régénérée à chaque run, donc à ne pas éditer en place.
    Les Disguises confirmés sont recopiés ailleurs, avec leur Revelation (ENT-08)."""
    fields = [f.name for f in dataclasses.fields(DisguiseCandidate)]
    # utf-8-sig : le CSV s'ouvre avec les bons accents dans Excel.
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for candidate in extraction.disguise_candidates:
            writer.writerow(asdict(candidate))


COMMON_WORDS_PATH = Path(__file__).with_name("common_words.txt")


def _read_list(path: Path) -> list[str]:
    """Un élément par ligne ; lignes vides et commentaires (#) ignorés."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def load_common_words(path: Path = COMMON_WORDS_PATH) -> frozenset[str]:
    return frozenset(w.lower() for w in _read_list(path))


def load_reference(reference_dir: Path = paths.REFERENCE_DIR) -> Reference:
    """Tout ce qui vient de l'extérieur de la bronze, chargé une fois pour le seam."""
    def dataset(name: str) -> tuple[dict, ...]:
        return tuple(json.loads((reference_dir / f"{name}.json").read_text(encoding="utf-8")))

    overrides = {row["canonical_name"]: row["entity_type"]
                 for row in _read_csv(reference_dir / TYPE_OVERRIDES)}
    disguises = tuple(
        Disguise(row["alias"], row["canonical_name"], int(row["revelation"]))
        for row in _read_csv(reference_dir / DISGUISES)
    )
    return Reference(
        common_words=load_common_words(),
        characters=dataset("characters"),
        islands=dataset("islands"),
        devil_fruits=dataset("devil_fruits"),
        concepts=frozenset(_read_list(reference_dir / "concepts.txt")),
        wiki_categories=load_category_cache(reference_dir / WIKI_CATEGORIES),
        type_overrides=overrides,
        redirects={row["redirect"]: row["canonical_name"]
                   for row in _read_csv(reference_dir / REDIRECTS)},
        disguises=disguises,
    )


WIKI_CATEGORIES = "wiki_categories.json"
TYPE_OVERRIDES = "type_overrides.csv"
DISGUISES = "disguises.csv"
REDIRECTS = "redirects.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    """CSV avec en-tête ; lignes de commentaire (#) ignorées."""
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


def run(data_dir: Path = paths.DATA_DIR, fetch: bool = True) -> Extraction:
    archive = load_bronze(paths.bronze_dir(data_dir) / "chapters.jsonl")
    chapters = list(archive.values())
    extraction = extract_entities(chapters, load_reference())

    # Les catégories du wiki ne sont demandées que pour les Entities encore
    # Unknown et absentes du cache ; un second run ne touche pas au réseau.
    # Un Title nouveau sort Unknown de la première extraction, puis est exclu
    # par ses catégories dans la seconde, juste après la requête. Un nom typé par un dataset n'est jamais
    # demandé au wiki : un Title présent dans un dataset ne serait pas exclu
    # (aucun au 2026-11-10 ; à ajouter à concepts.txt le cas échéant).
    # S'y ajoutent les sous-pages liées, les pages parentes des liens vers une partie
    # de page et les entrées de catalogue : leurs catégories décident d'une chose à
    # part, d'un catalogue ou d'une section qui porte le titre d'une autre page.
    unknown = {r.canonical_name for r in extraction.registry if r.entity_type == "Unknown"}
    if fetch:
        fetched = update_category_cache(paths.REFERENCE_DIR / WIKI_CATEGORIES,
                                        unknown | extraction.pages_without_categories)
        if fetched:
            print(f"Catégories du wiki récupérées pour {fetched} pages")
            extraction = extract_entities(chapters, load_reference())
    registry_path = write_gold(extraction, paths.gold_dir(data_dir) / "entities")

    scenes = extraction.quality.scenes_per_chapter
    entities = {row.canonical_name for row in extraction.registry}
    print(f"Bronze : {len(archive)} chapitres, {sum(scenes.values())} Scenes")
    print(f"Gold   : {registry_path} ({len(entities)} Entities, {len(extraction.registry)} lignes)")
    if extraction.quality.recall_proxy is not None:
        print(f"Recall proxy : {extraction.quality.recall_proxy:.1%} des Appearances ont une Mention")
    by_source = extraction.quality.mentions_by_source
    print(f"Mentions : {by_source['link']} par lien, {by_source['alias_match']} par Alias match")
    if extraction.quality.precision_proxy is not None:
        print(f"Precision proxy : {extraction.quality.precision_proxy:.1%} des Alias matches "
              "de Characters tombent dans le Cast")
    if extraction.quality.unknown_mention_share is not None:
        print(f"Mentions typées Unknown : {extraction.quality.unknown_mention_share:.1%}")
    print(f"Titles et Concepts exclus par catégorie du wiki : "
          f"{extraction.quality.excluded_by_category}")
    print(f"Disguise candidates à relire : {len(extraction.disguise_candidates)}")
    empty = [n for n, count in scenes.items() if count == 0]
    if empty:
        print(f"Chapitres sans Scene : {empty}")
    return extraction


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches bronze/gold (défaut : data/ à la racine du repo)")
    p.add_argument("--offline", action="store_true",
                   help="ne demande pas au wiki les catégories absentes du cache")
    args = p.parse_args()
    run(args.data_dir, fetch=not args.offline)


if __name__ == "__main__":
    main()

"""
One Piece — extraction des Entities, du bronze à Registry(t) dans la gold.

Gold : registry.jsonl (une ligne par Entity et par changement, datée par
valid_from / valid_to), registry_quality.json (rapport qualité) et
disguise_candidates.csv (Disguises possibles, à relire par un humain).

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

from .extraction import DisguiseCandidate, Extraction, Reference, extract_entities


def write_gold(extraction: Extraction, gold_dir: Path) -> Path:
    gold_dir.mkdir(parents=True, exist_ok=True)
    registry_path = gold_dir / "registry.jsonl"
    with registry_path.open("w", encoding="utf-8") as fh:
        for row in sorted(extraction.registry, key=lambda r: (r.valid_from, r.canonical_name)):
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    (gold_dir / "registry_quality.json").write_text(
        json.dumps(asdict(extraction.quality), indent=2), encoding="utf-8"
    )
    write_disguise_candidates(extraction, gold_dir / "disguise_candidates.csv")
    return registry_path


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

    return Reference(
        common_words=load_common_words(),
        characters=dataset("characters"),
        islands=dataset("islands"),
        devil_fruits=dataset("devil_fruits"),
        concepts=frozenset(_read_list(reference_dir / "concepts.txt")),
    )


def run(data_dir: Path = paths.DATA_DIR) -> Extraction:
    archive = load_bronze(paths.bronze_dir(data_dir) / "chapters.jsonl")
    reference = load_reference()
    extraction = extract_entities(list(archive.values()), reference)
    registry_path = write_gold(extraction, paths.gold_dir(data_dir))

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
    args = p.parse_args()
    run(args.data_dir)


if __name__ == "__main__":
    main()

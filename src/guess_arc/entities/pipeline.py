"""
One Piece — extraction des Entities, du bronze à Registry(t) dans la gold.

Gold : registry.jsonl (une ligne par Entity et par changement, datée par
valid_from / valid_to) et registry_quality.json (rapport qualité).

Usage :
    python -m guess_arc.entities
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from guess_arc import paths
from guess_arc.ingestion.pipeline import load_bronze

from .extraction import Extraction, Reference, extract_entities


def write_gold(extraction: Extraction, gold_dir: Path) -> Path:
    gold_dir.mkdir(parents=True, exist_ok=True)
    registry_path = gold_dir / "registry.jsonl"
    with registry_path.open("w", encoding="utf-8") as fh:
        for row in sorted(extraction.registry, key=lambda r: (r.valid_from, r.canonical_name)):
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    (gold_dir / "registry_quality.json").write_text(
        json.dumps(asdict(extraction.quality), indent=2), encoding="utf-8"
    )
    return registry_path


def run(data_dir: Path = paths.DATA_DIR) -> Extraction:
    archive = load_bronze(paths.bronze_dir(data_dir) / "chapters.jsonl")
    extraction = extract_entities(list(archive.values()), Reference())
    registry_path = write_gold(extraction, paths.gold_dir(data_dir))

    scenes = extraction.quality.scenes_per_chapter
    entities = {row.canonical_name for row in extraction.registry}
    print(f"Bronze : {len(archive)} chapitres, {sum(scenes.values())} Scenes")
    print(f"Gold   : {registry_path} ({len(entities)} Entities, {len(extraction.registry)} lignes)")
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

"""Issue #75 - book_id must not be guessed from a candidate field collision.

`CANDIDATE_FIELDS["book_id"]` used to include "arc", which collides with
the silver corpus's own `arc` front-matter field: with no `book_id` field
declared, auto-detection would resolve `book_id -> arc` and silently
fragment the single continuous One Piece narrative into one fake "book"
per story arc.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ncp.config import Config
from ncp.config.schema import DatasetConfig
from ncp.data.mapping import RecordMapper

REPO_ROOT = Path(__file__).resolve().parents[1]
SILVER_CONFIG_PATH = REPO_ROOT / "configs" / "dataset" / "silver.yaml"


def test_book_id_is_not_guessed_from_an_arc_field():
    config = DatasetConfig(default_book_id="one_piece")
    raw = {"chapter": 1, "summary": "A boy sets sail.", "arc": "Romance Dawn Arc"}

    mapper = RecordMapper.from_sample(config, raw)
    record = mapper.map_one(raw)

    assert record.book_id == "one_piece"


def _load_silver_dataset_config() -> DatasetConfig:
    with SILVER_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return Config.from_dict(data).dataset


def _sample_chapter(chapter: int, arc: str) -> dict:
    return {
        "chapter": chapter,
        "title": f"Chapter {chapter}",
        "jname": "...",
        "arc": arc,
        "revision_id": 1,
        "revised_at": "2026-01-01T00:00:00Z",
        "complete": True,
        "character_count": 0,
        "characters": [],
        "source": "https://onepiece.fandom.com/",
        "license": "CC BY-SA",
        "summary": f"Summary for chapter {chapter}.",
    }


def test_silver_config_maps_every_arc_to_a_single_book_id():
    dataset_config = _load_silver_dataset_config()
    raws = [
        _sample_chapter(1, "Romance Dawn Arc"),
        _sample_chapter(8, "Orange Town Arc"),
        _sample_chapter(1193, "Egghead Arc"),
    ]

    mapper = RecordMapper.from_sample(dataset_config, raws[0])
    records = mapper.map_many(raws)

    book_ids = {record.book_id for record in records}

    assert book_ids == {dataset_config.default_book_id}

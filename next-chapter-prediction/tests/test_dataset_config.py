"""T001 - the committed silver-corpus dataset config loads correctly.

Tested against `configs/dataset/silver.yaml`, not `local.yaml`: the latter is
an optional, gitignored, machine-specific override (see
`configs/dataset/local.example.yaml`) and must not be required for the
project to work on a fresh clone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ncp.config import Config, ConfigError

REPO_ROOT = Path(__file__).resolve().parents[1]
SILVER_CONFIG_PATH = REPO_ROOT / "configs" / "dataset" / "silver.yaml"

#: YAML front-matter fields named in SPEC §4 for a silver chapter file.
SPEC_FRONTMATTER_FIELDS = {
    "chapter",
    "title",
    "jname",
    "arc",
    "revision_id",
    "revised_at",
    "complete",
    "character_count",
    "characters",
    "source",
    "license",
}


def _load_silver_config() -> Config:
    with SILVER_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return Config.from_dict(data)


def test_silver_dataset_config_parses_with_expected_shape():
    config = _load_silver_config()

    assert config.dataset.format == "markdown_dir"
    assert config.dataset.field_map.chapter_index == "chapter"
    assert config.dataset.field_map.title == "title"
    assert set(config.dataset.field_map.metadata) == SPEC_FRONTMATTER_FIELDS - {"chapter", "title"}


def test_silver_dataset_config_resolved_path_is_an_existing_directory():
    config = _load_silver_config()

    resolved = config.dataset.resolved_path()

    if not resolved.is_dir():
        pytest.skip(
            f"Silver corpus not found at {resolved}. It is gitignored and must be "
            "generated locally - see 'Obtaining the silver corpus' in README.md."
        )

    assert resolved.is_dir()


def test_silver_dataset_config_drops_no_spec_frontmatter_field():
    config = _load_silver_config()

    mapped_fields = set(config.dataset.field_map.metadata)
    mapped_fields.add(config.dataset.field_map.chapter_index)
    mapped_fields.add(config.dataset.field_map.title)

    assert mapped_fields == SPEC_FRONTMATTER_FIELDS


def test_malformed_field_map_raises_config_error_not_a_crash():
    malformed = {
        "dataset": {
            "path": "configs/dataset",
            "field_map": {"not_a_real_logical_field": "chapter"},
        }
    }

    with pytest.raises(ConfigError):
        Config.from_dict(malformed)


def test_silver_dataset_config_validates_successfully():
    config = _load_silver_config()

    config.validate()  # must not raise: default_book_id covers the missing field_map.book_id


def test_dataset_config_without_any_book_id_source_raises_config_error():
    """Neither `field_map.book_id` nor a usable `default_book_id` is set.

    `book_id` must never silently end up `None` - every `ChapterRecord` needs
    one to be grouped into a `Book`.
    """
    config = Config.from_dict(
        {
            "dataset": {
                "path": "whatever",
                "default_book_id": None,
            }
        }
    )

    with pytest.raises(ConfigError):
        config.validate()

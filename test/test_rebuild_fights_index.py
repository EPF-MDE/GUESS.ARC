"""Sanity check for API/rebuild_fights_index.py — backfilling fights_index.json
from chapter_NNNN.json files that were tagged before the index existed (a gap
found in the issue #3 spec review: chapters written before issue #11 never
retroactively populate the index, since it's only updated live as
tag_chapter *writes* a new chapter file). No network access; writes only to
a temp directory."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from rebuild_fights_index import rebuild_index  # noqa: E402


def envelope_with_fight(chapter_number, fight_id="fight-0001", ends_this_chapter=False, winner=None):
    return {
        "schema_version": 1,
        "chapter": {"number": chapter_number},
        "characters": [],
        "interactions": [
            {
                "type": "fight",
                "fight_id": fight_id,
                "battle": {"sides": [["monkey-d-luffy"], ["arlong"]]},
                "duels": [],
                "ends_this_chapter": ends_this_chapter,
                "winner": winner,
            }
        ],
    }


def envelope_without_fight(chapter_number):
    return {
        "schema_version": 1,
        "chapter": {"number": chapter_number},
        "characters": [],
        "interactions": [],
    }


class TestRebuildIndex(unittest.TestCase):
    def test_rebuilds_a_multi_chapter_fight_from_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            taxonomy_dir = pathlib.Path(tmp)
            (taxonomy_dir / "chapter_0001.json").write_text(
                json.dumps(envelope_with_fight(1)), encoding="utf-8"
            )
            (taxonomy_dir / "chapter_0002.json").write_text(
                json.dumps(envelope_with_fight(2, ends_this_chapter=True, winner=["monkey-d-luffy"])),
                encoding="utf-8",
            )

            index = rebuild_index(taxonomy_dir)

        self.assertEqual(set(index), {"fight-0001"})
        entry = index["fight-0001"]
        self.assertEqual(entry["chapters"], [1, 2])
        self.assertTrue(entry["resolved"])
        self.assertEqual(entry["winner"], ["monkey-d-luffy"])

    def test_chapters_without_a_fight_interaction_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            taxonomy_dir = pathlib.Path(tmp)
            (taxonomy_dir / "chapter_0001.json").write_text(
                json.dumps(envelope_without_fight(1)), encoding="utf-8"
            )

            index = rebuild_index(taxonomy_dir)

        self.assertEqual(index, {})

    def test_rebuild_is_order_independent_regardless_of_filename_discovery_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            taxonomy_dir = pathlib.Path(tmp)
            # Written in reverse chapter order on disk — rebuild_index sorts
            # by parsed chapter number itself, not directory iteration order.
            (taxonomy_dir / "chapter_0005.json").write_text(
                json.dumps(envelope_with_fight(5, ends_this_chapter=True, winner=["arlong"])),
                encoding="utf-8",
            )
            (taxonomy_dir / "chapter_0003.json").write_text(
                json.dumps(envelope_with_fight(3)), encoding="utf-8"
            )

            index = rebuild_index(taxonomy_dir)

        self.assertEqual(index["fight-0001"]["chapters"], [3, 5])
        self.assertTrue(index["fight-0001"]["resolved"])


if __name__ == "__main__":
    unittest.main()

"""Sanity check for the Fights Index maintenance (issue #11). No network or
filesystem access needed for the merge logic itself — same spirit as
test_taxonomy_envelope.py's split between pure logic and I/O.

Covers the acceptance criteria called out as testable offline:
- a new fight_id creates an entry with that chapter in `chapters`
- a later chapter with the same fight_id extends the entry without
  duplicating or dropping previously recorded chapters
- `resolved`/`winner` update when a chapter marks the Fight's end
- processing a Fight's chapters out of order (or resuming after a gap)
  converges to the same index, never corrupting it
"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from fights_index import (  # noqa: E402
    load_fights_index,
    merge_fight_interaction,
    save_fights_index,
    update_index_with_chapter,
)


def fight_interaction(
    fight_id="fight-0034",
    sides=(["monkey-d-luffy"], ["arlong"]),
    ends_this_chapter=False,
    winner=None,
):
    return {
        "type": "fight",
        "fight_id": fight_id,
        "battle": {"sides": [list(side) for side in sides]},
        "duels": [],
        "ends_this_chapter": ends_this_chapter,
        "winner": winner,
    }


class TestNewFightCreatesEntry(unittest.TestCase):
    def test_first_chapter_seen_creates_an_entry_with_that_chapter(self):
        index = {}
        merge_fight_interaction(index, 82, fight_interaction())
        self.assertIn("fight-0034", index)
        self.assertEqual(index["fight-0034"]["chapters"], [82])

    def test_new_entry_starts_unresolved_with_no_winner(self):
        index = {}
        merge_fight_interaction(index, 82, fight_interaction())
        entry = index["fight-0034"]
        self.assertFalse(entry["resolved"])
        self.assertIsNone(entry["winner"])

    def test_new_entry_sides_mirror_the_interaction(self):
        index = {}
        merge_fight_interaction(
            index, 82, fight_interaction(sides=(["monkey-d-luffy", "roronoa-zoro"], ["arlong-pirates"]))
        )
        self.assertEqual(
            index["fight-0034"]["sides"],
            [["monkey-d-luffy", "roronoa-zoro"], ["arlong-pirates"]],
        )

    def test_label_is_derived_from_participant_ids(self):
        index = {}
        merge_fight_interaction(index, 82, fight_interaction(sides=(["monkey-d-luffy"], ["arlong"])))
        self.assertEqual(index["fight-0034"]["label"], "Monkey D Luffy vs. Arlong")

    def test_ends_this_chapter_on_first_chapter_resolves_immediately(self):
        index = {}
        merge_fight_interaction(
            index, 2, fight_interaction(ends_this_chapter=True, winner=["monkey-d-luffy"])
        )
        entry = index["fight-0034"]
        self.assertTrue(entry["resolved"])
        self.assertEqual(entry["winner"], ["monkey-d-luffy"])


class TestIncrementalUpdateExtendsExistingEntry(unittest.TestCase):
    def test_later_chapter_adds_to_chapters_without_losing_earlier_ones(self):
        index = {}
        merge_fight_interaction(index, 82, fight_interaction())
        merge_fight_interaction(index, 83, fight_interaction())
        self.assertEqual(index["fight-0034"]["chapters"], [82, 83])

    def test_reprocessing_the_same_chapter_does_not_duplicate_it(self):
        index = {}
        merge_fight_interaction(index, 82, fight_interaction())
        merge_fight_interaction(index, 82, fight_interaction())
        self.assertEqual(index["fight-0034"]["chapters"], [82])

    def test_many_consecutive_chapters_accumulate_in_order(self):
        # Mirrors the corpus pattern named in ADR 0004: 3-7+ consecutive
        # chapters (e.g. 418-426) sharing one fight_id.
        index = {}
        for chapter in range(418, 427):
            merge_fight_interaction(index, chapter, fight_interaction(fight_id="fight-0100"))
        self.assertEqual(index["fight-0100"]["chapters"], list(range(418, 427)))


class TestSidesMergeAdditively(unittest.TestCase):
    def test_new_participant_is_added_without_dropping_existing_ones(self):
        index = {}
        merge_fight_interaction(index, 81, fight_interaction(sides=(["monkey-d-luffy"], ["arlong"])))
        merge_fight_interaction(
            index, 82, fight_interaction(sides=(["monkey-d-luffy", "roronoa-zoro"], ["arlong"]))
        )
        sides = index["fight-0034"]["sides"]
        self.assertEqual(sides[0], sorted(["monkey-d-luffy", "roronoa-zoro"]))
        self.assertEqual(sides[1], ["arlong"])

    def test_duplicate_participant_across_chapters_is_not_repeated(self):
        index = {}
        merge_fight_interaction(index, 81, fight_interaction())
        merge_fight_interaction(index, 82, fight_interaction())
        self.assertEqual(index["fight-0034"]["sides"], [["monkey-d-luffy"], ["arlong"]])

    def test_label_reflects_the_merged_sides(self):
        index = {}
        merge_fight_interaction(index, 81, fight_interaction(sides=(["monkey-d-luffy"], ["arlong"])))
        merge_fight_interaction(
            index, 82, fight_interaction(sides=(["monkey-d-luffy", "roronoa-zoro"], ["arlong"]))
        )
        self.assertEqual(index["fight-0034"]["label"], "Monkey D Luffy, Roronoa Zoro vs. Arlong")


class TestResolutionUpdatesFromInteractionFlags(unittest.TestCase):
    def test_ends_this_chapter_marks_resolved_and_records_winner(self):
        index = {}
        merge_fight_interaction(index, 87, fight_interaction())
        merge_fight_interaction(
            index, 89, fight_interaction(ends_this_chapter=True, winner=["monkey-d-luffy"])
        )
        entry = index["fight-0034"]
        self.assertTrue(entry["resolved"])
        self.assertEqual(entry["winner"], ["monkey-d-luffy"])

    def test_unresolved_chapter_does_not_touch_an_already_resolved_entry(self):
        index = {}
        merge_fight_interaction(
            index, 89, fight_interaction(ends_this_chapter=True, winner=["monkey-d-luffy"])
        )
        merge_fight_interaction(index, 90, fight_interaction(ends_this_chapter=False))
        entry = index["fight-0034"]
        self.assertTrue(entry["resolved"])
        self.assertEqual(entry["winner"], ["monkey-d-luffy"])


class TestOutOfOrderProcessingDoesNotCorruptTheIndex(unittest.TestCase):
    """issue #11 AC: processing a Fight's chapters out of order, or resuming
    after a gap, must converge to the same index as processing in order."""

    def test_processing_the_ending_chapter_before_an_earlier_one(self):
        forward = {}
        merge_fight_interaction(forward, 87, fight_interaction())
        merge_fight_interaction(
            forward, 89, fight_interaction(ends_this_chapter=True, winner=["monkey-d-luffy"])
        )

        backward = {}
        merge_fight_interaction(
            backward, 89, fight_interaction(ends_this_chapter=True, winner=["monkey-d-luffy"])
        )
        merge_fight_interaction(backward, 87, fight_interaction())

        self.assertEqual(forward, backward)

    def test_sides_converge_regardless_of_merge_order(self):
        forward = {}
        merge_fight_interaction(forward, 81, fight_interaction(sides=(["monkey-d-luffy"], ["arlong"])))
        merge_fight_interaction(
            forward, 82, fight_interaction(sides=(["roronoa-zoro"], ["arlong", "hatchan"]))
        )

        backward = {}
        merge_fight_interaction(
            backward, 82, fight_interaction(sides=(["roronoa-zoro"], ["arlong", "hatchan"]))
        )
        merge_fight_interaction(backward, 81, fight_interaction(sides=(["monkey-d-luffy"], ["arlong"])))

        self.assertEqual(forward, backward)

    def test_resuming_after_a_gap_keeps_prior_history(self):
        index = {}
        merge_fight_interaction(index, 418, fight_interaction(fight_id="fight-0100"))
        merge_fight_interaction(index, 419, fight_interaction(fight_id="fight-0100"))
        # Simulate a run interrupted here, then resumed later.
        merge_fight_interaction(index, 422, fight_interaction(fight_id="fight-0100"))
        self.assertEqual(index["fight-0100"]["chapters"], [418, 419, 422])


class TestUpdateIndexWithChapter(unittest.TestCase):
    def test_merges_every_fight_interaction_in_the_envelope(self):
        envelope = {
            "interactions": [
                fight_interaction(fight_id="fight-0001"),
                fight_interaction(fight_id="fight-0002", sides=(["sanji"], ["kuroobi"])),
            ]
        }
        index = {}
        update_index_with_chapter(index, 82, envelope)
        self.assertEqual(set(index), {"fight-0001", "fight-0002"})
        self.assertEqual(index["fight-0001"]["chapters"], [82])
        self.assertEqual(index["fight-0002"]["chapters"], [82])

    def test_non_fight_interactions_are_ignored(self):
        envelope = {"interactions": [{"type": "alliance", "fight_id": "should-be-ignored"}]}
        index = {}
        update_index_with_chapter(index, 82, envelope)
        self.assertEqual(index, {})

    def test_chapter_with_no_interactions_is_a_no_op(self):
        index = {}
        update_index_with_chapter(index, 82, {"interactions": []})
        self.assertEqual(index, {})


class TestFightsIndexFileIO(unittest.TestCase):
    def test_load_missing_file_returns_empty_index(self, tmp_path=None):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "fights_index.json"
            self.assertEqual(load_fights_index(path), {})

    def test_save_then_load_round_trips(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "nested" / "fights_index.json"
            index = {}
            merge_fight_interaction(index, 82, fight_interaction())
            save_fights_index(index, path)
            self.assertEqual(load_fights_index(path), index)

    def test_saved_file_is_readable_json(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "fights_index.json"
            index = {}
            merge_fight_interaction(index, 82, fight_interaction())
            save_fights_index(index, path)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), index)

    def test_save_does_not_leave_a_temp_file_behind_on_success(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "fights_index.json"
            save_fights_index({}, path)
            self.assertEqual(list(pathlib.Path(tmpdir).iterdir()), [path])

    def test_a_previously_saved_file_survives_a_failed_overwrite(self):
        """issue #11 AC: resuming after a cut must not corrupt the index —
        save_fights_index writes via a temp file + atomic rename, so an
        error partway through a re-save (e.g. disk full, process killed)
        cannot leave the on-disk file truncated."""
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "fights_index.json"
            original = {}
            merge_fight_interaction(original, 82, fight_interaction())
            save_fights_index(original, path)

            updated = {}
            merge_fight_interaction(updated, 82, fight_interaction())
            merge_fight_interaction(updated, 83, fight_interaction())
            with patch("json.dumps", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    save_fights_index(updated, path)

            self.assertEqual(load_fights_index(path), original)
            self.assertEqual(list(pathlib.Path(tmpdir).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()

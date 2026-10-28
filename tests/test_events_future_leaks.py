"""Fuites du futur dans le préparsing, à travers le pipeline `--dry-run`.

Chapitres silver synthétiques et fichier de relecture écrits dans un dossier
temporaire, puis lecture de `data/event/in/events_NNNN.md` et de la liste des
candidats. Sans réseau.
"""
import io
import json
import unittest
from contextlib import redirect_stdout

from guess_arc import paths
from guess_arc.events.pipeline import main, run

from test_events_preparse import PreparseTestCase, chapter

LEAK = "Luffy would later meet him again in Wano."
LONG = f"Luffy fights Buggy. {LEAK} Nami steals the map."


class LeakTestCase(PreparseTestCase):
    def setUp(self):
        super().setUp()
        self.review_path = self.data_dir / "review" / "future_leaks.json"

    def write_review(self, *entries):
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_path.write_text(json.dumps(list(entries)), encoding="utf-8")

    def dry_run(self, first=None, last=None):
        run(data_dir=self.data_dir, first=first, last=last, dry_run=True,
            review_path=self.review_path)

    def candidates(self):
        path = paths.event_leak_candidates_path(self.data_dir)
        return json.loads(path.read_text(encoding="utf-8"))

    def long_summary(self, number):
        _, body = self.read_input(number)
        return body.split("=== LONG SUMMARY ===\n", 1)[1].split("\n\n=== CHAPTER NOTES", 1)[0]


class TestCandidates(LeakTestCase):
    def test_candidates_are_listed_with_chapter_section_and_passage(self):
        self.write_silver(
            chapter(10, long_summary=LONG,
                    short_summary="Zoro will later be revealed to be lost.",
                    notes=["This foreshadows the events of the Wano Country Arc.",
                           "Smoker is introduced."]),
            chapter(11),
        )
        self.dry_run()
        self.assertEqual(self.candidates(), [
            {"chapter": 10, "section": "short_summary",
             "passage": "Zoro will later be revealed to be lost.", "decision": None},
            {"chapter": 10, "section": "long_summary", "passage": LEAK, "decision": None},
            {"chapter": 10, "section": "notes",
             "passage": "This foreshadows the events of the Wano Country Arc.",
             "decision": None},
        ])

    def test_passage_is_a_whole_sentence_despite_abbreviations(self):
        self.write_silver(chapter(12, long_summary=(
            'Luffy meets Mr. 3. Dr. Kureha says "Mr. 2 will later betray you." '
            "Usopp cries!")))
        self.dry_run()
        self.assertEqual([c["passage"] for c in self.candidates()],
                         ['Dr. Kureha says "Mr. 2 will later betray you."'])

    def test_no_candidate_without_mention_of_the_future(self):
        self.write_silver(chapter(13, long_summary="10 years later, Luffy sets out to sea."))
        self.dry_run()
        self.assertEqual(self.candidates(), [])

    def test_known_decision_is_reported_in_candidates(self):
        self.write_silver(chapter(14, long_summary=LONG))
        self.write_review({"chapter": 14, "section": "long_summary", "passage": LEAK,
                           "decision": "keep"})
        self.dry_run()
        self.assertEqual(self.candidates()[0]["decision"], "keep")


class TestRemoval(LeakTestCase):
    def test_pending_candidate_stays_in_text(self):
        self.write_silver(chapter(20, long_summary=LONG))
        self.dry_run()
        self.assertEqual(self.long_summary(20), LONG)
        front, _ = self.read_input(20)
        self.assertRegex(front, r"(?m)^  future_leaks_removed: 0$")

    def test_kept_candidate_stays_in_text(self):
        self.write_silver(chapter(21, long_summary=LONG))
        self.write_review({"chapter": 21, "section": "long_summary", "passage": LEAK,
                           "decision": "keep"})
        self.dry_run()
        self.assertEqual(self.long_summary(21), LONG)

    def test_removed_sentence_leaves_the_rest_of_the_summary(self):
        self.write_silver(chapter(22, long_summary=f"{LONG}\n\n{LEAK}\n\nThe end."))
        self.write_review({"chapter": 22, "section": "long_summary", "passage": LEAK,
                           "decision": "remove"})
        self.dry_run()
        self.assertEqual(self.long_summary(22),
                         "Luffy fights Buggy. Nami steals the map.\n\nThe end.")
        front, _ = self.read_input(22)
        self.assertRegex(front, r"(?m)^  future_leaks_removed: 2$")

    def test_removed_note_and_short_summary_sentence(self):
        note = "This foreshadows the events of the Wano Country Arc."
        self.write_silver(chapter(23, short_summary="Zoro is lost. Zoro is later found.",
                                  notes=[note, "Smoker is introduced."]))
        self.write_review(
            {"chapter": 23, "section": "notes", "passage": note, "decision": "remove"},
            {"chapter": 23, "section": "short_summary", "passage": "Zoro is later found.",
             "decision": "remove"},
        )
        self.dry_run()
        front, body = self.read_input(23)
        self.assertIn("=== SHORT SUMMARY ===\nZoro is lost.\n", body)
        self.assertTrue(body.endswith("=== CHAPTER NOTES ===\n- Smoker is introduced.\n"))
        self.assertRegex(front, r"(?m)^  future_leaks_removed: 2$")

    def test_decision_applies_only_to_its_chapter(self):
        self.write_silver(chapter(24, long_summary=LONG), chapter(25, long_summary=LONG))
        self.write_review({"chapter": 24, "section": "long_summary", "passage": LEAK,
                           "decision": "remove"})
        self.dry_run()
        self.assertNotIn(LEAK, self.long_summary(24))
        self.assertIn(LEAK, self.long_summary(25))
        self.assertEqual([(c["chapter"], c["decision"]) for c in self.candidates()],
                         [(24, "remove"), (25, None)])

    def test_editorial_note_is_not_a_leak_candidate(self):
        self.write_silver(chapter(26, notes=[
            "This is the last chapter of the Loguetown Arc, which would later be adapted "
            "in the anime."]))
        self.dry_run()
        self.assertEqual(self.candidates(), [])


class TestReviewFile(LeakTestCase):
    def test_unknown_decision_is_refused(self):
        self.write_silver(chapter(30, long_summary=LONG))
        self.write_review({"chapter": 30, "section": "long_summary", "passage": LEAK,
                           "decision": "maybe"})
        with self.assertRaises(ValueError):
            self.dry_run()

    def test_decision_on_a_changed_passage_is_reported(self):
        self.write_silver(chapter(32, long_summary="Luffy would later meet him in Wano."))
        self.write_review({"chapter": 32, "section": "long_summary", "passage": LEAK,
                           "decision": "remove"})
        out = io.StringIO()
        with redirect_stdout(out):
            self.dry_run()
        self.assertIn("1 décisions ne désignent plus aucun passage", out.getvalue())
        self.assertIn("Luffy would later meet him in Wano.", self.long_summary(32))

    def test_cli_reads_review_file(self):
        self.write_silver(chapter(31, long_summary=LONG))
        self.write_review({"chapter": 31, "section": "long_summary", "passage": LEAK,
                           "decision": "remove"})
        main(["--data-dir", str(self.data_dir), "--dry-run",
              "--leak-review", str(self.review_path)])
        self.assertEqual(self.long_summary(31), "Luffy fights Buggy. Nami steals the map.")


if __name__ == "__main__":
    unittest.main()

"""Reprise du passage et gel de version, à travers le pipeline, contre un client factice.

Le pipeline est lancé deux fois sur le même dossier de données ; le nombre
d'appels au client factice dit quels chapitres ont été (ré)extraits.
"""
import json
import unittest
from unittest import mock

from guess_arc.events import versions
from guess_arc.events.resume import freeze

from test_events_llm import LlmTestCase, char, chapter, llm_event, response


def called_chapters(client):
    return [int(c.user.split()[1]) for c in client.calls]


class ResumeTestCase(LlmTestCase):
    def setUp(self):
        super().setUp()
        self.write_silver(*(chapter(n, char("Luffy"), char("Zoro")) for n in (1, 2, 3)))


class TestResume(ResumeTestCase):
    def test_rerun_after_a_complete_pass_calls_nothing(self):
        self.extract(response(1), response(2), response(3))
        before = [self.output(n) for n in (1, 2, 3)]
        self.extract()
        self.assertEqual(self.client.calls, [])
        self.assertEqual([self.output(n) for n in (1, 2, 3)], before)

    def test_rerun_after_a_stop_calls_only_missing_chapters(self):
        self.extract(response(1), response(2), response(3))
        self.out_path(2).unlink()
        self.extract(response(2))
        self.assertEqual(called_chapters(self.client), [2])

    def test_truncated_output_is_extracted_again(self):
        self.extract(response(1), response(2), response(3))
        self.out_path(2).write_text('{"meta": {"chap', encoding="utf-8")
        self.extract(response(2))
        self.assertEqual(called_chapters(self.client), [2])
        self.assertEqual(self.output(2)["meta"]["origins"], ["wiki", "llm"])

    def test_abandoned_chapter_is_retried_on_the_next_pass(self):
        self.extract(response(1), "x", "x", "x", response(3))
        self.extract(response(2))
        self.assertEqual(called_chapters(self.client), [2])
        self.assertEqual(self.output(2)["meta"]["origins"], ["wiki", "llm"])

    def test_dry_run_output_is_not_mistaken_for_an_extraction(self):
        self.extract(dry_run=True)
        self.extract(response(1), response(2), response(3))
        self.assertEqual(called_chapters(self.client), [1, 2, 3])

    def test_batches_by_range(self):
        self.extract(response(1), response(2), first=1, last=2)
        self.extract(response(3))
        self.assertEqual(called_chapters(self.client), [3])


class TestIncomplete(ResumeTestCase):
    def test_incomplete_chapter_is_skipped_then_extracted_once_complete(self):
        self.write_silver(chapter(2, char("Luffy"), char("Zoro"), complete=False))
        self.extract(response(1), response(3))
        self.assertEqual(called_chapters(self.client), [1, 3])
        self.assertEqual(self.output(2)["meta"]["origins"], ["wiki"])
        self.write_silver(chapter(2, char("Luffy"), char("Zoro"), complete=True))
        self.extract(response(2))
        self.assertEqual(called_chapters(self.client), [2])
        self.assertEqual(self.output(2)["meta"]["origins"], ["wiki", "llm"])


class TestRevision(ResumeTestCase):
    def setUp(self):
        super().setUp()
        self.extract(response(1), response(2), response(3))
        self.write_silver(chapter(2, char("Luffy"), char("Zoro"), revision_id=9999,
                                  long_summary="Luffy fights Zoro and wins again."))

    def test_changed_revision_is_extracted_again(self):
        self.extract(response(2, llm_event(evidence="Luffy fights Zoro and wins again.")))
        self.assertEqual(called_chapters(self.client), [2])
        self.assertEqual(self.output(2)["meta"]["revision_id"], 9999)

    def test_frozen_version_keeps_the_chapter(self):
        freeze(self.data_dir, "fake-gemma")
        before = self.output(2)
        self.extract()
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.output(2), before)

    def test_freeze_of_another_model_does_not_apply(self):
        freeze(self.data_dir, "other-model")
        self.extract(response(2))
        self.assertEqual(called_chapters(self.client), [2])

    def test_frozen_version_still_extracts_missing_chapters(self):
        freeze(self.data_dir, "fake-gemma")
        self.out_path(3).unlink()
        self.extract(response(3))
        self.assertEqual(called_chapters(self.client), [3])

    def test_freeze_file_records_the_versions(self):
        path = freeze(self.data_dir, "fake-gemma")
        self.assertEqual(path, self.data_dir / "event" / "frozen.json")
        frozen = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["model"], "fake-gemma")
        for key in ("prompt_version", "schema_version", "taxonomy_version",
                    "entities_version"):
            self.assertRegex(frozen[key], r"^v\d+$", key)


class TestVersionChange(ResumeTestCase):
    def setUp(self):
        super().setUp()
        self.extract(response(1), response(2), response(3))

    def test_prompt_version_change_extracts_every_chapter(self):
        with mock.patch.object(versions, "PROMPT_VERSION", "v999"):
            self.extract(response(1), response(2), response(3))
        self.assertEqual(called_chapters(self.client), [1, 2, 3])
        self.assertEqual(self.output(1)["meta"]["prompt_version"], "v999")

    def test_version_change_overrides_the_freeze(self):
        freeze(self.data_dir, "fake-gemma")
        for name in ("PROMPT_VERSION", "SCHEMA_VERSION", "TAXONOMY_VERSION",
                     "ENTITIES_VERSION"):
            with self.subTest(version=name), mock.patch.object(versions, name, "v999"):
                self.extract(response(1), response(2), response(3))
                self.assertEqual(called_chapters(self.client), [1, 2, 3])

    def test_model_change_extracts_every_chapter(self):
        self.extract(response(1), response(2), response(3), model="gemma-5")
        self.assertEqual(called_chapters(self.client), [1, 2, 3])

    def test_checks_version_change_does_not_call_the_model(self):
        # Les contrôles ne changent pas la réponse du modèle : ils n'imposent pas
        # d'appel (les sorties gardent leurs anciens `checks`).
        with mock.patch.object(versions, "CHECKS_VERSION", "v999"):
            self.extract()
        self.assertEqual(self.client.calls, [])


if __name__ == "__main__":
    unittest.main()

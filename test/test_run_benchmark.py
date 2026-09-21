"""Tests for the benchmark run script (issue #10).

default_batch() reads the real data/silver/ directory (no network, no API
key needed) — same "sanity check against real bronze/silver data" spirit as
test_silver_format.py. The provider-call logging path is covered separately
in test_taxonomy_client_benchmark_log.py, with requests mocked out.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
import run_benchmark  # noqa: E402
import taxonomy_client  # noqa: E402
from providers import GEMINI, MISTRAL  # noqa: E402
from quota_state import QuotaState  # noqa: E402
from run_benchmark import default_batch  # noqa: E402
from taxonomy_client import SILVER_DIR  # noqa: E402

from test_taxonomy_client_fallback import FakeResponse, envelope_response  # noqa: E402
from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402


@unittest.skipUnless(SILVER_DIR.exists(), "data/silver/ not present in this checkout")
class TestDefaultBatch(unittest.TestCase):
    def test_default_batch_size_is_twenty_chapters(self):
        batch = default_batch(20)
        self.assertEqual(len(batch), 20)

    def test_batch_is_the_lowest_numbered_chapters_in_ascending_order(self):
        batch = default_batch(5)
        self.assertEqual(batch, sorted(batch))
        all_numbers = default_batch(10_000)
        self.assertEqual(batch, all_numbers[:5])

    def test_batch_size_larger_than_the_corpus_returns_every_chapter(self):
        all_numbers = default_batch(10_000)
        self.assertEqual(default_batch(10_000 + 1), all_numbers)


@unittest.skipUnless(SILVER_DIR.exists(), "data/silver/ not present in this checkout")
class TestRunSurvivesARejectedEnvelope(unittest.TestCase):
    """Reproduces a real run: one provider returns a schema-valid envelope
    for the wrong chapter (tag_chapter now rejects that with ValueError —
    see TestChapterNumberMismatchIsRejected in
    test_taxonomy_client_fallback.py). Before this fix, run_benchmark.run()
    only caught AllProvidersFailedError, so that ValueError crashed the
    whole benchmark uncaught, skipping every provider/chapter still queued
    behind the bad one (observed for real with Groq on 2026-09-21)."""

    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key", "MISTRAL_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.taxonomy_dir = pathlib.Path(self.tmpdir.name) / "taxonomy"
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_mismatched_chapter_is_logged_and_the_rest_of_the_run_still_completes(self):
        good_envelope = copy.deepcopy(VALID_ENVELOPE)
        good_envelope["chapter"]["number"] = 1
        wrong_chapter_envelope = copy.deepcopy(VALID_ENVELOPE)  # chapter.number == 82, not 1

        def fake_post(url, headers=None, json=None, timeout=None):
            if GEMINI.base_url.rstrip("/") in url:
                return envelope_response(good_envelope)
            return envelope_response(wrong_chapter_envelope)  # mistral: the bad one

        with patch.object(taxonomy_client, "TAXONOMY_DIR", self.taxonomy_dir), \
             patch.object(run_benchmark, "TAXONOMY_DIR", self.taxonomy_dir), \
             patch.object(run_benchmark, "QuotaState", lambda: QuotaState(path=None)), \
             patch("taxonomy_client.requests.post", side_effect=fake_post):
            with self.assertRaises(SystemExit) as ctx:
                run_benchmark.run(
                    chapters=[1], batch_size=20, provider_names=["gemini", "mistral"], log_path=self.log_path,
                )

        # Non-zero exit reports the failure, but it's a controlled SystemExit
        # raised at the very end of run() — not the bare ValueError escaping
        # mid-loop, which would abort before mistral's own (also queued)
        # provider even ran.
        self.assertEqual(ctx.exception.code, 1)
        self.assertTrue((self.taxonomy_dir / "gemini" / "chapter_0001.json").exists())
        self.assertFalse((self.taxonomy_dir / "mistral" / "chapter_0001.json").exists())


if __name__ == "__main__":
    unittest.main()

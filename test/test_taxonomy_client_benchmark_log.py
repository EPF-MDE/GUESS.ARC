"""Integration-shaped sanity check for per-call benchmark logging (issue
#10), with requests.post mocked out so it runs with no network access —
same spirit as test_taxonomy_client_fallback.py / test_taxonomy_client_quota.py.

Covers issue #10 AC: each call journals provider/model used, real input/
output tokens, success/failure, and error code where applicable.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from benchmark_log import BenchmarkLog, load_entries, summarize  # noqa: E402
from provider_fallback import AllProvidersFailedError  # noqa: E402
from providers import GEMINI, MISTRAL, OPENROUTER  # noqa: E402
from taxonomy_client import call_provider_chain, tag_chapter  # noqa: E402

from test_taxonomy_client_fallback import FakeResponse, models_response, no_sleep  # noqa: E402
from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402

SYSTEM_PROMPT = "system prompt"
CHAPTER_MARKDOWN = "chapter markdown"
JSON_SCHEMA = {"type": "object"}


def envelope_response_with_usage(envelope: dict, prompt_tokens: int, completion_tokens: int) -> FakeResponse:
    return FakeResponse(
        200,
        {
            "choices": [{"message": {"content": json.dumps(envelope)}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        },
    )


def envelope_response_without_usage(envelope: dict) -> FakeResponse:
    return FakeResponse(200, {"choices": [{"message": {"content": json.dumps(envelope)}}]})


class TestSuccessfulCallIsLogged(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_real_token_counts_and_provider_model_are_logged(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response_with_usage(envelope, prompt_tokens=321, completion_tokens=654)

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain(
                [GEMINI], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                chapter=7, log=log, sleep_fn=no_sleep,
            )

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["chapter"], 7)
        self.assertEqual(entry["provider"], "gemini")
        self.assertEqual(entry["model"], GEMINI.model())
        self.assertTrue(entry["success"])
        self.assertEqual(entry["input_tokens"], 321)
        self.assertEqual(entry["output_tokens"], 654)
        self.assertIsNone(entry["error_code"])

    def test_missing_usage_object_logs_none_tokens_instead_of_failing(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response_without_usage(envelope)

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain(
                [GEMINI], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                chapter=1, log=log, sleep_fn=no_sleep,
            )

        entries = load_entries(self.log_path)
        self.assertTrue(entries[0]["success"])
        self.assertIsNone(entries[0]["input_tokens"])
        self.assertIsNone(entries[0]["output_tokens"])


class TestFailedAttemptsAreLoggedWithErrorCode(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key", "MISTRAL_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_gemini_5xx_then_mistral_success_logs_every_attempt(self):
        """provider_fallback retries a 5xx once in place (MAX_5XX_ATTEMPTS)
        before falling over — so Gemini is logged twice (both failures) and
        Mistral once (success): 3 entries total, not 2."""
        mistral_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "generativelanguage" in url:
                return FakeResponse(503)
            return envelope_response_with_usage(mistral_envelope, prompt_tokens=50, completion_tokens=25)

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain(
                [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                chapter=3, log=log, sleep_fn=no_sleep,
            )

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 3)

        gemini_entries = [e for e in entries if e["provider"] == "gemini"]
        self.assertEqual(len(gemini_entries), 2)
        for gemini_entry in gemini_entries:
            self.assertFalse(gemini_entry["success"])
            self.assertEqual(gemini_entry["error_code"], 503)
            self.assertIsNone(gemini_entry["input_tokens"])

        mistral_entries = [e for e in entries if e["provider"] == "mistral"]
        self.assertEqual(len(mistral_entries), 1)
        mistral_entry = mistral_entries[0]
        self.assertTrue(mistral_entry["success"])
        self.assertEqual(mistral_entry["input_tokens"], 50)
        self.assertEqual(mistral_entry["output_tokens"], 25)

    def test_in_place_429_retries_are_each_logged_as_separate_attempts(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        calls = {"n": 0}

        def fake_post(url, headers=None, json=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResponse(429, headers={"Retry-After": "0"})
            return envelope_response_with_usage(envelope, prompt_tokens=10, completion_tokens=5)

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain(
                [GEMINI], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                chapter=1, log=log, sleep_fn=no_sleep,
            )

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 2)
        self.assertFalse(entries[0]["success"])
        self.assertEqual(entries[0]["error_code"], 429)
        self.assertTrue(entries[1]["success"])

    def test_quota_exhausted_skip_is_not_logged_as_a_call(self):
        """A provider skipped for exhausted local quota never reaches the
        network, so it has no tokens/model to report — it must not appear
        in the call log (issue #10 logs *calls*, not skips)."""
        from quota_state import QuotaState

        envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response_with_usage(envelope, prompt_tokens=1, completion_tokens=1)

        def fake_has_budget(self, provider_name, daily_limit):
            return provider_name != "gemini"

        quota = QuotaState(path=None)
        log = BenchmarkLog(path=self.log_path)
        with patch.object(QuotaState, "has_budget", fake_has_budget), patch(
            "taxonomy_client.requests.post", side_effect=fake_post
        ):
            call_provider_chain(
                [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                quota=quota, chapter=1, log=log, sleep_fn=no_sleep,
            )

        entries = load_entries(self.log_path)
        self.assertEqual({e["provider"] for e in entries}, {"mistral"})


class TestTagChapterPlumbsChapterNumberIntoLog(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_tag_chapter_logs_under_the_right_chapter_number(self):
        silver_dir = pathlib.Path(self.tmpdir.name) / "silver"
        taxonomy_dir = pathlib.Path(self.tmpdir.name) / "taxonomy"
        silver_dir.mkdir()
        (silver_dir / "chapter_0042.md").write_text("chapter text", encoding="utf-8")

        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 42

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response_with_usage(envelope, prompt_tokens=9, completion_tokens=3)

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.SILVER_DIR", silver_dir), patch(
            "taxonomy_client.TAXONOMY_DIR", taxonomy_dir
        ), patch("taxonomy_client.requests.post", side_effect=fake_post):
            tag_chapter(42, [GEMINI], SYSTEM_PROMPT, JSON_SCHEMA, log=log)

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["chapter"], 42)
        self.assertEqual(entries[0]["input_tokens"], 9)


class TestOpenRouterCatalogLookupFailureIsLogged(unittest.TestCase):
    """issue #10 AC: 'chaque appel journalise... code d'erreur le cas
    échéant' — a failed GET /models catalog lookup (issue #8) is itself a
    real network attempt against OpenRouter, so it must show up in the
    benchmark log even though it never reaches call_provider."""

    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "valid-key", "OPENROUTER_MODEL": ""},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_failed_catalog_lookup_is_logged_with_no_model_and_the_error_code(self):
        def fake_get(url, headers=None, params=None, timeout=None):
            return FakeResponse(500)

        def fake_post(url, headers=None, json=None, timeout=None):
            raise AssertionError("chat completions should never be reached: catalog lookup already failed")

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.get", side_effect=fake_get), patch(
            "taxonomy_client.requests.post", side_effect=fake_post
        ):
            with self.assertRaises(AllProvidersFailedError):
                call_provider_chain(
                    [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                    chapter=1, log=log, sleep_fn=no_sleep,
                )

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["provider"], "openrouter")
        self.assertIsNone(entries[0]["model"])
        self.assertFalse(entries[0]["success"])
        self.assertEqual(entries[0]["error_code"], 500)

    def test_empty_free_catalog_is_logged_too(self):
        def fake_get(url, headers=None, params=None, timeout=None):
            return models_response([], paid_ids=["some/paid-model"])

        log = BenchmarkLog(path=self.log_path)
        with patch("taxonomy_client.requests.get", side_effect=fake_get):
            with self.assertRaises(AllProvidersFailedError):
                call_provider_chain(
                    [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA,
                    chapter=1, log=log, sleep_fn=no_sleep,
                )

        entries = load_entries(self.log_path)
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["success"])
        self.assertEqual(entries[0]["error_code"], 503)


class TestObservedRateInReport(unittest.TestCase):
    def test_observed_rpm_and_tpm_are_computed_from_call_timestamps(self):
        entries = [
            {"provider": "gemini", "success": True, "input_tokens": 100, "output_tokens": 100,
             "timestamp": "2026-01-01T00:00:00+00:00"},
            {"provider": "gemini", "success": True, "input_tokens": 100, "output_tokens": 100,
             "timestamp": "2026-01-01T00:01:00+00:00"},
            {"provider": "gemini", "success": True, "input_tokens": 100, "output_tokens": 100,
             "timestamp": "2026-01-01T00:02:00+00:00"},
        ]
        summary = summarize(entries)
        gemini = summary["gemini"]
        self.assertEqual(gemini["elapsed_minutes"], 2.0)
        self.assertAlmostEqual(gemini["observed_rpm"], 1.5)
        self.assertAlmostEqual(gemini["observed_tpm"], 300.0)

    def test_single_call_has_no_observed_rate(self):
        entries = [{"provider": "gemini", "success": True, "input_tokens": 10, "output_tokens": 5,
                    "timestamp": "2026-01-01T00:00:00+00:00"}]
        summary = summarize(entries)
        self.assertIsNone(summary["gemini"]["observed_rpm"])
        self.assertIsNone(summary["gemini"]["observed_tpm"])


if __name__ == "__main__":
    unittest.main()

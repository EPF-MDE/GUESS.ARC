"""Integration-shaped sanity check for the preventive quota check (issue #9),
same spirit as test_taxonomy_client_fallback.py: requests.post/get mocked
out so it runs with no network access.

Covers the issue #9 acceptance criteria:
- a chapter tagged successfully updates API/quota_state.json for the
  provider that served it, and that update persists across a fresh
  QuotaState instance (cold restart);
- simulating an exhausted Groq quota falls straight over to OpenRouter
  *without ever calling Groq's endpoint*;
- simulating an exhausted OpenRouter quota (its 50/day cap) as the last
  available link raises the same explicit AllProvidersFailedError as any
  other exhausted chain, with no network call to OpenRouter either.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from providers import GEMINI, GROQ, MISTRAL, OPENROUTER  # noqa: E402
from taxonomy_client import call_provider_chain  # noqa: E402
from provider_fallback import AllProvidersFailedError  # noqa: E402
from quota_state import QuotaState  # noqa: E402

from test_taxonomy_client_fallback import setUpModule, tearDownModule, FakeResponse, envelope_response, models_response, no_sleep  # noqa: E402
from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402

SYSTEM_PROMPT = "system prompt"
CHAPTER_MARKDOWN = "chapter markdown"
JSON_SCHEMA = {"type": "object"}


class TestQuotaRecordedOnSuccess(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_path = pathlib.Path(self.tmpdir.name) / "quota_state.json"

    def test_successful_call_updates_quota_state_for_that_provider(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response(envelope)

        quota = QuotaState(path=self.state_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain([GEMINI], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, quota=quota, sleep_fn=no_sleep)

        on_disk = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["gemini"]["count"], 1)

    def test_quota_persists_across_a_cold_restart(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response(envelope)

        quota = QuotaState(path=self.state_path)
        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            call_provider_chain([GEMINI], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, quota=quota, sleep_fn=no_sleep)

        # Simulates a cold restart: a brand new QuotaState reading the same file.
        reloaded = QuotaState(path=self.state_path)
        self.assertEqual(reloaded.remaining("gemini", None), None)
        on_disk = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["gemini"]["count"], 1)


class TestGroqQuotaExhaustedSkipsToOpenRouter(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "valid-key",
                "OPENROUTER_API_KEY": "valid-key",
                "OPENROUTER_MODEL": "",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exhausted_groq_quota_falls_over_to_openrouter_with_no_network_call_to_groq(self):
        openrouter_envelope = copy.deepcopy(VALID_ENVELOPE)
        quota = QuotaState(path=None)
        for _ in range(GROQ.daily_limit):
            quota.record_success("groq")
        self.assertFalse(quota.has_budget("groq", GROQ.daily_limit))

        def fake_post(url, headers=None, json=None, timeout=None):
            if "groq" in url:
                raise AssertionError("groq must not be called once its local quota is exhausted")
            return envelope_response(openrouter_envelope)

        def fake_get(url, headers=None, params=None, timeout=None):
            return models_response(["some/free-model:free"])

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            envelope, used = call_provider_chain(
                [GROQ, OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, quota=quota, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, openrouter_envelope)
        self.assertIs(used, OPENROUTER)

    def test_healthy_groq_quota_is_used_normally(self):
        groq_envelope = copy.deepcopy(VALID_ENVELOPE)
        quota = QuotaState(path=None)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "groq" not in url:
                raise AssertionError("openrouter should never be called when groq has budget and succeeds")
            return envelope_response(groq_envelope)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            envelope, used = call_provider_chain(
                [GROQ, OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, quota=quota, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, groq_envelope)
        self.assertIs(used, GROQ)
        self.assertEqual(quota.remaining("groq", GROQ.daily_limit), GROQ.daily_limit - 1)


class TestOpenRouterQuotaExhaustedAsLastLink(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {"MISTRAL_API_KEY": "valid-key", "OPENROUTER_API_KEY": "valid-key", "OPENROUTER_MODEL": ""},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exhausted_openrouter_quota_as_last_link_raises_all_providers_failed_with_no_network_call(self):
        quota = QuotaState(path=None)
        for _ in range(OPENROUTER.daily_limit):
            quota.record_success("openrouter")
        self.assertFalse(quota.has_budget("openrouter", OPENROUTER.daily_limit))

        def fake_post(url, headers=None, json=None, timeout=None):
            raise AssertionError("openrouter must not be called once its local quota is exhausted")

        def fake_get(url, headers=None, params=None, timeout=None):
            raise AssertionError("openrouter's catalog must not be queried once its local quota is exhausted")

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, quota=quota, sleep_fn=no_sleep
                )
        self.assertEqual(set(ctx.exception.errors), {"openrouter"})

    def test_exhausted_openrouter_quota_mid_chain_falls_through_to_all_providers_failed(self):
        quota = QuotaState(path=None)
        for _ in range(OPENROUTER.daily_limit):
            quota.record_success("openrouter")

        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(500)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [MISTRAL, OPENROUTER],
                    SYSTEM_PROMPT,
                    CHAPTER_MARKDOWN,
                    JSON_SCHEMA,
                    quota=quota,
                    sleep_fn=no_sleep,
                )
        self.assertEqual(set(ctx.exception.errors), {"mistral", "openrouter"})


if __name__ == "__main__":
    unittest.main()

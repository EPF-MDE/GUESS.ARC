"""Integration-shaped sanity check for the Gemini->Mistral fallback wiring
(issue #6 acceptance criteria), with requests.post mocked out so it still
runs with no network access — same spirit as test_taxonomy_envelope.py.

Covers AC1: forcing a systematic Gemini failure falls over to Mistral, which
produces the expected JSON for the same chapter.
"""
import copy
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from providers import GEMINI, MISTRAL  # noqa: E402
from taxonomy_client import call_provider_chain  # noqa: E402
from provider_fallback import AllProvidersFailedError  # noqa: E402

from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402

SYSTEM_PROMPT = "system prompt"
CHAPTER_MARKDOWN = "chapter markdown"
JSON_SCHEMA = {"type": "object"}  # never sent to a real endpoint in these tests


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def envelope_response(envelope: dict) -> FakeResponse:
    return FakeResponse(200, {"choices": [{"message": {"content": json.dumps(envelope)}}]})


def no_sleep(_seconds: float) -> None:
    """Injected as sleep_fn so retry/backoff waits are instant in tests."""


class TestGeminiToMistralFallback(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(
            "os.environ", {"GEMINI_API_KEY": "invalid-key", "MISTRAL_API_KEY": "valid-key"}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_persistent_gemini_5xx_falls_over_to_mistral(self):
        mistral_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "generativelanguage" in url:
                return FakeResponse(500)
            return envelope_response(mistral_envelope)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            envelope, used = call_provider_chain(
                [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, mistral_envelope)
        self.assertIs(used, MISTRAL)

    def test_persistent_gemini_429_falls_over_to_mistral(self):
        mistral_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "generativelanguage" in url:
                return FakeResponse(429, headers={"Retry-After": "2"})
            return envelope_response(mistral_envelope)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            envelope, used = call_provider_chain(
                [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, mistral_envelope)
        self.assertIs(used, MISTRAL)

    def test_gemini_success_never_calls_mistral(self):
        gemini_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "generativelanguage" in url:
                return envelope_response(gemini_envelope)
            raise AssertionError("mistral should never be called when gemini succeeds")

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            envelope, used = call_provider_chain(
                [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, gemini_envelope)
        self.assertIs(used, GEMINI)

    def test_both_providers_failing_raises_all_providers_failed(self):
        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(500)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [GEMINI, MISTRAL], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
                )
        self.assertEqual(set(ctx.exception.errors), {"gemini", "mistral"})


if __name__ == "__main__":
    unittest.main()

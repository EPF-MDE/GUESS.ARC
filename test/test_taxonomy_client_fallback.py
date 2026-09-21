"""Integration-shaped sanity check for the Gemini->Mistral->Groq->OpenRouter
fallback wiring (issue #6, #7, #8 acceptance criteria), with requests.post
mocked out so it still runs with no network access — same spirit as
test_taxonomy_envelope.py.

Covers AC1 of #6: forcing a systematic Gemini failure falls over to Mistral,
which produces the expected JSON for the same chapter.
Covers AC1 of #7: forcing a systematic failure on both Gemini and Mistral
falls over to Groq, which produces the expected JSON for the same chapter —
reusing the same generic mechanism (#6), no Groq-specific branching.
Covers #8: forcing a systematic failure on Gemini, Mistral and Groq falls
over to OpenRouter, which resolves a `:free` model at runtime via
GET /models?max_price=0 (never a hardcoded id) and sends the
HTTP-Referer/X-Title headers; if all four providers fail, the caller sees
an explicit AllProvidersFailedError rather than a silently skipped chapter.
"""
import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from providers import GEMINI, GROQ, MISTRAL, OPENROUTER  # noqa: E402
from taxonomy_client import call_provider_chain, tag_chapter  # noqa: E402
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
            "os.environ",
            {
                "GEMINI_API_KEY": "invalid-key",
                "MISTRAL_API_KEY": "valid-key",
                "GROQ_API_KEY": "valid-key",
            },
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


class TestGeminiMistralGroqFallback(unittest.TestCase):
    """Issue #7 AC1: forcing a systematic failure on both Gemini and Mistral
    falls over to Groq (openai/gpt-oss-120b), which produces the expected
    JSON for the same chapter — same generic mechanism as #6, no
    Groq-specific branching in call_provider_chain."""

    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "invalid-key",
                "MISTRAL_API_KEY": "invalid-key",
                "GROQ_API_KEY": "valid-key",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_persistent_gemini_and_mistral_failure_falls_over_to_groq(self):
        groq_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "generativelanguage" in url or "mistral" in url:
                return FakeResponse(500)
            return envelope_response(groq_envelope)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            envelope, used = call_provider_chain(
                [GEMINI, MISTRAL, GROQ],
                SYSTEM_PROMPT,
                CHAPTER_MARKDOWN,
                JSON_SCHEMA,
                sleep_fn=no_sleep,
            )

        self.assertEqual(envelope, groq_envelope)
        self.assertIs(used, GROQ)
        self.assertEqual(used.model(), "openai/gpt-oss-120b")

    def test_all_three_providers_failing_raises_all_providers_failed(self):
        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(500)

        with patch("taxonomy_client.requests.post", side_effect=fake_post):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [GEMINI, MISTRAL, GROQ],
                    SYSTEM_PROMPT,
                    CHAPTER_MARKDOWN,
                    JSON_SCHEMA,
                    sleep_fn=no_sleep,
                )
        self.assertEqual(set(ctx.exception.errors), {"gemini", "mistral", "groq"})


def models_response(free_ids: list[str], paid_ids: list[str] | None = None) -> FakeResponse:
    data = [{"id": mid} for mid in free_ids] + [{"id": mid} for mid in (paid_ids or [])]
    return FakeResponse(200, {"data": data})


class TestOpenRouterFallback(unittest.TestCase):
    """Issue #8: OpenRouter as 4th and last relay behind Gemini, Mistral and
    Groq, resolving a `:free` model at runtime (never a hardcoded id) and
    sending HTTP-Referer/X-Title headers."""

    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "invalid-key",
                "MISTRAL_API_KEY": "invalid-key",
                "GROQ_API_KEY": "invalid-key",
                "OPENROUTER_API_KEY": "valid-key",
                # force runtime resolution regardless of what a local .env sets
                "OPENROUTER_MODEL": "",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_persistent_failure_on_first_three_falls_over_to_openrouter(self):
        openrouter_envelope = copy.deepcopy(VALID_ENVELOPE)

        def fake_post(url, headers=None, json=None, timeout=None):
            if "openrouter" not in url:
                return FakeResponse(500)
            self.assertEqual(json["model"], "some/free-model:free")
            self.assertEqual(headers["HTTP-Referer"], "https://github.com/EPF-MDE/GUESS.ARC")
            self.assertEqual(headers["X-Title"], "GUESS.ARC taxonomy tagger")
            return envelope_response(openrouter_envelope)

        def fake_get(url, headers=None, params=None, timeout=None):
            self.assertIn("openrouter", url)
            self.assertEqual(params, {"max_price": 0})
            self.assertEqual(headers["HTTP-Referer"], "https://github.com/EPF-MDE/GUESS.ARC")
            self.assertEqual(headers["X-Title"], "GUESS.ARC taxonomy tagger")
            return models_response(["some/free-model:free"], paid_ids=["some/paid-model"])

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            envelope, used = call_provider_chain(
                [GEMINI, MISTRAL, GROQ, OPENROUTER],
                SYSTEM_PROMPT,
                CHAPTER_MARKDOWN,
                JSON_SCHEMA,
                sleep_fn=no_sleep,
            )

        self.assertEqual(envelope, openrouter_envelope)
        self.assertIs(used, OPENROUTER)

    def test_explicit_model_env_override_skips_catalog_lookup(self):
        with patch.dict("os.environ", {"OPENROUTER_MODEL": "pinned/model:free"}):
            openrouter_envelope = copy.deepcopy(VALID_ENVELOPE)

            def fake_post(url, headers=None, json=None, timeout=None):
                self.assertEqual(json["model"], "pinned/model:free")
                return envelope_response(openrouter_envelope)

            def fake_get(url, headers=None, params=None, timeout=None):
                raise AssertionError("catalog lookup should be skipped when OPENROUTER_MODEL is set")

            with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
                "taxonomy_client.requests.get", side_effect=fake_get
            ):
                envelope, used = call_provider_chain(
                    [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
                )

            self.assertEqual(envelope, openrouter_envelope)
            self.assertIs(used, OPENROUTER)

    def test_catalog_is_resolved_once_even_when_completion_call_is_retried(self):
        """The `:free` model is resolved once per provider attempt, not on
        every in-place 429 retry of the completion call — otherwise a
        rotating catalog could switch models mid-retry-sequence and burn
        extra requests against OpenRouter's rate limit."""
        openrouter_envelope = copy.deepcopy(VALID_ENVELOPE)
        get_calls = {"n": 0}
        post_calls = {"n": 0}

        def fake_get(url, headers=None, params=None, timeout=None):
            get_calls["n"] += 1
            return models_response(["some/free-model:free"])

        def fake_post(url, headers=None, json=None, timeout=None):
            post_calls["n"] += 1
            if post_calls["n"] == 1:
                return FakeResponse(429, headers={"Retry-After": "0"})
            self.assertEqual(json["model"], "some/free-model:free")
            return envelope_response(openrouter_envelope)

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            envelope, used = call_provider_chain(
                [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
            )

        self.assertEqual(envelope, openrouter_envelope)
        self.assertIs(used, OPENROUTER)
        self.assertEqual(post_calls["n"], 2)
        self.assertEqual(get_calls["n"], 1)

    def test_empty_free_catalog_is_a_provider_call_error_not_a_bare_runtime_error(self):
        """An empty `:free` catalog must fold into AllProvidersFailedError
        (and thus into tag_chapter's explicit stderr signal) like any other
        provider failure, not escape as an unhandled RuntimeError."""

        def fake_get(url, headers=None, params=None, timeout=None):
            return models_response([], paid_ids=["some/paid-model"])

        def fake_post(url, headers=None, json=None, timeout=None):
            raise AssertionError("chat completions should never be reached with no resolvable model")

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [OPENROUTER], SYSTEM_PROMPT, CHAPTER_MARKDOWN, JSON_SCHEMA, sleep_fn=no_sleep
                )
        self.assertEqual(set(ctx.exception.errors), {"openrouter"})

    def test_all_four_providers_failing_raises_all_providers_failed(self):
        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(500)

        def fake_get(url, headers=None, params=None, timeout=None):
            return FakeResponse(500)

        with patch("taxonomy_client.requests.post", side_effect=fake_post), patch(
            "taxonomy_client.requests.get", side_effect=fake_get
        ):
            with self.assertRaises(AllProvidersFailedError) as ctx:
                call_provider_chain(
                    [GEMINI, MISTRAL, GROQ, OPENROUTER],
                    SYSTEM_PROMPT,
                    CHAPTER_MARKDOWN,
                    JSON_SCHEMA,
                    sleep_fn=no_sleep,
                )
        self.assertEqual(set(ctx.exception.errors), {"gemini", "mistral", "groq", "openrouter"})

    def test_tag_chapter_signals_explicitly_instead_of_silently_skipping(self):
        """issue #8 AC: if all four providers fail on a chapter, tag_chapter
        must print a visible error and re-raise — never silently skip it."""

        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(500)

        def fake_get(url, headers=None, params=None, timeout=None):
            return FakeResponse(500)

        stderr = io.StringIO()
        # Isolated output dir: without it, this test depends on whether
        # data/taxonomy/chapter_0001.json already exists on disk from a real
        # run — tag_chapter would then skip straight to "already exists"
        # instead of exercising the all-providers-failed path at all.
        with tempfile.TemporaryDirectory() as tmp_taxonomy_dir, patch(
            "taxonomy_client.requests.post", side_effect=fake_post
        ), patch("taxonomy_client.requests.get", side_effect=fake_get), redirect_stderr(stderr):
            with self.assertRaises(AllProvidersFailedError):
                tag_chapter(
                    1,
                    [GEMINI, MISTRAL, GROQ, OPENROUTER],
                    SYSTEM_PROMPT,
                    JSON_SCHEMA,
                    output_dir=pathlib.Path(tmp_taxonomy_dir),
                )

        self.assertIn("chapter 1", stderr.getvalue())
        self.assertIn("ALL PROVIDERS FAILED", stderr.getvalue())


class TestChapterNumberMismatchIsRejected(unittest.TestCase):
    """A model can return a schema-valid envelope that just isn't about the
    chapter it was asked for — observed for real on Groq: asked for chapter
    1's silver .md, it returned a well-formed chapter 82 envelope, seemingly
    drawn from parametric memory instead of the supplied text.
    tag_chapter must reject that (and never write it to disk) instead of
    trusting chapter.number blindly, which would silently collide with a
    later real chapter 82 in the same output_dir."""

    def setUp(self):
        patcher = patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "valid-key", "MISTRAL_API_KEY": "valid-key"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mismatched_chapter_number_raises_and_writes_nothing(self):
        wrong_chapter_envelope = copy.deepcopy(VALID_ENVELOPE)  # chapter.number == 82

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response(wrong_chapter_envelope)

        with tempfile.TemporaryDirectory() as tmp_taxonomy_dir, patch(
            "taxonomy_client.requests.post", side_effect=fake_post
        ):
            with self.assertRaises(ValueError) as ctx:
                tag_chapter(
                    1,
                    [GEMINI],
                    SYSTEM_PROMPT,
                    JSON_SCHEMA,
                    output_dir=pathlib.Path(tmp_taxonomy_dir),
                )
            self.assertIn("82", str(ctx.exception))
            self.assertEqual(list(pathlib.Path(tmp_taxonomy_dir).glob("*.json")), [])

    def test_matching_chapter_number_is_written_normally(self):
        matching_envelope = copy.deepcopy(VALID_ENVELOPE)
        matching_envelope["chapter"]["number"] = 1

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response(matching_envelope)

        with tempfile.TemporaryDirectory() as tmp_taxonomy_dir, patch(
            "taxonomy_client.requests.post", side_effect=fake_post
        ):
            out_path = tag_chapter(
                1,
                [GEMINI],
                SYSTEM_PROMPT,
                JSON_SCHEMA,
                output_dir=pathlib.Path(tmp_taxonomy_dir),
            )
            self.assertEqual(out_path.name, "chapter_0001.json")
            self.assertTrue(out_path.exists())


if __name__ == "__main__":
    unittest.main()

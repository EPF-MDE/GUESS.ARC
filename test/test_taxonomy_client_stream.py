"""Streamed (SSE) completions, used by locallm (see providers.py's LOCALLM
comment): _collect_stream must fold the `data: {...}` chunks back into the
shape of a non-streamed response, so call_provider treats both the same way.
requests.post is mocked out, so this runs with no network access.
"""
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from providers import LOCALLM  # noqa: E402
from provider_fallback import ProviderCallError  # noqa: E402
from taxonomy_client import _collect_stream, call_provider  # noqa: E402


class FakeStreamResponse:
    """Stands in for a `requests.post(..., stream=True)` response: only
    iter_lines is read, plus status_code/headers by _raise_for_provider_status."""

    def __init__(self, lines: list[str], status_code: int = 200, error: Exception | None = None):
        self.status_code = status_code
        self.headers = {}
        self._lines = lines
        self._error = error

    def iter_lines(self, decode_unicode=False):
        yield from self._lines
        if self._error is not None:
            raise self._error


def sse(chunk: dict) -> str:
    return "data: " + json.dumps(chunk)


def delta(content: str, finish_reason: str | None = None) -> str:
    return sse({"choices": [{"delta": {"content": content}, "finish_reason": finish_reason}]})


USAGE_CHUNK = sse({"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 7}})


class TestCollectStream(unittest.TestCase):
    def test_deltas_are_joined_into_one_message_with_finish_reason_and_usage(self):
        response = FakeStreamResponse([
            delta('{"a": '),
            "",  # keep-alive blank line between events
            delta("1}"),
            delta("", finish_reason="stop"),
            USAGE_CHUNK,
            "data: [DONE]",
        ])

        self.assertEqual(_collect_stream(response), {
            "choices": [{"message": {"content": '{"a": 1}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 7},
        })

    def test_non_data_lines_are_ignored(self):
        response = FakeStreamResponse([
            ": ping",
            "event: message",
            delta("ok", finish_reason="stop"),
            "data: [DONE]",
        ])

        self.assertEqual(_collect_stream(response)["choices"][0]["message"]["content"], "ok")

    def test_nothing_after_done_is_read(self):
        response = FakeStreamResponse([delta("kept", finish_reason="stop"), "data: [DONE]", delta(" dropped")])

        self.assertEqual(_collect_stream(response)["choices"][0]["message"]["content"], "kept")

    def test_null_delta_content_is_skipped(self):
        response = FakeStreamResponse([
            sse({"choices": [{"delta": {"role": "assistant", "content": None}}]}),
            delta("ok", finish_reason="stop"),
            "data: [DONE]",
        ])

        self.assertEqual(_collect_stream(response)["choices"][0]["message"]["content"], "ok")

    def test_in_band_error_chunk_is_returned_as_is(self):
        error = {"message": "model overloaded", "code": 503}
        response = FakeStreamResponse([delta("partial"), sse({"error": error}), "data: [DONE]"])

        self.assertEqual(_collect_stream(response), {"error": error})

    def test_stream_without_any_choice_has_no_choices_key(self):
        response = FakeStreamResponse([USAGE_CHUNK, "data: [DONE]"])

        self.assertEqual(_collect_stream(response), {"usage": {"prompt_tokens": 120, "completion_tokens": 7}})


class TestCallProviderStreaming(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"LOCALLM_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, response: FakeStreamResponse):
        with patch("taxonomy_client.requests.post", return_value=response) as post:
            result = call_provider(LOCALLM, "test/locallm-model", "system prompt", "chapter markdown", {"type": "object"})
        return result, post

    def test_streamed_answer_is_returned_like_a_non_streamed_one(self):
        response = FakeStreamResponse([
            delta('{"a": '), delta("1}", finish_reason="stop"), USAGE_CHUNK, "data: [DONE]",
        ])

        (content, usage), post = self.call(response)

        self.assertEqual(content, '{"a": 1}')
        self.assertEqual(usage, {"input_tokens": 120, "output_tokens": 7})
        kwargs = post.call_args.kwargs
        self.assertTrue(kwargs["stream"])
        self.assertEqual(kwargs["timeout"], LOCALLM.request_timeout_s)
        self.assertTrue(kwargs["json"]["stream"])
        self.assertEqual(kwargs["json"]["stream_options"], {"include_usage": True})

    def test_in_band_error_chunk_becomes_a_provider_call_error_with_its_code(self):
        response = FakeStreamResponse([sse({"error": {"message": "model overloaded", "code": 503}})])

        with self.assertRaises(ProviderCallError) as ctx:
            self.call(response)

        self.assertEqual(ctx.exception.status_code, 503)

    def test_connection_cut_mid_stream_becomes_a_503(self):
        response = FakeStreamResponse([delta("partial")], error=requests.exceptions.ChunkedEncodingError("cut"))

        with self.assertRaises(ProviderCallError) as ctx:
            self.call(response)

        self.assertEqual(ctx.exception.status_code, 503)

    def test_malformed_chunk_becomes_a_503(self):
        response = FakeStreamResponse(["data: {not json"])

        with self.assertRaises(ProviderCallError) as ctx:
            self.call(response)

        self.assertEqual(ctx.exception.status_code, 503)

    def test_stream_with_empty_content_is_rejected(self):
        response = FakeStreamResponse([delta("", finish_reason="length"), "data: [DONE]"])

        with self.assertRaises(ProviderCallError) as ctx:
            self.call(response)

        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()

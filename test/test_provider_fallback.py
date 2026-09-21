"""Sanity check for the generic provider fallback mechanism (issue #6). No
network access: call_fn/sleep_fn are fakes, exercising only the pure
retry/fallback logic in API/provider_fallback.py.
"""
import pathlib
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from provider_fallback import (  # noqa: E402
    AllProvidersFailedError,
    ProviderCallError,
    backoff_seconds,
    call_with_fallback,
    call_with_retry,
)


@dataclass(frozen=True)
class FakeProvider:
    name: str


class FakeSleep:
    """Records every delay it was asked to sleep for, without actually sleeping."""

    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def fail_n_times(n: int, status_code: int, retry_after: float | None = None, result="ok"):
    """A call_fn that raises ProviderCallError `n` times, then returns `result`."""
    state = {"calls": 0}

    def call_fn():
        state["calls"] += 1
        if state["calls"] <= n:
            raise ProviderCallError(status_code, retry_after=retry_after)
        return result

    return call_fn


def always_fail(status_code: int, retry_after: float | None = None):
    def call_fn():
        raise ProviderCallError(status_code, retry_after=retry_after)

    return call_fn


class TestBackoffSeconds(unittest.TestCase):
    def test_grows_exponentially(self):
        self.assertEqual(backoff_seconds(0), 1)
        self.assertEqual(backoff_seconds(1), 2)
        self.assertEqual(backoff_seconds(2), 4)

    def test_capped_at_120(self):
        self.assertEqual(backoff_seconds(10), 120)
        self.assertEqual(backoff_seconds(30), 120)


class TestCallWithRetry429(unittest.TestCase):
    def test_respects_retry_after_header_when_present(self):
        sleep = FakeSleep()
        call_fn = fail_n_times(1, status_code=429, retry_after=7.5)
        result = call_with_retry(call_fn, sleep_fn=sleep)
        self.assertEqual(result, "ok")
        self.assertEqual(sleep.calls, [7.5])

    def test_falls_back_to_capped_exponential_backoff_without_retry_after(self):
        sleep = FakeSleep()
        call_fn = fail_n_times(3, status_code=429, retry_after=None)
        result = call_with_retry(call_fn, sleep_fn=sleep)
        self.assertEqual(result, "ok")
        self.assertEqual(sleep.calls, [1, 2, 4])

    def test_retry_after_is_capped_at_120(self):
        sleep = FakeSleep()
        call_fn = fail_n_times(1, status_code=429, retry_after=9999)
        call_with_retry(call_fn, sleep_fn=sleep)
        self.assertEqual(sleep.calls, [120])

    def test_gives_up_after_max_429_attempts(self):
        sleep = FakeSleep()
        call_fn = always_fail(429, retry_after=1)
        with self.assertRaises(ProviderCallError) as ctx:
            call_with_retry(call_fn, sleep_fn=sleep, max_429_attempts=3)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(len(sleep.calls), 3)


class TestCallWithRetry5xx(unittest.TestCase):
    def test_retries_once_then_succeeds(self):
        sleep = FakeSleep()
        call_fn = fail_n_times(1, status_code=503)
        result = call_with_retry(call_fn, sleep_fn=sleep, max_5xx_attempts=1)
        self.assertEqual(result, "ok")
        self.assertEqual(len(sleep.calls), 1)

    def test_gives_up_when_failure_persists(self):
        sleep = FakeSleep()
        call_fn = always_fail(500)
        with self.assertRaises(ProviderCallError) as ctx:
            call_with_retry(call_fn, sleep_fn=sleep, max_5xx_attempts=1)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(len(sleep.calls), 1)


class TestCallWithRetryOtherErrors(unittest.TestCase):
    def test_non_429_non_5xx_error_is_not_retried(self):
        sleep = FakeSleep()
        call_fn = always_fail(401)
        with self.assertRaises(ProviderCallError):
            call_with_retry(call_fn, sleep_fn=sleep)
        self.assertEqual(sleep.calls, [])

    def test_non_provider_call_error_propagates_unretried(self):
        def call_fn():
            raise ValueError("not an HTTP failure")

        with self.assertRaises(ValueError):
            call_with_retry(call_fn, sleep_fn=FakeSleep())


class TestCallWithFallback(unittest.TestCase):
    """The generic chain mechanism: current provider first, next on failure —
    the acceptance-criteria scenario for issue #6 (Gemini fails, Mistral
    produces the result), expressed with fake providers/call_fns."""

    def test_second_provider_used_when_first_fails_persistently(self):
        gemini, mistral = FakeProvider("gemini"), FakeProvider("mistral")

        def factory(provider):
            if provider.name == "gemini":
                return always_fail(500)
            return lambda: "mistral result"

        result, used = call_with_fallback(
            [gemini, mistral], factory, sleep_fn=FakeSleep(), max_5xx_attempts=1
        )
        self.assertEqual(result, "mistral result")
        self.assertIs(used, mistral)

    def test_first_provider_used_when_it_succeeds(self):
        gemini, mistral = FakeProvider("gemini"), FakeProvider("mistral")

        def factory(provider):
            if provider.name == "gemini":
                return lambda: "gemini result"
            raise AssertionError("mistral should never be called")

        result, used = call_with_fallback([gemini, mistral], factory, sleep_fn=FakeSleep())
        self.assertEqual(result, "gemini result")
        self.assertIs(used, gemini)

    def test_raises_when_every_provider_is_exhausted(self):
        gemini, mistral = FakeProvider("gemini"), FakeProvider("mistral")

        def factory(provider):
            return always_fail(500)

        with self.assertRaises(AllProvidersFailedError) as ctx:
            call_with_fallback([gemini, mistral], factory, sleep_fn=FakeSleep(), max_5xx_attempts=1)
        self.assertEqual(set(ctx.exception.errors), {"gemini", "mistral"})

    def test_429_then_persistent_5xx_still_falls_over(self):
        # Gemini: recovers from a 429 but then hits a persistent 5xx; Mistral succeeds.
        gemini, mistral = FakeProvider("gemini"), FakeProvider("mistral")
        gemini_calls = {"n": 0}

        def gemini_call_fn():
            gemini_calls["n"] += 1
            if gemini_calls["n"] == 1:
                raise ProviderCallError(429, retry_after=1)
            raise ProviderCallError(503)

        def factory(provider):
            return gemini_call_fn if provider.name == "gemini" else (lambda: "mistral result")

        result, used = call_with_fallback(
            [gemini, mistral], factory, sleep_fn=FakeSleep(), max_5xx_attempts=1
        )
        self.assertEqual(result, "mistral result")
        self.assertIs(used, mistral)


if __name__ == "__main__":
    unittest.main()

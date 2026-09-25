"""Quota-frugal benchmark scheduling (issue #12). No network access: the
scheduler (run_benchmark.run_batch) is driven by a fake `tag_fn` that
raises the same AllProvidersFailedError/ValueError a real tag_chapter call
would, and the per-provider throttle (throttle.Throttle) by a fake clock —
same injected-dependency spirit as test_provider_fallback.py.
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from provider_fallback import AllProvidersFailedError, ProviderCallError  # noqa: E402
from providers import PROVIDERS  # noqa: E402
from quota_state import QUOTA_EXHAUSTED_STATUS, QuotaState  # noqa: E402
from run_benchmark import run_batch  # noqa: E402
from throttle import Throttle  # noqa: E402


def failure(name: str, status_code: int, retry_after: float | None = None) -> AllProvidersFailedError:
    return AllProvidersFailedError({name: ProviderCallError(status_code, retry_after=retry_after)})


class FakeTagger:
    """Records every (provider, chapter) call; `script` maps a pair to a list
    of exceptions raised on its successive calls (None = success)."""

    def __init__(self, script: dict | None = None):
        self.script = {key: list(outcomes) for key, outcomes in (script or {}).items()}
        self.calls: list[tuple[str, int]] = []

    def __call__(self, name: str, number: int):
        self.calls.append((name, number))
        outcomes = self.script.get((name, number))
        outcome = outcomes.pop(0) if outcomes else None
        if outcome is not None:
            raise outcome


class TestRoundRobin(unittest.TestCase):
    def test_every_provider_gets_chapter_n_before_anyone_gets_chapter_n_plus_one(self):
        tagger = FakeTagger()
        run_batch([1, 2], ["gemini", "mistral", "groq"], tagger, QuotaState(path=None))
        self.assertEqual(tagger.calls, [
            ("gemini", 1), ("mistral", 1), ("groq", 1),
            ("gemini", 2), ("mistral", 2), ("groq", 2),
        ])


class TestDeferred429(unittest.TestCase):
    def test_429_is_not_retried_in_place_but_deferred_to_the_end_of_the_batch(self):
        tagger = FakeTagger({("gemini", 1): [failure("gemini", 429)]})
        result = run_batch([1, 2], ["gemini", "mistral"], tagger, QuotaState(path=None))
        self.assertEqual(tagger.calls, [
            ("gemini", 1), ("mistral", 1), ("gemini", 2), ("mistral", 2),
            ("gemini", 1),  # the deferred pair, retried once after the whole batch
        ])
        self.assertEqual(result.failed, [])
        self.assertEqual(result.skipped, [])

    def test_second_429_marks_the_provider_exhausted_and_skips_its_remaining_deferred_pairs(self):
        tagger = FakeTagger({
            ("mistral", 1): [failure("mistral", 429), failure("mistral", 429)],
            ("mistral", 2): [failure("mistral", 429)],
        })
        quota = QuotaState(path=None)
        result = run_batch([1, 2], ["gemini", "mistral"], tagger, quota)
        # (mistral, 2) was deferred too, but never re-sent once (mistral, 1)'s
        # retry proved the daily quota gone.
        self.assertEqual(tagger.calls.count(("mistral", 2)), 1)
        self.assertEqual(tagger.calls.count(("mistral", 1)), 2)
        self.assertTrue(quota.is_exhausted("mistral"))
        self.assertIn("mistral", result.exhausted)
        self.assertEqual(result.failed, [("mistral", 1)])
        self.assertEqual(result.skipped, [("mistral", 2)])

    def test_long_retry_after_marks_exhausted_straight_away(self):
        tagger = FakeTagger({("gemini", 1): [failure("gemini", 429, retry_after=3600)]})
        quota = QuotaState(path=None)
        result = run_batch([1, 2, 3], ["gemini", "mistral"], tagger, quota)
        self.assertEqual([c for c in tagger.calls if c[0] == "gemini"], [("gemini", 1)])
        self.assertTrue(quota.is_exhausted("gemini"))
        self.assertEqual(result.skipped, [("gemini", 2), ("gemini", 3)])

    def test_short_retry_after_is_still_just_deferred(self):
        tagger = FakeTagger({("gemini", 1): [failure("gemini", 429, retry_after=30)]})
        quota = QuotaState(path=None)
        run_batch([1], ["gemini"], tagger, quota)
        self.assertEqual(tagger.calls, [("gemini", 1), ("gemini", 1)])
        self.assertFalse(quota.is_exhausted("gemini"))


class TestExhaustionIsPerAccount(unittest.TestCase):
    """The 3 OpenRouter models share one key and its daily cap (quota_key
    "openrouter"): once one of them proves it spent, the others must not
    keep burning 429s against it."""

    OPENROUTER_MODELS = ["openrouter-nemotron", "openrouter-nex-pro", "openrouter-dots"]

    def test_exhausting_one_openrouter_model_skips_the_ones_sharing_its_key(self):
        tagger = FakeTagger({
            ("openrouter-nemotron", 1): [failure("openrouter-nemotron", 429, retry_after=3600)],
        })
        quota = QuotaState(path=None)
        result = run_batch([1, 2], ["gemini", *self.OPENROUTER_MODELS], tagger, quota)

        self.assertEqual([c for c in tagger.calls if c[0].startswith("openrouter")], [("openrouter-nemotron", 1)])
        self.assertTrue(quota.is_exhausted("openrouter"))
        self.assertIn(("openrouter-dots", 2), result.skipped)

    def test_same_day_rerun_skips_every_model_on_the_exhausted_key(self):
        quota = QuotaState(path=None)
        quota.mark_exhausted("openrouter")
        tagger = FakeTagger()
        run_batch([1], ["gemini", *self.OPENROUTER_MODELS], tagger, quota)
        self.assertEqual(tagger.calls, [("gemini", 1)])


class TestExhaustedPersistsForTheDay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_path = pathlib.Path(self.tmpdir.name) / "quota_state.json"

    def test_same_day_rerun_skips_the_exhausted_provider_without_any_call(self):
        first = FakeTagger({("mistral", 1): [failure("mistral", 429), failure("mistral", 429)]})
        run_batch([1], ["gemini", "mistral"], first, QuotaState(path=self.state_path))

        rerun = FakeTagger()
        result = run_batch([1, 2], ["gemini", "mistral"], rerun, QuotaState(path=self.state_path))

        self.assertEqual(rerun.calls, [("gemini", 1), ("gemini", 2)])
        self.assertEqual(result.skipped, [("mistral", 1), ("mistral", 2)])


class TestOtherFailures(unittest.TestCase):
    def test_5xx_failure_is_a_plain_failure_not_deferred(self):
        # The short in-place 5xx retry happens inside tag_chapter
        # (call_with_retry); once it gives up, the pair is just failed.
        tagger = FakeTagger({("gemini", 1): [failure("gemini", 503)]})
        result = run_batch([1], ["gemini"], tagger, QuotaState(path=None))
        self.assertEqual(tagger.calls, [("gemini", 1)])
        self.assertEqual(result.failed, [("gemini", 1)])

    def test_validation_rejection_is_a_failure_and_the_run_goes_on(self):
        tagger = FakeTagger({("groq", 1): [ValueError("chapter.number=82 instead of 1")]})
        result = run_batch([1, 2], ["groq"], tagger, QuotaState(path=None))
        self.assertEqual(tagger.calls, [("groq", 1), ("groq", 2)])
        self.assertEqual(result.failed, [("groq", 1)])

    def test_local_daily_budget_exhaustion_skips_the_provider_for_the_rest_of_the_run(self):
        tagger = FakeTagger({("groq", 1): [failure("groq", QUOTA_EXHAUSTED_STATUS)]})
        quota = QuotaState(path=None)
        result = run_batch([1, 2], ["groq"], tagger, quota)
        self.assertEqual(tagger.calls, [("groq", 1)])
        self.assertEqual(result.skipped, [("groq", 1), ("groq", 2)])
        # Already persisted by the local counter itself — not duplicated as
        # a 429-style "exhausted" mark.
        self.assertFalse(quota.is_exhausted("groq"))


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class TestThrottle(unittest.TestCase):
    def test_first_call_never_waits(self):
        clock = FakeClock()
        Throttle(clock=clock, sleep_fn=clock.sleep).wait("gemini", 15)
        self.assertEqual(clock.sleeps, [])

    def test_second_call_to_the_same_key_waits_out_the_remaining_interval(self):
        clock = FakeClock()
        throttle = Throttle(clock=clock, sleep_fn=clock.sleep)
        throttle.wait("gemini", 15)
        clock.now += 4
        throttle.wait("gemini", 15)
        self.assertEqual(clock.sleeps, [11])

    def test_no_wait_once_the_interval_has_already_elapsed(self):
        clock = FakeClock()
        throttle = Throttle(clock=clock, sleep_fn=clock.sleep)
        throttle.wait("groq", 60)
        clock.now += 90
        throttle.wait("groq", 60)
        self.assertEqual(clock.sleeps, [])

    def test_keys_are_independent(self):
        clock = FakeClock()
        throttle = Throttle(clock=clock, sleep_fn=clock.sleep)
        throttle.wait("gemini", 15)
        throttle.wait("mistral", 2)
        self.assertEqual(clock.sleeps, [])


class TestMinIntervalConfig(unittest.TestCase):
    def test_every_benchmarked_provider_has_a_positive_min_interval(self):
        for name, provider in PROVIDERS.items():
            with self.subTest(provider=name):
                self.assertGreater(provider.min_interval_s, 0)

    def test_groq_interval_is_bounded_by_its_8k_tpm(self):
        self.assertGreaterEqual(PROVIDERS["groq"].min_interval_s, 60)


if __name__ == "__main__":
    unittest.main()

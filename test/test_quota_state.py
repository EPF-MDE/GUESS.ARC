"""Unit tests for the persistent daily quota counter (issue #9). No network
access, no real dates frozen — exercises quota_state.py in isolation against
a temp file, same spirit as test_provider_fallback.py."""
import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from quota_state import QUOTA_EXHAUSTED_STATUS, QuotaState  # noqa: E402


class TestQuotaStateInMemory(unittest.TestCase):
    """path=None: never touches disk, always starts empty."""

    def test_no_daily_limit_is_always_unlimited(self):
        qs = QuotaState(path=None)
        self.assertIsNone(qs.remaining("gemini", None))
        self.assertTrue(qs.has_budget("gemini", None))
        for _ in range(10):
            qs.record_success("gemini")
        self.assertTrue(qs.has_budget("gemini", None))

    def test_fresh_state_has_full_budget(self):
        qs = QuotaState(path=None)
        self.assertEqual(qs.remaining("groq", 1000), 1000)
        self.assertTrue(qs.has_budget("groq", 1000))

    def test_record_success_decrements_remaining_budget(self):
        qs = QuotaState(path=None)
        qs.record_success("openrouter")
        qs.record_success("openrouter")
        self.assertEqual(qs.remaining("openrouter", 50), 48)
        self.assertTrue(qs.has_budget("openrouter", 50))

    def test_budget_exhausted_when_count_reaches_daily_limit(self):
        qs = QuotaState(path=None)
        for _ in range(50):
            qs.record_success("openrouter")
        self.assertEqual(qs.remaining("openrouter", 50), 0)
        self.assertFalse(qs.has_budget("openrouter", 50))

    def test_count_never_goes_negative_past_the_limit(self):
        qs = QuotaState(path=None)
        for _ in range(55):
            qs.record_success("openrouter")
        self.assertEqual(qs.remaining("openrouter", 50), 0)

    def test_providers_are_tracked_independently(self):
        qs = QuotaState(path=None)
        for _ in range(50):
            qs.record_success("openrouter")
        self.assertFalse(qs.has_budget("openrouter", 50))
        self.assertTrue(qs.has_budget("groq", 1000))


class TestQuotaStatePersistence(unittest.TestCase):
    """path=<file>: persists across QuotaState instances, i.e. across a cold
    restart of the process (issue #9 AC)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_path = pathlib.Path(self.tmpdir.name) / "quota_state.json"

    def test_missing_file_starts_with_full_budget(self):
        qs = QuotaState(path=self.state_path)
        self.assertEqual(qs.remaining("groq", 1000), 1000)

    def test_record_success_writes_the_file(self):
        qs = QuotaState(path=self.state_path)
        qs.record_success("groq")
        self.assertTrue(self.state_path.exists())
        on_disk = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["groq"]["count"], 1)

    def test_state_survives_a_fresh_instance_cold_restart(self):
        qs = QuotaState(path=self.state_path)
        for _ in range(3):
            qs.record_success("groq")

        reloaded = QuotaState(path=self.state_path)
        self.assertEqual(reloaded.remaining("groq", 1000), 997)

    def test_corrupt_state_file_degrades_to_empty_instead_of_crashing(self):
        self.state_path.write_text("not json", encoding="utf-8")
        qs = QuotaState(path=self.state_path)
        self.assertEqual(qs.remaining("groq", 1000), 1000)

    def test_stale_date_resets_the_counter_for_that_provider_only(self):
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        self.state_path.write_text(
            json.dumps({"openrouter": {"date": yesterday, "count": 50}, "groq": {"date": yesterday, "count": 3}}),
            encoding="utf-8",
        )
        qs = QuotaState(path=self.state_path)
        self.assertEqual(qs.remaining("openrouter", 50), 50)
        self.assertTrue(qs.has_budget("openrouter", 50))

        qs.record_success("groq")
        on_disk = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["groq"]["count"], 1)
        self.assertEqual(on_disk["groq"]["date"], datetime.now(timezone.utc).date().isoformat())

    def test_same_day_count_is_not_reset_by_a_new_instance(self):
        """A cold restart on the *same* day must not zero the counter — only
        a genuine date change should (issue #9 AC: "n'est pas remis à zéro
        par erreur")."""
        qs = QuotaState(path=self.state_path)
        for _ in range(49):
            qs.record_success("openrouter")

        reloaded = QuotaState(path=self.state_path)
        self.assertEqual(reloaded.remaining("openrouter", 50), 1)
        self.assertTrue(reloaded.has_budget("openrouter", 50))
        reloaded.record_success("openrouter")
        self.assertFalse(reloaded.has_budget("openrouter", 50))


class TestExhaustedForTheDay(unittest.TestCase):
    """A provider marked exhausted after a repeated 429 (issue #12) stays
    skipped for the rest of the (UTC) day, across cold restarts too."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.state_path = pathlib.Path(self.tmpdir.name) / "quota_state.json"

    def test_fresh_provider_is_not_exhausted(self):
        self.assertFalse(QuotaState(path=None).is_exhausted("mistral"))

    def test_mark_exhausted_survives_a_cold_restart(self):
        QuotaState(path=self.state_path).mark_exhausted("mistral")
        reloaded = QuotaState(path=self.state_path)
        self.assertTrue(reloaded.is_exhausted("mistral"))
        self.assertFalse(reloaded.is_exhausted("gemini"))

    def test_exhausted_mark_from_a_previous_day_is_ignored(self):
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        self.state_path.write_text(
            json.dumps({"mistral": {"date": yesterday, "count": 0, "exhausted": True}}), encoding="utf-8",
        )
        self.assertFalse(QuotaState(path=self.state_path).is_exhausted("mistral"))

    def test_mark_exhausted_keeps_todays_success_count(self):
        qs = QuotaState(path=self.state_path)
        for _ in range(3):
            qs.record_success("groq")
        qs.mark_exhausted("groq")
        self.assertEqual(qs.remaining("groq", 1000), 997)

    def test_record_success_does_not_clear_the_exhausted_mark(self):
        qs = QuotaState(path=None)
        qs.mark_exhausted("groq")
        qs.record_success("groq")
        self.assertTrue(qs.is_exhausted("groq"))


class TestQuotaExhaustedStatusSentinel(unittest.TestCase):
    def test_is_not_a_429_or_5xx_status(self):
        self.assertNotEqual(QUOTA_EXHAUSTED_STATUS, 429)
        self.assertFalse(500 <= QUOTA_EXHAUSTED_STATUS < 600)


if __name__ == "__main__":
    unittest.main()

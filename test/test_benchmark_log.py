"""Unit tests for the benchmark journal (issue #10), no network access —
same spirit as test_quota_state.py: pure logic plus a temp-file round trip
for the on-disk JSONL format.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from benchmark_log import VALIDATION_REJECTED, BenchmarkLog, CallLogEntry, format_report, load_entries, summarize  # noqa: E402


class TestBenchmarkLogPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.log_path = pathlib.Path(self.tmpdir.name) / "benchmark_log.jsonl"

    def test_record_appends_one_json_line_per_call(self):
        log = BenchmarkLog(path=self.log_path)
        log.record(CallLogEntry(chapter=1, provider="gemini", model="gemini-2.5-flash", success=True,
                                 input_tokens=100, output_tokens=50))
        log.record(CallLogEntry(chapter=2, provider="gemini", model="gemini-2.5-flash", success=False,
                                 error_code=429, error_message="rate limited"))

        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["chapter"], 1)
        self.assertEqual(first["provider"], "gemini")
        self.assertEqual(first["input_tokens"], 100)
        self.assertEqual(first["output_tokens"], 50)
        self.assertTrue(first["success"])
        self.assertIn("timestamp", first)

        second = json.loads(lines[1])
        self.assertFalse(second["success"])
        self.assertEqual(second["error_code"], 429)

    def test_entries_persist_across_a_fresh_instance_reading_the_same_file(self):
        log = BenchmarkLog(path=self.log_path)
        log.record(CallLogEntry(chapter=1, provider="mistral", model="mistral-small-latest", success=True,
                                 input_tokens=10, output_tokens=5))

        reloaded = load_entries(self.log_path)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0]["provider"], "mistral")

    def test_in_memory_log_with_no_path_never_touches_disk(self):
        log = BenchmarkLog(path=None)
        log.record(CallLogEntry(chapter=1, provider="gemini", model="m", success=True))
        self.assertEqual(len(log.entries), 1)
        self.assertFalse(self.log_path.exists())

    def test_load_entries_on_missing_file_returns_empty_list(self):
        missing = pathlib.Path(self.tmpdir.name) / "does_not_exist.jsonl"
        self.assertEqual(load_entries(missing), [])


class TestSummarize(unittest.TestCase):
    def test_aggregates_per_provider_counts_and_token_stats(self):
        entries = [
            {"provider": "gemini", "success": True, "input_tokens": 100, "output_tokens": 50},
            {"provider": "gemini", "success": True, "input_tokens": 200, "output_tokens": 150},
            {"provider": "gemini", "success": False, "error_code": 429},
            {"provider": "mistral", "success": True, "input_tokens": 40, "output_tokens": 20},
        ]

        summary = summarize(entries)

        gemini = summary["gemini"]
        self.assertEqual(gemini["calls"], 3)
        self.assertEqual(gemini["successes"], 2)
        self.assertEqual(gemini["failures"], 1)
        self.assertEqual(gemini["error_codes"], {"429": 1})
        self.assertEqual(gemini["input_tokens_min"], 100)
        self.assertEqual(gemini["input_tokens_max"], 200)
        self.assertEqual(gemini["input_tokens_avg"], 150.0)
        self.assertEqual(gemini["output_tokens_avg"], 100.0)

        mistral = summary["mistral"]
        self.assertEqual(mistral["calls"], 1)
        self.assertEqual(mistral["input_tokens_min"], 40)

    def test_provider_with_only_failures_has_none_token_stats(self):
        entries = [{"provider": "openrouter", "success": False, "error_code": 500}]
        summary = summarize(entries)
        self.assertEqual(summary["openrouter"]["input_tokens_min"], None)
        self.assertEqual(summary["openrouter"]["input_tokens_avg"], None)

    def test_empty_entries_produce_empty_summary(self):
        self.assertEqual(summarize([]), {})

    def test_validation_rejections_are_counted_apart_from_network_calls(self):
        """issue #12: a 200 whose envelope tag_chapter then rejected is a
        successful *call* but no *file* — the report must tell them apart."""
        entries = [
            {"provider": "groq", "success": True, "input_tokens": 100, "output_tokens": 50},
            {"provider": "groq", "success": True, "input_tokens": 100, "output_tokens": 50},
            {"provider": "groq", "success": False, "error_code": VALIDATION_REJECTED},
            {"provider": "groq", "success": False, "error_code": 429},
        ]

        groq = summarize(entries)["groq"]

        self.assertEqual(groq["calls"], 3)
        self.assertEqual(groq["successes"], 2)
        self.assertEqual(groq["failures"], 1)
        self.assertEqual(groq["error_codes"], {"429": 1})
        self.assertEqual(groq["rejected"], 1)
        self.assertEqual(groq["files_written"], 1)


class TestFormatReport(unittest.TestCase):
    def test_report_mentions_every_provider_and_its_call_count(self):
        summary = summarize([
            {"provider": "gemini", "success": True, "input_tokens": 10, "output_tokens": 5},
            {"provider": "groq", "success": False, "error_code": 429},
        ])
        report = format_report(summary)
        self.assertIn("gemini:", report)
        self.assertIn("groq:", report)
        self.assertIn("calls: 1", report)
        self.assertIn("429", report)

    def test_report_shows_files_written_and_rejections(self):
        report = format_report(summarize([
            {"provider": "groq", "success": True, "input_tokens": 10, "output_tokens": 5},
            {"provider": "groq", "success": False, "error_code": VALIDATION_REJECTED},
        ]))
        self.assertIn("files written: 0", report)
        self.assertIn("rejected by validation: 1", report)

    def test_empty_summary_reports_no_calls_logged(self):
        self.assertEqual(format_report({}), "(no calls logged)")


if __name__ == "__main__":
    unittest.main()

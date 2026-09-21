"""Tests for the benchmark run script (issue #10).

default_batch() reads the real data/silver/ directory (no network, no API
key needed) — same "sanity check against real bronze/silver data" spirit as
test_silver_format.py. The provider-call logging path is covered separately
in test_taxonomy_client_benchmark_log.py, with requests mocked out.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from run_benchmark import default_batch  # noqa: E402
from taxonomy_client import SILVER_DIR  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

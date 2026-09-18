"""Sanity check for data/bronze/chapters.jsonl (issue #4). No network access."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sanity_checks import validate_bronze_record

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BRONZE_PATH = REPO_ROOT / "data" / "bronze" / "chapters.jsonl"

VALID_RECORD = {
    "number": 1,
    "revid": 2131942,
    "timestamp": "2026-09-06T18:33:22Z",
    "wikitext": "some wikitext",
}


class TestValidateBronzeRecord(unittest.TestCase):
    """Unit tests for the pure validator, against synthetic fixtures."""

    def test_valid_record_has_no_errors(self):
        self.assertEqual(validate_bronze_record(VALID_RECORD, line_no=1), [])

    def test_missing_field_is_reported(self):
        record = dict(VALID_RECORD)
        del record["wikitext"]
        errors = validate_bronze_record(record, line_no=5)
        self.assertTrue(any("wikitext" in e and "line 5" in e for e in errors))

    def test_wrong_type_is_reported(self):
        record = dict(VALID_RECORD, number="1")
        errors = validate_bronze_record(record, line_no=2)
        self.assertTrue(any("number" in e and "str" in e for e in errors))

    def test_non_positive_number_is_reported(self):
        record = dict(VALID_RECORD, number=0)
        errors = validate_bronze_record(record, line_no=3)
        self.assertTrue(any("positive" in e for e in errors))

    def test_empty_wikitext_is_reported(self):
        record = dict(VALID_RECORD, wikitext="   ")
        errors = validate_bronze_record(record, line_no=4)
        self.assertTrue(any("empty" in e for e in errors))

    def test_malformed_timestamp_is_reported(self):
        record = dict(VALID_RECORD, timestamp="Sept 6 2026")
        errors = validate_bronze_record(record, line_no=6)
        self.assertTrue(any("timestamp" in e and "ISO-8601" in e for e in errors))

    def test_non_object_record_is_reported(self):
        errors = validate_bronze_record(["not", "an", "object"], line_no=7)
        self.assertTrue(any("JSON object" in e for e in errors))


class TestBronzeDataOnDisk(unittest.TestCase):
    """Integration sanity check against the real data/bronze/ corpus."""

    @classmethod
    def setUpClass(cls):
        if not BRONZE_PATH.is_file():
            raise unittest.SkipTest(f"{BRONZE_PATH} does not exist")

    def test_every_line_is_valid_json_and_matches_expected_shape(self):
        errors = []
        seen_numbers = []
        with BRONZE_PATH.open(encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                raw_line = raw_line.rstrip("\n")
                if not raw_line.strip():
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as e:
                    errors.append(f"line {line_no}: invalid JSON ({e})")
                    continue
                errors.extend(validate_bronze_record(record, line_no))
                if isinstance(record, dict) and "number" in record:
                    seen_numbers.append(record["number"])

        duplicates = {n for n in seen_numbers if seen_numbers.count(n) > 1}
        if duplicates:
            errors.append(f"duplicate chapter numbers found: {sorted(duplicates)}")

        self.assertEqual(
            errors, [],
            "data/bronze/chapters.jsonl has malformed record(s):\n" + "\n".join(errors)
        )


if __name__ == "__main__":
    unittest.main()

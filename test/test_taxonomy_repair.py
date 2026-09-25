"""Repair of malformed LLM taxonomy output before validation (issue #13).

Unit tests for API/taxonomy_repair.py against the real
docs/taxonomy-schema.json, plus tag_chapter end-to-end with requests.post
mocked out (no network), same spirit as test_taxonomy_client_fights_index.py.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from benchmark_log import INVALID_JSON, VALIDATION_REJECTED, BenchmarkLog, format_report, load_entries, summarize  # noqa: E402
from providers import GROQ  # noqa: E402
from quota_state import QuotaState  # noqa: E402
from taxonomy_client import load_json_schema, tag_chapter  # noqa: E402
from taxonomy_core import validate_taxonomy_envelope  # noqa: E402
from taxonomy_repair import InvalidModelJSON, parse_model_json, repair_to_schema  # noqa: E402

from test_taxonomy_client_fallback import setUpModule, tearDownModule, FakeResponse  # noqa: E402,F401
from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402

SCHEMA = load_json_schema()


def envelope(**chapter_overrides) -> dict:
    env = copy.deepcopy(VALID_ENVELOPE)
    env["chapter"].update(chapter_overrides)
    return env


class TestParseModelJson(unittest.TestCase):
    def test_valid_json_needs_no_repair(self):
        value, repairs = parse_model_json('{"a": 1}')
        self.assertEqual(value, {"a": 1})
        self.assertEqual(repairs, [])

    def test_markdown_fence_is_stripped(self):
        value, repairs = parse_model_json('```json\n{"a": 1}\n```')
        self.assertEqual(value, {"a": 1})
        self.assertEqual([r.kind for r in repairs], ["strip_markdown_fence"])

    def test_text_around_the_object_is_stripped(self):
        value, repairs = parse_model_json('Here is the JSON:\n{"a": 1}\nHope it helps!')
        self.assertEqual(value, {"a": 1})
        self.assertEqual([r.kind for r in repairs], ["strip_surrounding_text"])

    def test_unquoted_key_is_repaired(self):
        # nemotron: "Expecting property name enclosed in double quotes: line 2 column 1"
        value, repairs = parse_model_json('{\nschema_version: 1}')
        self.assertEqual(value, {"schema_version": 1})
        self.assertEqual([r.kind for r in repairs], ["json5_syntax"])

    def test_trailing_comma_single_quotes_and_comments_are_repaired(self):
        value, _ = parse_model_json("{'a': [1, 2,], // note\n 'b': 'x',}")
        self.assertEqual(value, {"a": [1, 2], "b": "x"})

    def test_truncated_text_is_not_completed(self):
        # openrouter-dots: "Unterminated string" — closing it would invent data.
        with self.assertRaises(InvalidModelJSON) as ctx:
            parse_model_json('{"chapter": {"arc": "Romance Da')
        self.assertIn("Romance Da", ctx.exception.excerpt)

    def test_plain_prose_is_invalid(self):
        with self.assertRaises(InvalidModelJSON):
            parse_model_json("Sorry, I can't help with that.")


class TestRepairToSchema(unittest.TestCase):
    def test_valid_envelope_is_untouched(self):
        value, repairs = repair_to_schema(copy.deepcopy(VALID_ENVELOPE), SCHEMA)
        self.assertEqual(value, VALID_ENVELOPE)
        self.assertEqual(repairs, [])

    def test_string_winner_becomes_a_one_item_list(self):
        # groq: interactions/0/winner: 'red-hair-pirates' is not of type 'array', 'null'
        env = envelope()
        env["interactions"][0]["winner"] = "red-hair-pirates"
        value, repairs = repair_to_schema(env, SCHEMA)
        self.assertEqual(value["interactions"][0]["winner"], ["red-hair-pirates"])
        self.assertEqual(validate_taxonomy_envelope(value, SCHEMA), [])
        self.assertEqual(
            [r.to_dict() for r in repairs],
            [{"path": "interactions/0/winner", "kind": "string_to_array",
              "before": "red-hair-pirates", "after": ["red-hair-pirates"]}],
        )

    def test_null_strings_become_null_on_nullable_fields(self):
        env = envelope(yonko_name="null")
        env["interactions"][0]["winner"] = ""
        value, repairs = repair_to_schema(env, SCHEMA)
        self.assertIsNone(value["chapter"]["yonko_name"])
        self.assertIsNone(value["interactions"][0]["winner"])
        self.assertEqual({r.kind for r in repairs}, {"string_null_to_null", "empty_string_to_null"})

    def test_empty_string_stays_on_a_nullable_string_field(self):
        value, repairs = repair_to_schema(envelope(cliffhanger_type=""), SCHEMA)
        self.assertEqual(value["chapter"]["cliffhanger_type"], "")
        self.assertEqual(repairs, [])

    def test_numeric_strings_and_integral_floats_become_integers(self):
        value, repairs = repair_to_schema(envelope(number="82", confidence=92.0), SCHEMA)
        self.assertEqual(value["chapter"]["number"], 82)
        self.assertEqual(value["chapter"]["confidence"], 92)
        self.assertEqual({r.path for r in repairs}, {"chapter/number", "chapter/confidence"})

    def test_boolean_strings_become_booleans(self):
        value, _ = repair_to_schema(envelope(color_spread="true"), SCHEMA)
        self.assertIs(value["chapter"]["color_spread"], True)

    def test_ambiguous_values_are_left_for_validation_to_reject(self):
        env = envelope(tension_level=15, confidence="high")
        del env["chapter"]["arc"]
        env["characters"][0]["emotional_state"] = None
        env["characters"][0]["bounty_amount"] = 30000000
        env["interactions"][0]["type"] = "dialogue"
        before = copy.deepcopy(env)

        value, repairs = repair_to_schema(env, SCHEMA)

        self.assertEqual(value, before)
        self.assertEqual(repairs, [])
        errors = "\n".join(validate_taxonomy_envelope(value, SCHEMA))
        for expected in ("tension_level", "'arc' is a required property", "emotional_state",
                         "bounty_amount", "'fight' was expected", "chapter/confidence"):
            self.assertIn(expected, errors)


class TestTagChapterRepairsBeforeValidating(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GROQ_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = pathlib.Path(self.tmpdir.name)
        self.silver_dir = root / "silver"
        self.taxonomy_dir = root / "taxonomy"
        self.silver_dir.mkdir()
        (self.silver_dir / "chapter_0082.md").write_text("chapter text", encoding="utf-8")
        self.log = BenchmarkLog(path=root / "benchmark_log.jsonl")
        self.quota = QuotaState(path=None)

    def _tag(self, content: str):
        def fake_post(url, headers=None, json=None, timeout=None):
            return FakeResponse(200, {
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            })

        with patch("taxonomy_client.SILVER_DIR", self.silver_dir), patch(
            "taxonomy_client.TAXONOMY_DIR", self.taxonomy_dir
        ), patch("taxonomy_client.requests.post", side_effect=fake_post):
            return tag_chapter(82, [GROQ], "system prompt", SCHEMA, quota=self.quota, log=self.log)

    def test_groq_string_winner_is_written_as_a_list_and_journaled(self):
        env = envelope()
        env["interactions"][0]["winner"] = "red-hair-pirates"

        out_path = self._tag(json.dumps(env))

        written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(written["interactions"][0]["winner"], ["red-hair-pirates"])
        [entry] = load_entries(self.log.path)
        self.assertTrue(entry["success"])
        self.assertEqual(entry["repairs"][0]["path"], "interactions/0/winner")

    def test_unquoted_key_and_trailing_comma_are_repaired_then_written(self):
        text = json.dumps(envelope(), indent=2).replace('"schema_version"', "schema_version", 1)
        text = text[:-1].rstrip() + ",\n}"

        out_path = self._tag(text)

        self.assertIsNotNone(out_path)
        self.assertEqual(validate_taxonomy_envelope(json.loads(out_path.read_text(encoding="utf-8")), SCHEMA), [])

    def test_unreadable_text_is_logged_as_invalid_json_and_counted_in_quota(self):
        with self.assertRaises(InvalidModelJSON):
            self._tag('{"chapter": {"arc": "Romance Da')

        [entry] = load_entries(self.log.path)
        self.assertFalse(entry["success"])
        self.assertEqual(entry["error_code"], INVALID_JSON)
        self.assertEqual(entry["model"], GROQ.model())
        self.assertEqual((entry["input_tokens"], entry["output_tokens"]), (100, 50))
        self.assertIn("Romance Da", entry["error_message"])
        self.assertEqual(self.quota.remaining(GROQ.quota_name, 10), 9)
        self.assertFalse(self.taxonomy_dir.exists())

    def test_missing_required_field_is_still_rejected(self):
        env = envelope()
        del env["interactions"][0]["winner"]

        with self.assertRaises(ValueError):
            self._tag(json.dumps(env))

        self.assertEqual([e["error_code"] for e in load_entries(self.log.path)], [None, VALIDATION_REJECTED])
        self.assertFalse(self.taxonomy_dir.exists())

    def test_out_of_enum_value_is_still_rejected(self):
        env = envelope()
        env["interactions"][0]["type"] = "dialogue"

        with self.assertRaises(ValueError):
            self._tag(json.dumps(env))

        self.assertEqual(load_entries(self.log.path)[-1]["error_code"], VALIDATION_REJECTED)


class TestReportSplitsOutcomes(unittest.TestCase):
    def test_first_try_repaired_and_rejected_are_counted_per_provider(self):
        repair = {"path": "interactions/0/winner", "kind": "string_to_array", "before": "x", "after": ["x"]}
        entries = [
            {"provider": "groq", "chapter": 1, "success": True, "repairs": []},
            {"provider": "groq", "chapter": 2, "success": True, "repairs": [repair]},
            {"provider": "groq", "chapter": 3, "success": True, "repairs": [repair]},
            {"provider": "groq", "chapter": 3, "success": False, "error_code": VALIDATION_REJECTED},
            {"provider": "groq", "chapter": 4, "success": False, "error_code": INVALID_JSON,
             "input_tokens": 100, "output_tokens": 50},
            {"provider": "groq", "chapter": 5, "success": True},  # pre-#13 entry, no repairs field
        ]

        groq = summarize(entries)["groq"]

        self.assertEqual(groq["first_try_valid"], 2)
        self.assertEqual(groq["repaired"], 1)
        self.assertEqual(groq["invalid_json"], 1)
        self.assertEqual(groq["total_rejected"], 2)
        self.assertEqual(groq["files_written"], 3)
        self.assertEqual(groq["calls"], 5)
        self.assertEqual(groq["input_tokens_max"], 100)
        self.assertIn("first-try valid: 2, repaired: 1, rejected: 2", format_report({"groq": groq}))


if __name__ == "__main__":
    unittest.main()

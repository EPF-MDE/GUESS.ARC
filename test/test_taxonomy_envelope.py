"""Sanity check for the taxonomy tagging client (issue #5). No network access.

Covers the two things the acceptance criteria call out as testable offline:
- validating a taxonomy envelope against docs/taxonomy-schema.json (schema v1)
- reassociating a result by chapter.number, never by send order
"""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from taxonomy_core import (  # noqa: E402
    build_system_prompt,
    extract_taxonomy_definition,
    taxonomy_output_filename,
    validate_taxonomy_envelope,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
JSON_SCHEMA_PATH = REPO_ROOT / "docs" / "taxonomy-schema.json"
SCHEMA_DOC_PATH = REPO_ROOT / "docs" / "taxonomy-schema.md"

VALID_ENVELOPE = {
    "schema_version": 1,
    "chapter": {
        "number": 82,
        "arc": "Arlong Park Arc",
        "chapter_mood": "tense",
        "tension_level": 8,
        "locations": ["Arlong Park"],
        "location_change": False,
        "sea_region": "East Blue",
        "cliffhanger_type": "battle_escalation",
        "marines_present": False,
        "yonko_present": False,
        "yonko_name": None,
        "shichibukai_present": False,
        "world_government_present": False,
        "revolutionary_army_present": False,
        "road_poneglyph_found": False,
        "ancient_weapon_mentioned": False,
        "will_of_d_mentioned": False,
        "color_spread": False,
        "new_arc_starts": False,
        "arc_ends": False,
        "new_alliance_formed": False,
        "confidence": 92,
    },
    "characters": [
        {
            "character_id": "monkey-d-luffy",
            "role": "protagonist",
            "affiliation": "straw-hat-pirates",
            "health_state": "healthy",
            "emotional_state": "determined",
            "technique_revealed": None,
            "haki_used": [],
            "power_used": "Gomu Gomu no Mi",
            "dies": False,
            "death_type": None,
            "bounty_revealed": False,
            "major_decision": True,
            "arc_goal_progress": "progressing",
            "has_flashback": False,
            "confidence": 90,
        }
    ],
    "interactions": [
        {
            "type": "fight",
            "fight_id": "fight-0034",
            "battle": {"sides": [["monkey-d-luffy"], ["arlong"]]},
            "duels": [
                {"participants": ["roronoa-zoro", "hatchan"], "confidence": 85}
            ],
            "ends_this_chapter": False,
            "winner": None,
        }
    ],
}


class TestValidateTaxonomyEnvelope(unittest.TestCase):
    """Unit tests for the pure schema validator, against synthetic fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(JSON_SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_valid_envelope_has_no_errors(self):
        self.assertEqual(validate_taxonomy_envelope(VALID_ENVELOPE, self.schema), [])

    def test_wrong_schema_version_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["schema_version"] = 2
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_missing_top_level_field_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        del envelope["interactions"]
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("interactions" in e for e in errors))

    def test_missing_chapter_field_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        del envelope["chapter"]["confidence"]
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("confidence" in e for e in errors))

    def test_out_of_range_confidence_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["confidence"] = 101
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("confidence" in e for e in errors))

    def test_wrong_type_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = "82"
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("number" in e for e in errors))

    def test_unknown_field_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["unexpected_field"] = "surprise"
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(errors)

    def test_wrong_interaction_type_is_reported(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["interactions"][0]["type"] = "alliance"
        errors = validate_taxonomy_envelope(envelope, self.schema)
        self.assertTrue(any("type" in e for e in errors))


class TestTaxonomyOutputFilename(unittest.TestCase):
    """Reassociation by chapter.number — never by send order (issue #5)."""

    def test_filename_derived_from_chapter_number(self):
        self.assertEqual(taxonomy_output_filename(VALID_ENVELOPE), "chapter_0082.json")

    def test_filename_is_zero_padded_like_silver(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 7
        self.assertEqual(taxonomy_output_filename(envelope), "chapter_0007.json")

    def test_reassociation_ignores_a_mismatched_requested_number(self):
        # Even if the caller believed it was sending chapter 1, the response's
        # own chapter.number is what decides the output filename.
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 999
        self.assertEqual(taxonomy_output_filename(envelope), "chapter_0999.json")

    def test_missing_chapter_number_raises(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        del envelope["chapter"]["number"]
        with self.assertRaises(ValueError):
            taxonomy_output_filename(envelope)

    def test_non_positive_chapter_number_raises(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 0
        with self.assertRaises(ValueError):
            taxonomy_output_filename(envelope)


class TestExtractTaxonomyDefinition(unittest.TestCase):
    """The system-prompt block is sourced from docs/taxonomy-schema.md, not hardcoded."""

    def test_extracts_section_1_from_synthetic_doc(self):
        doc = (
            "# Taxonomy schema\n\n"
            "intro text\n\n"
            "## 1. Chapter taxonomy file\n\n"
            "the real content\n\n"
            "## 2. Fights index\n\n"
            "fights index content\n"
        )
        definition = extract_taxonomy_definition(doc)
        self.assertIn("the real content", definition)
        self.assertNotIn("fights index content", definition)

    def test_missing_section_raises(self):
        with self.assertRaises(ValueError):
            extract_taxonomy_definition("# Taxonomy schema\n\nno numbered sections here\n")

    def test_extracts_from_real_taxonomy_schema_doc(self):
        if not SCHEMA_DOC_PATH.is_file():
            raise unittest.SkipTest(f"{SCHEMA_DOC_PATH} does not exist")
        definition = extract_taxonomy_definition(SCHEMA_DOC_PATH.read_text(encoding="utf-8"))
        self.assertIn("chapter_0082.json", definition)
        self.assertNotIn("fights_index.json", definition)

    def test_build_system_prompt_injects_under_expected_heading(self):
        prompt = build_system_prompt("some taxonomy definition")
        self.assertIn("## DÉFINITION TAXONOMIE", prompt)
        self.assertIn("some taxonomy definition", prompt)


if __name__ == "__main__":
    unittest.main()

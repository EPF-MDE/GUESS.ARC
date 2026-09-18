"""Sanity check for data/silver/chapter_NNNN.md (issue #4). No network access."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sanity_checks import validate_silver_content

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SILVER_DIR = REPO_ROOT / "data" / "silver"

VALID_CONTENT = """---
chapter: 1
title: "Romance Dawn"
arc: "Romance Dawn Arc"
characters:
  - name: "Monkey D. Luffy"
    faction: "Straw Hat Pirates"
    on_panel: true
---

# Chapter 1

## Short Summary

Something happens.

## Long Summary

Something happens, in detail.

## Chapter Notes

- A note.
"""


class TestValidateSilverContent(unittest.TestCase):
    """Unit tests for the pure validator, against synthetic fixtures."""

    def test_valid_content_has_no_errors(self):
        self.assertEqual(validate_silver_content(VALID_CONTENT, "chapter_0001.md"), [])

    def test_missing_front_matter_is_reported(self):
        errors = validate_silver_content("# Just a body\n", "chapter_0002.md")
        self.assertTrue(any("front-matter" in e and "chapter_0002.md" in e for e in errors))

    def test_missing_chapter_number_is_reported(self):
        content = VALID_CONTENT.replace("chapter: 1\n", "")
        errors = validate_silver_content(content, "chapter_0003.md")
        self.assertTrue(any("'chapter:'" in e for e in errors))

    def test_missing_title_is_reported(self):
        content = VALID_CONTENT.replace('title: "Romance Dawn"\n', "")
        errors = validate_silver_content(content, "chapter_0004.md")
        self.assertTrue(any("'title:'" in e for e in errors))

    def test_missing_arc_is_reported(self):
        content = VALID_CONTENT.replace('arc: "Romance Dawn Arc"\n', "")
        errors = validate_silver_content(content, "chapter_0005.md")
        self.assertTrue(any("'arc:'" in e for e in errors))

    def test_empty_characters_list_is_reported(self):
        content = VALID_CONTENT.replace(
            '  - name: "Monkey D. Luffy"\n    faction: "Straw Hat Pirates"\n    on_panel: true\n', ""
        )
        errors = validate_silver_content(content, "chapter_0006.md")
        self.assertTrue(any("'characters:'" in e for e in errors))

    def test_missing_section_is_reported(self):
        content = VALID_CONTENT.replace("## Chapter Notes\n\n- A note.\n", "")
        errors = validate_silver_content(content, "chapter_0007.md")
        self.assertTrue(any("Chapter Notes" in e and "chapter_0007.md" in e for e in errors))


class TestSilverDataOnDisk(unittest.TestCase):
    """Integration sanity check against the real data/silver/ corpus."""

    @classmethod
    def setUpClass(cls):
        if not SILVER_DIR.is_dir():
            raise unittest.SkipTest(f"{SILVER_DIR} does not exist")
        cls.files = sorted(SILVER_DIR.glob("chapter_*.md"))
        if not cls.files:
            raise unittest.SkipTest(f"no chapter_*.md files found in {SILVER_DIR}")

    def test_every_chapter_file_matches_expected_format(self):
        errors = []
        for path in self.files:
            text = path.read_text(encoding="utf-8")
            errors.extend(validate_silver_content(text, path.name))

        self.assertEqual(
            errors, [],
            f"{len(self.files)} silver chapter(s) checked, malformed file(s) found:\n" + "\n".join(errors)
        )


if __name__ == "__main__":
    unittest.main()

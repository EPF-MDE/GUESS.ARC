"""Sanity check for data/silver/chapter_NNNN.md. No network access."""
import pathlib
import tempfile
import unittest

from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import SilverChapter, read_chapter, write_markdown
from guess_arc.ingestion.validation import validate_silver_content
from guess_arc.paths import DATA_DIR

SILVER_DIR = DATA_DIR / "silver"

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

    def test_empty_title_placeholder_is_reported(self):
        # The silver writer emits `title: ""` when its parser fails to extract
        # a title — this must be caught, not treated as a present value.
        content = VALID_CONTENT.replace('title: "Romance Dawn"', 'title: ""')
        errors = validate_silver_content(content, "chapter_0004b.md")
        self.assertTrue(any("'title:'" in e for e in errors))

    def test_missing_arc_is_reported(self):
        content = VALID_CONTENT.replace('arc: "Romance Dawn Arc"\n', "")
        errors = validate_silver_content(content, "chapter_0005.md")
        self.assertTrue(any("'arc:'" in e for e in errors))

    def test_empty_arc_placeholder_is_reported(self):
        content = VALID_CONTENT.replace('arc: "Romance Dawn Arc"', 'arc: ""')
        errors = validate_silver_content(content, "chapter_0005b.md")
        self.assertTrue(any("'arc:'" in e for e in errors))

    def test_empty_characters_list_is_reported(self):
        content = VALID_CONTENT.replace(
            '  - name: "Monkey D. Luffy"\n    faction: "Straw Hat Pirates"\n    on_panel: true\n', ""
        )
        errors = validate_silver_content(content, "chapter_0006.md")
        self.assertTrue(any("'characters:'" in e for e in errors))

    def test_character_with_empty_name_placeholder_is_reported(self):
        content = VALID_CONTENT.replace('name: "Monkey D. Luffy"', 'name: ""')
        errors = validate_silver_content(content, "chapter_0006b.md")
        self.assertTrue(any("'characters:'" in e for e in errors))

    def test_missing_section_is_reported(self):
        content = VALID_CONTENT.replace("## Chapter Notes\n\n- A note.\n", "")
        errors = validate_silver_content(content, "chapter_0007.md")
        self.assertTrue(any("Chapter Notes" in e and "chapter_0007.md" in e for e in errors))


LONG = "Luffy meets Chouchou.\n\nBuggy fires at the town."


def written_chapter(**overrides) -> Chapter:
    values = dict(
        number=12,
        title='The "Dog" \\ part 1',
        jname="犬",
        arc="Orange Town Arc",
        revision_id=4321,
        revised_at="2026-11-01T00:00:00Z",
        characters=[
            {"name": "Monkey D. Luffy", "faction": "Straw Hat Pirates", "on_panel": True},
            {"name": "Shanks", "faction": None, "on_panel": False},
        ],
        notes=["First appearance of Chouchou.", "Second note."],
        short_summary="Luffy meets a dog.",
        long_summary=LONG,
        complete=True,
    )
    values.update(overrides)
    return Chapter(**values)


class TestReadChapter(unittest.TestCase):
    """read_chapter relit ce que write_markdown écrit."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def round_trip(self, ch: Chapter) -> SilverChapter:
        return read_chapter(write_markdown(ch, self.dir))

    def rewrite(self, path: pathlib.Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_round_trip_gives_back_the_fields_and_sections(self):
        self.assertEqual(self.round_trip(written_chapter()), SilverChapter(
            number=12,
            title='The "Dog" \\ part 1',
            jname="犬",
            arc="Orange Town Arc",
            revision_id=4321,
            revised_at="2026-11-01T00:00:00Z",
            complete=True,
            character_count=2,
            characters=[
                {"name": "Monkey D. Luffy", "faction": "Straw Hat Pirates", "on_panel": True},
                {"name": "Shanks", "faction": "", "on_panel": False},
            ],
            short_summary="Luffy meets a dog.",
            long_summary=LONG,
            notes=["First appearance of Chouchou.", "Second note."],
        ))

    def test_incomplete_chapter_is_read_as_incomplete(self):
        self.assertFalse(self.round_trip(written_chapter(complete=False)).complete)

    def test_absent_sections_are_read_as_empty(self):
        read = self.round_trip(written_chapter(short_summary="", long_summary="", notes=[]))
        self.assertEqual((read.short_summary, read.long_summary, read.notes), ("", "", []))

    def test_windows_line_endings_are_accepted(self):
        path = write_markdown(written_chapter(), self.dir)
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(read_chapter(path).long_summary, LONG)

    def test_missing_front_matter_raises_naming_the_file(self):
        path = self.dir / "chapter_0012.md"
        path.write_text("# Chapter 12\n\n## Long Summary\n\nText.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chapter_0012.md.*front-matter"):
            read_chapter(path)

    def test_missing_required_field_raises_naming_the_file_and_field(self):
        for field, line in (("chapter", "chapter: 12\n"), ("arc", 'arc: "Orange Town Arc"\n'),
                            ("revision_id", "revision_id: 4321\n"), ("complete", "complete: true\n")):
            with self.subTest(field=field):
                path = write_markdown(written_chapter(), self.dir)
                self.rewrite(path, line, "")
                with self.assertRaisesRegex(ValueError, f"chapter_0012.md.*'{field}'"):
                    read_chapter(path)

    def test_invalid_field_value_raises_naming_the_file_and_field(self):
        for old, new in (("revision_id: 4321", "revision_id: abc"), ("complete: true", "complete: yes")):
            with self.subTest(new=new):
                path = write_markdown(written_chapter(), self.dir)
                self.rewrite(path, old, new)
                with self.assertRaisesRegex(ValueError, f"chapter_0012.md.*'{new.split(':')[0]}'"):
                    read_chapter(path)

    def test_missing_section_raises_naming_the_file_and_section(self):
        path = write_markdown(written_chapter(), self.dir)
        self.rewrite(path, "## Chapter Notes", "## Other")
        with self.assertRaisesRegex(ValueError, "chapter_0012.md.*Chapter Notes"):
            read_chapter(path)


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

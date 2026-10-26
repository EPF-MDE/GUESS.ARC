"""Tests du parseur de wikitexte, sur des extraits réels des chapitres 500 et 1193. No network access."""
import unittest

from guess_arc.ingestion.parser import parse_chapter, parse_characters, section
from guess_arc.ingestion.silver import render_markdown
from guess_arc.ingestion.validation import validate_silver_content

# Extrait réel du chapitre 500 (style ancien : annotations en parenthèses nues)
CH500_CHARACTERS = """
{| class="CharTable"
! colspan="2"|[[Pirates]]
! [[World Government]]
! colspan="2"|Others
|-
|
;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Nami]]
*[[Usopp]]
|
;[[Heart Pirates]]
*[[Trafalgar D. Water Law|Trafalgar Law]]
*[[Bepo]]
----
;Other
*[[Stansen]]
|
;[[CP9]]
*[[Kalifa]] (cover)
|}
"""

# Extrait réel du chapitre 1193 (style récent : ''(cover)'' / ''(flashback)'')
CH1193_CHARACTERS = """
{|class="CharTable"
!colspan="2"|[[Pirate]]s
|-
|
;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Roronoa Zoro]]
|
;[[Beasts Pirates]]
*[[King]] ''(cover)''
|
;[[Elbaph]]
*[[Harald]] ''(flashback)''
*[[Loki]]
|}
"""

CH1193_PAGE = """{{Chapter Box
| title = Still Practicing
| jname = 練習中
}}
'''Chapter 1193''' is titled "Still Practicing".

==Short Summary==
[[Monkey D. Luffy|Luffy]] and [[Loki]] attack [[Nerona Imu|Imu]].

==Long Summary==
""" + ("Luffy and [[Loki|Loki's]] combined attack blasts Imu into the tree. " * 8) + """

==Quick References==
===Chapter Notes===
*[[Roronoa Zoro|Zoro]] resumes his battle.
**Sommers is injured.

===Characters===
""" + CH1193_CHARACTERS + """
==Arc Navigation==
{{Elbaph Arc}}
"""


def by_name(characters, name):
    return next(c for c in characters if c["name"] == name)


class TestParseCharacters(unittest.TestCase):

    def test_old_style_annotations(self):
        chars = parse_characters(CH500_CHARACTERS)
        self.assertEqual(len(chars), 7)
        self.assertFalse(by_name(chars, "Kalifa")["on_panel"])
        self.assertTrue(by_name(chars, "Monkey D. Luffy")["on_panel"])

    def test_piped_link_resolves_to_page_name(self):
        chars = parse_characters(CH500_CHARACTERS)
        self.assertIn("Trafalgar D. Water Law", [c["name"] for c in chars])

    def test_faction_is_attached(self):
        chars = parse_characters(CH500_CHARACTERS)
        self.assertEqual(by_name(chars, "Nami")["faction"], "Straw Hat Pirates")

    def test_unlinked_group_is_captured(self):
        chars = parse_characters(CH500_CHARACTERS)
        self.assertEqual(by_name(chars, "Stansen")["faction"], "Other")

    def test_new_style_annotations(self):
        chars = parse_characters(CH1193_CHARACTERS)
        self.assertEqual(len(chars), 5)
        self.assertFalse(by_name(chars, "King")["on_panel"])
        self.assertFalse(by_name(chars, "Harald")["on_panel"])
        self.assertTrue(by_name(chars, "Loki")["on_panel"])


class TestSection(unittest.TestCase):

    def test_deeper_subheading_stays_inside_section(self):
        # Chapitre 590 : des sous-titres ===...=== dans ==Long Summary==.
        page = "==Long Summary==\nA\n===Day 1===\nB\n==Quick References==\nC\n"
        self.assertEqual(section(page, "Long Summary"), "A\n===Day 1===\nB")

    def test_sibling_subheading_ends_section(self):
        page = "==Quick References==\n===Chapter Notes===\n*A\n===Characters===\n*[[B]]\n"
        self.assertEqual(section(page, "Chapter Notes"), "*A")

    def test_heading_with_bom_is_found(self):
        # Chapitre 46 : '===﻿Chapter Notes==='.
        self.assertEqual(section("===﻿Chapter Notes===\n*A\n", "Chapter Notes"), "*A")

    def test_missing_section_is_empty(self):
        self.assertEqual(section("==Long Summary==\nA\n", "Short Summary"), "")


class TestParseChapter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ch = parse_chapter(1193, CH1193_PAGE, 123, "2026-09-13T16:09:21Z")

    def test_metadata(self):
        self.assertEqual(self.ch.title, "Still Practicing")
        self.assertEqual(self.ch.jname, "練習中")
        self.assertEqual(self.ch.arc, "Elbaph Arc")
        self.assertTrue(self.ch.complete)

    def test_notes_exclude_character_table(self):
        self.assertEqual(self.ch.notes, ["Zoro resumes his battle.", "Sommers is injured."])

    def test_characters(self):
        self.assertEqual(len(self.ch.characters), 5)

    def test_summaries_are_stripped_of_markup(self):
        self.assertNotIn("[[", self.ch.long_summary)
        self.assertEqual(self.ch.short_summary, "Luffy and Loki attack Imu.")

    def test_short_long_summary_marks_chapter_incomplete(self):
        page = CH1193_PAGE.replace("combined attack blasts Imu into the tree. ", "x ")
        self.assertFalse(parse_chapter(1193, page, 123, "2026-09-13T16:09:21Z").complete)

    def test_rendered_silver_passes_format_contract(self):
        self.assertEqual(validate_silver_content(render_markdown(self.ch), "chapter_1193.md"), [])


if __name__ == "__main__":
    unittest.main()

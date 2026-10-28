"""Préparsing de l'extraction des événements, à travers le pipeline `--dry-run`.

Chapitres silver synthétiques écrits dans un dossier de données temporaire,
puis lecture des fichiers `data/event/in/events_NNNN.md` produits. Sans réseau.
"""
import re
import tempfile
import unittest
from pathlib import Path

from guess_arc import paths
from guess_arc.events.pipeline import main, run
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def chapter(number, **kwargs):
    defaults = dict(
        title=f"Title {number}",
        arc="Loguetown Arc",
        revision_id=1000 + number,
        revised_at="2025-01-01T00:00:00Z",
        characters=[{"name": "Monkey D. Luffy", "faction": "Straw Hat Pirates",
                     "on_panel": True, "appearance": []}],
        short_summary=f"Short summary {number}.",
        long_summary=f"Long summary {number}.",
        notes=[f"Note {number}."],
        complete=True,
    )
    defaults.update(kwargs)
    return Chapter(number=number, **defaults)


class PreparseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_silver(self, *chapters):
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(self.data_dir))

    def dry_run(self, first=None, last=None):
        run(data_dir=self.data_dir, first=first, last=last, dry_run=True)

    def read_input(self, number):
        text = (paths.event_in_dir(self.data_dir) / f"events_{number:04d}.md").read_text(
            encoding="utf-8")
        match = FRONT_MATTER_RE.match(text)
        self.assertIsNotNone(match, "front-matter manquant")
        return match.group(1), text[match.end():]


class TestDryRunFiles(PreparseTestCase):
    def test_one_input_file_per_chapter_in_range(self):
        self.write_silver(*(chapter(n) for n in range(1, 6)))
        self.dry_run(first=2, last=4)
        written = sorted(p.name for p in paths.event_in_dir(self.data_dir).iterdir())
        self.assertEqual(written, ["events_0002.md", "events_0003.md", "events_0004.md"])

    def test_no_range_means_every_silver_chapter(self):
        self.write_silver(chapter(1), chapter(2))
        self.dry_run()
        written = sorted(p.name for p in paths.event_in_dir(self.data_dir).iterdir())
        self.assertEqual(written, ["events_0001.md", "events_0002.md"])

    def test_cli_dry_run(self):
        self.write_silver(chapter(7), chapter(8))
        main(["--data-dir", str(self.data_dir), "--dry-run", "--from", "8", "--to", "8"])
        written = [p.name for p in paths.event_in_dir(self.data_dir).iterdir()]
        self.assertEqual(written, ["events_0008.md"])

    def test_cli_without_dry_run_is_refused_for_now(self):
        self.write_silver(chapter(1))
        with self.assertRaises(SystemExit):
            main(["--data-dir", str(self.data_dir)])


class TestPrompt(PreparseTestCase):
    def test_prompt_carries_number_title_arc_and_sections(self):
        self.write_silver(chapter(
            97, title="Sandai Kitetsu", arc="Loguetown Arc",
            short_summary="Zoro buys swords.",
            long_summary="Zoro enters the Arms Shop.\n\nSmoker waits.",
            notes=["Smoker is introduced.", "Tashigi is a Marine."],
        ))
        self.dry_run()
        _, body = self.read_input(97)
        self.assertEqual(body, (
            'CHAPTER 97 — "Sandai Kitetsu" — Arc: Loguetown Arc\n'
            "\n"
            "=== SHORT SUMMARY ===\n"
            "Zoro buys swords.\n"
            "\n"
            "=== LONG SUMMARY ===\n"
            "Zoro enters the Arms Shop.\n"
            "\n"
            "Smoker waits.\n"
            "\n"
            "=== CHAPTER NOTES ===\n"
            "- Smoker is introduced.\n"
            "- Tashigi is a Marine.\n"
        ))

    def test_chapter_without_notes(self):
        self.write_silver(chapter(3, notes=[]))
        self.dry_run()
        _, body = self.read_input(3)
        self.assertTrue(body.endswith("=== CHAPTER NOTES ===\n- none\n"))


class TestFrontMatter(PreparseTestCase):
    def test_front_matter_is_complete(self):
        self.write_silver(chapter(12, revision_id=424242))
        self.dry_run()
        front, _ = self.read_input(12)
        self.assertRegex(front, r"(?m)^chapter: 12$")
        self.assertRegex(front, r"(?m)^revision_id: 424242$")
        self.assertRegex(front, r'(?m)^entities_version: "v\d+"$')
        self.assertRegex(front, r'(?m)^prompt_version: "v\d+"$')
        self.assertRegex(front, r"(?m)^flags:$")
        self.assertRegex(front, r"(?m)^  editorial_notes_removed: 0$")
        self.assertRegex(front, r"(?m)^  cover_notes_removed: 0$")


class TestNoteRemoval(PreparseTestCase):
    EDITORIAL = [
        "This is the first chapter of the Loguetown Arc.",
        "This is the last chapter of the Loguetown Arc and the East Blue Saga.",
        "This is the final chapter of the Punk Hazard Arc.",
        "It is also the first chapter of the Return to Sabaody Arc and the Fish-Man Island Saga.",
        "This chapter marks the end of Act 1 of the Wano Country Arc.",
        "The second act of the Wano Country Arc begins.",
        "This chapter marks the beginning of the second half of One Piece.",
        "In the Jump version of this chapter, Neptune said that Zoro's bounty is 160,000,000.",
        "Kyros is drawn with both legs in this chapter, but this is corrected in the volume version.",
        "This was fixed in the Volume 84 release.",
        "Charlotte Amande was previously only mentioned in SBS Volume 87.",
        "The scene appears in the 12th One Piece Opening Kaze o Sagashite.",
    ]
    COVER = [
        "The cover marks the first appearance of Garp and Bogard.",
        "Pandakid appears on the cover next to Wapol's toy stand.",
        "Franky's cover story begins.",
        "Usopp starts his coverstory.",
        "The cover page shows the Straw Hats' costumes based on fruits.",
        "Gaimon is seen for the first time since the cover mini-story.",
        "It is the first, and so far only, color spread split into 4 pages.",
        "Someone has escaped Marine custody at the start of a new cover arc.",
        "This is the final chapter of Jango's Dance Paradise.",
    ]
    KEPT = [
        "Smoker is introduced.",
        "Nami covers the cost of Kureha's treatment.",
        "Sanji is able to cover it up.",
        "This causes Luffy to blow his cover in front of Cavendish.",
        "Imu ordered the cover up of Roger's true name.",
        "The ill sister may have been a cover story for his work with Doflamingo.",
        "Ipponmatsu and Ipponume appear for the first time since the Loguetown Arc.",
        "Another Rear Admiral is introduced, the previous one being the anime-only Yukimura.",
        "Chopper uses Jumping Point to jump to higher ground.",
    ]

    def test_editorial_and_cover_notes_are_removed_and_counted(self):
        self.write_silver(chapter(50, notes=self.EDITORIAL + self.COVER + self.KEPT))
        self.dry_run()
        front, body = self.read_input(50)
        notes = body.split("=== CHAPTER NOTES ===\n", 1)[1]
        self.assertEqual(notes, "".join(f"- {n}\n" for n in self.KEPT))
        self.assertRegex(front, rf"(?m)^  editorial_notes_removed: {len(self.EDITORIAL)}$")
        self.assertRegex(front, rf"(?m)^  cover_notes_removed: {len(self.COVER)}$")

    def test_all_notes_removed_leaves_none(self):
        self.write_silver(chapter(51, notes=["This is the last chapter of the Zou Arc."]))
        self.dry_run()
        _, body = self.read_input(51)
        self.assertTrue(body.endswith("=== CHAPTER NOTES ===\n- none\n"))


class TestNormalisation(PreparseTestCase):
    def test_text_is_normalised(self):
        self.write_silver(chapter(
            60,
            title="Donut Race<nowiki>!!</nowiki>",
            short_summary="﻿A bomb with a blast diameter of 5&nbsp;km.",
            long_summary=(
                "Buggy\xa0gloats,\xa0he shoots.  Luffy then says to Kuro  no.\n"
                "\t\n"
                "[[File:Luffy Kicking Hody.png|thumb|left|210px|Luffy Kicks Hody.]]\n"
                "\n"
                "Luffy meets [[Nami]] and [[Roronoa Zoro|Zoro]] {{Qref|chap=1}}.​"
            ),
            notes=["Title is '''0''' and <s>3D</s>2Y<br />now.", "A &amp; B."],
        ))
        self.dry_run()
        _, body = self.read_input(60)
        self.assertNotRegex(body, r"&[a-zA-Z]+;|&#\d+;")
        self.assertNotRegex(body, "[\xa0​﻿\t]")
        self.assertNotRegex(body, r"\[\[|\]\]|\{\{|\}\}|''|<[^>]+>")
        self.assertNotRegex(body, r"  ")
        self.assertIn('CHAPTER 60 — "Donut Race!!" — Arc:', body)
        self.assertIn("=== SHORT SUMMARY ===\nA bomb with a blast diameter of 5 km.\n", body)
        self.assertIn(
            "=== LONG SUMMARY ===\n"
            "Buggy gloats, he shoots. Luffy then says to Kuro no.\n"
            "\n"
            "Luffy meets Nami and Zoro.\n",
            body,
        )
        self.assertIn("- Title is 0 and 2Y now.\n- A & B.\n", body)


if __name__ == "__main__":
    unittest.main()

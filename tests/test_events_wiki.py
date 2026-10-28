"""Événements d'origine `wiki`, à travers le pipeline `--dry-run`.

Chapitres silver synthétiques répartis sur plusieurs arcs, écrits dans un dossier
de données temporaire, puis lecture des fichiers `data/event/out/events_NNNN.json`.
Sans réseau ni modèle.
"""
import json
import tempfile
import unittest
from pathlib import Path

from guess_arc import paths
from guess_arc.events.pipeline import run
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown


def char(name, *appearance):
    excluded = {"cover", "flashback", "mentioned", "dream"}
    return {"name": name, "faction": "Some Faction",
            "on_panel": not excluded & set(appearance), "appearance": list(appearance)}


def chapter(number, arc, *characters, **kwargs):
    defaults = dict(
        title=f"Title {number}",
        arc=arc,
        revision_id=1000 + number,
        revised_at="2025-01-01T00:00:00Z",
        characters=list(characters),
        short_summary=f"Short summary {number}.",
        long_summary=f"Long summary {number}.",
        notes=[],
        complete=True,
    )
    defaults.update(kwargs)
    return Chapter(number=number, **defaults)


class WikiEventsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_silver(self, *chapters):
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(self.data_dir))

    def dry_run(self, first=None, last=None):
        run(data_dir=self.data_dir, first=first, last=last, dry_run=True,
            review_path=self.data_dir / "no_review.json")

    def output(self, number):
        path = paths.event_out_dir(self.data_dir) / f"events_{number:04d}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def events(self, number, type_=None):
        return [e for e in self.output(number)["events"]
                if type_ is None or e["type"] == type_]

    def names(self, number, type_):
        return [e["participants"][0]["name"] for e in self.events(number, type_)]


class TestFirstAppearance(WikiEventsTestCase):
    def test_first_chapter_on_panel(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy")),
            chapter(2, "A Arc", char("Luffy"), char("Zoro")),
        )
        self.dry_run()
        self.assertEqual(self.names(1, "first_appearance"), ["Luffy"])
        self.assertEqual(self.names(2, "first_appearance"), ["Zoro"])

    def test_flashback_counts_and_is_marked(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Shanks", "flashback")),
            chapter(2, "A Arc", char("Luffy"), char("Shanks")),
        )
        self.dry_run()
        [event] = self.events(1, "first_appearance")[1:]
        self.assertEqual(event["participants"], [{"name": "Shanks", "role": "agent"}])
        self.assertTrue(event["in_flashback"])
        self.assertFalse(self.events(1, "first_appearance")[0]["in_flashback"])
        self.assertEqual(self.names(2, "first_appearance"), [])

    def test_mention_cover_and_dream_alone_do_not_count(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Garp", "mentioned"),
                    char("Bogard", "cover"), char("Kuina", "dream")),
            chapter(2, "A Arc", char("Garp"), char("Bogard"), char("Kuina", "flashback")),
        )
        self.dry_run()
        self.assertEqual(self.names(1, "first_appearance"), ["Luffy"])
        self.assertEqual(self.names(2, "first_appearance"), ["Garp", "Bogard", "Kuina"])

    def test_flashback_on_a_cover_does_not_count(self):
        # Les cover stories sont exclues en v1, y compris leurs flashbacks.
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Tsukimi", "cover", "flashback")),
            chapter(2, "A Arc", char("Tsukimi")),
        )
        self.dry_run()
        self.assertEqual(self.names(1, "first_appearance"), ["Luffy"])
        self.assertEqual(self.names(2, "first_appearance"), ["Tsukimi"])

    def test_image_counts_as_on_panel(self):
        self.write_silver(chapter(1, "A Arc", char("Roger", "image")))
        self.dry_run()
        self.assertEqual(self.names(1, "first_appearance"), ["Roger"])


class TestReturn(WikiEventsTestCase):
    def test_return_after_a_whole_arc_of_absence(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Bellamy")),
            chapter(2, "B Arc", char("Luffy")),
            chapter(3, "B Arc", char("Luffy")),
            chapter(4, "C Arc", char("Luffy")),
            chapter(5, "C Arc", char("Luffy"), char("Bellamy")),
            chapter(6, "C Arc", char("Bellamy")),
        )
        self.dry_run()
        self.assertEqual(self.names(5, "return"), ["Bellamy"])
        [event] = self.events(5, "return")
        self.assertFalse(event["in_flashback"])
        self.assertEqual(self.names(6, "return"), [])
        # Luffy est là dans chaque arc : jamais de retour.
        self.assertEqual([n for c in range(1, 7) for n in self.names(c, "return")],
                         ["Bellamy"])

    def test_no_return_within_an_arc(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Buggy")),
            *(chapter(n, "A Arc", char("Luffy")) for n in range(2, 6)),
            chapter(6, "A Arc", char("Luffy"), char("Buggy")),
        )
        self.dry_run()
        self.assertEqual([n for c in range(1, 7) for n in self.names(c, "return")], [])

    def test_presence_off_panel_in_previous_arc_is_still_an_absence(self):
        self.write_silver(
            chapter(1, "A Arc", char("Bellamy")),
            chapter(2, "B Arc", char("Bellamy", "flashback"), char("Ace", "cover"),
                    char("Luffy")),
            chapter(3, "C Arc", char("Bellamy")),
        )
        self.dry_run()
        self.assertEqual(self.names(3, "return"), ["Bellamy"])

    def test_on_panel_in_previous_arc_is_not_a_return(self):
        self.write_silver(
            chapter(1, "A Arc", char("Usopp")),
            chapter(2, "B Arc", char("Usopp")),
            chapter(3, "C Arc", char("Usopp")),
        )
        self.dry_run()
        self.assertEqual(self.names(3, "return"), [])

    def test_first_appearance_is_not_a_return(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy")),
            chapter(2, "B Arc", char("Luffy")),
            chapter(3, "C Arc", char("Robin", "flashback")),
            chapter(4, "C Arc", char("Robin")),
        )
        self.dry_run()
        self.assertEqual(self.names(3, "first_appearance"), ["Robin"])
        self.assertEqual(self.names(3, "return") + self.names(4, "return"), [])

    def test_only_presented_by_cover_before_is_not_a_return(self):
        self.write_silver(
            chapter(1, "A Arc", char("Koby", "cover")),
            chapter(2, "B Arc", char("Luffy")),
            chapter(3, "C Arc", char("Koby")),
        )
        self.dry_run()
        self.assertEqual(self.names(3, "return"), [])
        self.assertEqual(self.names(3, "first_appearance"), ["Koby"])

    def test_arc_order_follows_first_occurrence_of_label(self):
        # Chapitre 4 revient au label « A Arc » : l'arc précédent de « C Arc »
        # reste « B Arc », l'ordre suit la première occurrence des labels.
        self.write_silver(
            chapter(1, "A Arc", char("Bellamy"), char("Luffy")),
            chapter(2, "B Arc", char("Luffy")),
            chapter(3, "A Arc", char("Luffy")),
            chapter(4, "C Arc", char("Bellamy")),
        )
        self.dry_run()
        self.assertEqual(self.names(4, "return"), ["Bellamy"])


class TestDefeat(WikiEventsTestCase):
    def test_one_defeat_per_ko(self):
        self.write_silver(chapter(
            1, "A Arc", char("Luffy"), char("Alvida", "ko"), char("Morgan", "ko", "other"),
            char("Shanks", "flashback", "ko"),
        ))
        self.dry_run()
        defeats = self.events(1, "defeat")
        self.assertEqual([e["participants"] for e in defeats], [
            [{"name": "Alvida", "role": "target"}],
            [{"name": "Morgan", "role": "target"}],
            [{"name": "Shanks", "role": "target"}],
        ])
        self.assertEqual([e["in_flashback"] for e in defeats], [False, False, True])

    def test_ko_on_a_cover_story_is_not_a_defeat(self):
        # Les cover stories sont exclues en v1.
        self.write_silver(chapter(1, "A Arc", char("Luffy"), char("Mohji", "cover", "ko")))
        self.dry_run()
        self.assertEqual(self.events(1, "defeat"), [])


class TestFormat(WikiEventsTestCase):
    def test_event_fields(self):
        self.write_silver(chapter(1, "A Arc", char("Luffy", "ko")))
        self.dry_run()
        for event in self.events(1):
            self.assertEqual(list(event), [
                "id", "origin", "type", "description", "participants", "location",
                "status", "in_flashback", "evidence", "source",
            ])
            self.assertEqual(event["origin"], "wiki")
            self.assertEqual(event["location"], "")
            self.assertEqual(event["status"], "single")
            self.assertEqual(event["evidence"], "")
            self.assertEqual(event["source"], "characters")
            self.assertIn("Luffy", event["description"])
        self.assertEqual([e["type"] for e in self.events(1)], ["first_appearance", "defeat"])

    def test_meta_block(self):
        self.write_silver(chapter(7, "A Arc", char("Luffy"), revision_id=424242))
        self.dry_run()
        meta = self.output(7)["meta"]
        self.assertEqual(meta["chapter"], 7)
        self.assertEqual(meta["revision_id"], 424242)
        self.assertRegex(meta["taxonomy_version"], r"^v\d+$")
        self.assertRegex(meta["entities_version"], r"^v\d+$")
        # Seule l'origine wiki est passée : la reprise ne doit pas croire le
        # chapitre déjà extrait par le modèle.
        self.assertEqual(meta["origins"], ["wiki"])

    def test_ids_are_stable_and_unique(self):
        chapters = [
            chapter(1, "A Arc", char("Luffy", "ko"), char("Zoro")),
            chapter(2, "B Arc", char("Nami")),
            chapter(3, "C Arc", char("Zoro", "ko")),
        ]
        self.write_silver(*chapters)
        self.dry_run()
        first = [e["id"] for c in (1, 2, 3) for e in self.events(c)]
        self.assertEqual(len(first), len(set(first)))
        # Nouvelle exécution, dans un autre dossier et avec une révision différente.
        self.tearDown()
        self.setUp()
        self.write_silver(*chapters[:2], chapter(3, "C Arc", char("Zoro", "ko"),
                                                 revision_id=9999))
        self.dry_run()
        self.assertEqual([e["id"] for c in (1, 2, 3) for e in self.events(c)], first)

    def test_chapter_without_events_still_has_a_file(self):
        self.write_silver(chapter(1, "A Arc", char("Luffy")), chapter(2, "A Arc", char("Luffy")))
        self.dry_run()
        self.assertEqual(self.events(2), [])
        self.assertEqual(self.output(2)["meta"]["chapter"], 2)


class TestRange(WikiEventsTestCase):
    def test_range_uses_history_before_it(self):
        self.write_silver(
            chapter(1, "A Arc", char("Luffy"), char("Bellamy")),
            chapter(2, "B Arc", char("Luffy")),
            chapter(3, "C Arc", char("Luffy"), char("Bellamy")),
        )
        self.dry_run(first=3, last=3)
        written = [p.name for p in paths.event_out_dir(self.data_dir).iterdir()]
        self.assertEqual(written, ["events_0003.json"])
        self.assertEqual(self.names(3, "first_appearance"), [])
        self.assertEqual(self.names(3, "return"), ["Bellamy"])


if __name__ == "__main__":
    unittest.main()

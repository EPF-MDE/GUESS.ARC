"""Bloc d'entités « sans futur » du prompt, à travers le pipeline `--dry-run`.

Chapitres silver synthétiques et mini-fichiers d'entités (`data/Entité/`)
écrits dans un dossier de données temporaire, puis lecture des fichiers
`data/event/in/events_NNNN.md` : bloc ENTITIES du corps et liste
`allowed_names` du front-matter. Sans réseau ni modèle.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from guess_arc import paths
from guess_arc.events.pipeline import run
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def char(name, *appearance):
    excluded = {"cover", "flashback", "mentioned", "dream"}
    return {"name": name, "faction": "Some Faction",
            "on_panel": not excluded & set(appearance), "appearance": list(appearance)}


def chapter(number, *characters, text="Nothing happens.", notes=(), **kwargs):
    defaults = dict(
        title=f"Title {number}",
        arc="A Arc",
        revision_id=1000 + number,
        revised_at="2025-01-01T00:00:00Z",
        characters=list(characters),
        short_summary="Short summary.",
        long_summary=text,
        notes=list(notes),
        complete=True,
    )
    defaults.update(kwargs)
    return Chapter(number=number, **defaults)


def person(name, first=1, race="Human", journey=None, **extra):
    return {"name": name, "image": "/x.webp", "first_appearance_arc": f"Chapter {first}"
            if isinstance(first, int) else first, "race": race, "status": "Alive",
            "description": f"Secret of {name}", "journey": journey, **extra}


LUFFY = person(
    "Monkey D. Luffy", 1,
    bounty=3000000000, devil_fruit="Hito Hito no Mi, Model: Nika",
    epithet="Straw Hat", affiliation="Straw Hat Pirates",
    relationships=[{"name": "Monkey D. Dragon", "relationship": "Son"}],
    journey=[
        {"location": "Dawn Island"},
        {"location": "Loguetown", "chapter": "Chapter 96"},
        {"location": "Reverse Mountain", "chapter": "Chapter 101", "region": "Grand Line"},
    ],
)

CHARACTERS = [
    LUFFY,
    person("Roronoa Zoro", 3),
    person("Cutty Flam [Franky]", 5, race="Cyborg"),
    person("Bentham (Bon Clay) [Mr. 2]", 5, race="Human"),
    person("Kinemon", 5),
    person("Charlotte Brûlée", 5),
    person("Arber [King]", 5, race="Lunarian"),
    person("Hody Jones", 5, race="Fish-Man"),
    person("Davy D. Jones", 5),
    person("Monkey D. Dragon", 100),
    person("Pandaman", "SBS Volume 4"),
    person("Bogard", 5),
    person("Page One", 5),
    person("Baby 5", 5),
    person("Basil Hawkins", 5),
]

FRUITS = [
    {"name": " Bara Bara no Mi", "english": "Chop-Chop Fruit", "image": "/x.webp",
     "type": "Paramecia", "user": "Buggy", "description": "Splitting Human."},
    {"name": "Gomu Gomu no Mi", "english": "Gum-Gum Fruit", "image": "/x.webp",
     "type": "Zoan", "user": "Monkey D. Luffy", "description": "Awakened as Nika."},
    {"name": "Mera Mera no Mi", "english": "Flame-Flame Fruit", "image": "/x.webp",
     "type": "Logia", "user": "Portgas D. Ace", "description": "Fire."},
]

ISLANDS = [
    {"name": "Dawn Island", "image": "/x.webp", "location": "East Blue",
     "description": "Home island of Luffy, Dragon and Garp.",
     "current_ruler": "Sterry", "notable_members": ["Makino"]},
    {"name": "Wano Country", "image": "/x.webp", "location": "New World",
     "description": "Land of samurai.", "current_ruler": "Kozuki Momonosuke"},
]


class EntitiesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.write_entities(CHARACTERS, FRUITS, ISLANDS)

    def tearDown(self):
        self._tmp.cleanup()

    def write_entities(self, characters, fruits, islands):
        entity_dir = paths.entities_dir(self.data_dir)
        entity_dir.mkdir(parents=True, exist_ok=True)
        for name, content in (("characters", characters), ("devil_fruits", fruits),
                              ("islands", islands)):
            (entity_dir / f"{name}.json").write_text(
                json.dumps(content, ensure_ascii=False), encoding="utf-8")

    def write_silver(self, *chapters):
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(self.data_dir))

    def dry_run(self, first=None, last=None):
        run(data_dir=self.data_dir, first=first, last=last, dry_run=True,
            review_path=self.data_dir / "no_review.json")

    def read_input(self, number):
        text = (paths.event_in_dir(self.data_dir) / f"events_{number:04d}.md").read_text(
            encoding="utf-8")
        match = FRONT_MATTER_RE.match(text)
        return match.group(1), text[match.end():]

    def block(self, number):
        _, body = self.read_input(number)
        return body.split("ENTITIES (use these exact names):\n", 1)[1].split(
            "\n\n=== SHORT SUMMARY ===", 1)[0]

    def section(self, number, title):
        lines = self.block(number).split(f"{title}:\n", 1)[1].split("\n")
        return [line for line in lines[:next((i for i, l in enumerate(lines)
                                              if not l.startswith("- ")), len(lines))]]

    def characters(self, number):
        return self.section(number, "Characters")

    def allowed_names(self, number):
        front, _ = self.read_input(number)
        match = re.search(r"(?ms)^allowed_names:(.*?)(?=^\S|\Z)", front)
        self.assertIsNotNone(match, "allowed_names absent du front-matter")
        inline = match.group(1).strip()
        if inline == "[]":
            return []
        return [json.loads(line.strip()[2:]) for line in inline.splitlines()]


class TestBlockPlacement(EntitiesTestCase):
    def test_block_sits_between_header_and_summaries(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy")))
        self.dry_run()
        _, body = self.read_input(10)
        self.assertTrue(body.startswith(
            'CHAPTER 10 — "Title 10" — Arc: A Arc\n'
            "\n"
            "ENTITIES (use these exact names):\n"
            "Characters:\n"
            "- Monkey D. Luffy (aliases: Luffy; race: Human)\n"
            "Devil Fruits mentioned:\n"
            "- none\n"
            "Places mentioned:\n"
            "- none\n"
            "\n"
            "=== SHORT SUMMARY ===\n"))

    def test_without_entity_files_the_table_still_gives_names(self):
        for path in paths.entities_dir(self.data_dir).iterdir():
            path.unlink()
        self.write_silver(chapter(10, char("Monkey D. Luffy")))
        self.dry_run()
        self.assertEqual(self.characters(10), ["- Monkey D. Luffy"])
        self.assertEqual(self.section(10, "Devil Fruits mentioned"), ["- none"])


class TestNoFuture(EntitiesTestCase):
    def test_only_name_aliases_and_race_are_sent(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy")))
        self.dry_run()
        block = self.block(10)
        for leak in ("Secret of", "3000000000", "Hito Hito", "Straw Hat", "Dragon",
                     "Alive", "Son"):
            self.assertNotIn(leak, block)

    def test_journey_keeps_only_steps_dated_up_to_t(self):
        self.write_silver(chapter(96, char("Monkey D. Luffy")),
                          chapter(100, char("Monkey D. Luffy")),
                          chapter(101, char("Monkey D. Luffy")))
        self.dry_run()
        self.assertEqual(self.characters(100), [
            "- Monkey D. Luffy (aliases: Luffy; race: Human; journey: Loguetown (ch. 96))"])
        self.assertEqual(self.characters(101), [
            "- Monkey D. Luffy (aliases: Luffy; race: Human; "
            "journey: Loguetown (ch. 96), Reverse Mountain (ch. 101))"])
        self.assertNotIn("Dawn Island", self.block(101))

    def test_fruits_and_islands_cited_in_text_carry_only_name_and_sea(self):
        self.write_silver(chapter(
            10, char("Monkey D. Luffy"),
            text="Luffy ate the Gomu Gomu no Mi on Dawn Island. Buggy's Chop-Chop Fruit."))
        self.dry_run()
        self.assertEqual(self.section(10, "Devil Fruits mentioned"), [
            "- Bara Bara no Mi (Chop-Chop Fruit)",
            "- Gomu Gomu no Mi (Gum-Gum Fruit)",
        ])
        self.assertEqual(self.section(10, "Places mentioned"), ["- Dawn Island (East Blue)"])

    def test_unknown_sea_is_not_sent(self):
        self.write_entities(CHARACTERS, FRUITS, [
            {"name": "Rusukaina", "image": "/x.webp", "location": "Unknown",
             "description": "Island where Luffy trained.", "current_ruler": "Unknown"}])
        self.write_silver(chapter(10, char("Monkey D. Luffy"), text="Luffy lands on Rusukaina."))
        self.dry_run()
        self.assertEqual(self.section(10, "Places mentioned"), ["- Rusukaina"])
        block = self.block(10)
        for leak in ("Zoan", "Paramecia", "Nika", "Home island", "Sterry", "Makino",
                     "Mera", "Wano"):
            self.assertNotIn(leak, block)


class TestSelection(EntitiesTestCase):
    def test_cover_only_character_is_left_out(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), char("Bogard", "cover")))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy"])

    def test_cover_character_named_in_text_is_included(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), char("Bogard", "cover"),
                                  text="Bogard watches."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Bogard"])

    def test_mentioned_and_flashback_characters_are_included(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), char("Roronoa Zoro", "mentioned"),
                                  char("Bogard", "flashback")))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Roronoa Zoro", "Bogard"])

    def test_character_named_only_in_text_is_included(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"),
                                  notes=["Zoro is seen sleeping."]))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Roronoa Zoro"])

    def test_silver_character_unknown_to_entities_is_sent_by_its_name(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), char("Mozu and Kiwi")))
        self.dry_run()
        self.assertEqual(self.characters(10)[1], "- Mozu and Kiwi")
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Mozu and Kiwi"])

    def test_two_rows_for_the_same_entity_give_one_card(self):
        self.write_silver(chapter(10, char("Cutty Flam"), char("Franky", "flashback"),
                                  text="Franky shouts."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Cutty Flam [Franky]"])


class TestTimeFilter(EntitiesTestCase):
    def test_character_named_before_first_appearance_is_never_sent(self):
        self.write_silver(
            chapter(10, char("Monkey D. Luffy"), text="Monkey D. Dragon is Luffy's father."),
            chapter(100, char("Monkey D. Luffy"), text="Monkey D. Dragon smiles."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy"])
        self.assertEqual(self.allowed_names(100), ["Monkey D. Luffy", "Monkey D. Dragon"])

    def test_mentioned_in_table_before_first_appearance_is_never_sent(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"),
                                  char("Monkey D. Dragon", "mentioned")))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy"])

    def test_presented_in_silver_counts_as_appeared(self):
        # Pandaman n'a pas de chapitre de première apparition (« SBS Volume 4 ») :
        # il est apparu dès qu'un chapitre de la silver l'a présenté.
        self.write_silver(
            chapter(10, char("Monkey D. Luffy"), text="Pandaman waves."),
            chapter(11, char("Monkey D. Luffy"), char("Pandaman")),
            chapter(12, char("Monkey D. Luffy"), text="Pandaman waves."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy"])
        self.assertEqual(self.allowed_names(11), ["Monkey D. Luffy", "Pandaman"])
        self.assertEqual(self.allowed_names(12), ["Monkey D. Luffy", "Pandaman"])

    def test_cover_appearance_does_not_count_as_appeared(self):
        self.write_silver(
            chapter(1, char("Monkey D. Luffy"), char("Pandaman", "cover")),
            chapter(2, char("Monkey D. Luffy"), text="Pandaman waves."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(2), ["Monkey D. Luffy"])

    def test_history_before_the_range_is_taken_into_account(self):
        self.write_silver(
            chapter(11, char("Pandaman")),
            chapter(12, char("Monkey D. Luffy"), text="Pandaman waves."),
        )
        self.dry_run(first=12)
        self.assertEqual(self.allowed_names(12), ["Monkey D. Luffy", "Pandaman"])


class TestAliases(EntitiesTestCase):
    def test_brackets(self):
        self.write_silver(chapter(10, char("Franky")))
        self.dry_run()
        self.assertEqual(self.characters(10), [
            "- Cutty Flam [Franky] (aliases: Cutty Flam, Franky, Flam; race: Cyborg)"])

    def test_parentheses(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), text="Bon Clay dances."))
        self.dry_run()
        self.assertEqual(self.characters(10)[1],
                         "- Bentham (Bon Clay) [Mr. 2] (aliases: Bentham, Bon Clay, Mr. 2; "
                         "race: Human)")

    def test_unambiguous_last_word(self):
        self.write_silver(chapter(10, char("Zoro"), text="Hody fights."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Roronoa Zoro"])

    def test_ambiguous_last_word_is_not_used(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), char("Jones"),
                                  text="Jones laughs."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Jones"])
        self.assertNotIn("Hody", self.block(10))
        self.assertNotIn("Davy", self.block(10))

    def test_ambiguous_last_word_is_not_listed_as_alias(self):
        self.write_silver(chapter(10, char("Hody Jones")))
        self.dry_run()
        self.assertEqual(self.characters(10), ["- Hody Jones (race: Fish-Man)"])

    def test_case(self):
        self.write_silver(chapter(10, char("monkey d. LUFFY"), text="ZORO yawns."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Roronoa Zoro"])

    def test_accents(self):
        self.write_silver(chapter(10, char("Charlotte Brulee"), text="Brûlée hides."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Charlotte Brûlée"])

    def test_apostrophes(self):
        self.write_silver(chapter(10, char("Kin'emon"), text="Kin’emon's sword."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Kinemon"])

    def test_possessive_in_text(self):
        self.write_silver(chapter(10, char("Monkey D. Luffy"), text="Zoro's swords."))
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Roronoa Zoro"])

    def test_lowercase_word_in_text_is_not_a_name(self):
        self.write_silver(
            chapter(10, char("Monkey D. Luffy"),
                    text="Luffy beats the king of the island while King watches."),
            chapter(11, char("Monkey D. Luffy"), text="Luffy beats the king of the island."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Arber [King]"])
        self.assertEqual(self.allowed_names(11), ["Monkey D. Luffy"])

    def test_word_mostly_written_in_lowercase_is_not_searched_alone(self):
        # « One » est surtout un mot courant (« one of them ») : « One Piece » ne
        # désigne pas Page One, mais son nom complet le désigne.
        self.write_silver(
            chapter(10, char("Monkey D. Luffy"), text="Luffy wants the One Piece. "
                    "He is one of them, one day, one by one."),
            chapter(11, char("Monkey D. Luffy"), text="Luffy wants the One Piece."),
            chapter(12, char("Monkey D. Luffy"), text="Luffy meets Page One."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(11), ["Monkey D. Luffy"])
        self.assertEqual(self.allowed_names(12), ["Monkey D. Luffy", "Page One"])

    def test_counts_only_read_chapters_up_to_t(self):
        self.write_silver(
            chapter(10, char("Monkey D. Luffy"), text="Luffy wants the One Piece."),
            chapter(11, char("Monkey D. Luffy"), text="one of them, one day, one by one."),
        )
        self.dry_run()
        self.assertEqual(self.allowed_names(10), ["Monkey D. Luffy", "Page One"])

    def test_number_or_short_last_word_is_not_an_alias(self):
        self.write_silver(chapter(10, char("Baby 5"), char("Basil Hawkins"),
                                  text="5 marines and Hawkins."))
        self.dry_run()
        self.assertEqual(self.characters(10), [
            "- Baby 5 (race: Human)",
            "- Basil Hawkins (aliases: Hawkins; race: Human)",
        ])


if __name__ == "__main__":
    unittest.main()

"""Tests de l'extraction d'entités via son seul point d'entrée, sur des extraits réels du bronze. No network access."""
import unittest

from guess_arc.entities import Reference, extract_entities

# Extrait réel du chapitre 552
CH552_SCENE = (
    "At the [[Marineford|Marine Headquarters]], all [[Marines]] suddenly become alert as news "
    "gets out that [[Shanks]] and [[Edward Newgate|Whitebeard]] are about to meet. As both "
    "[[pirate]] ships approach each other, Whitebeard's men announce Shanks is coming. "
    "[[Polo Marco|Marco]] gives the warning to the younger crew members to step back as they "
    '"will not last", causing them to question why.'
)

# Extrait réel du chapitre 1044 : lien vers une sous-page
CH1044_SCENE = (
    "On the rooftop, Luffy says he can keep fighting longer now, and declares his new form "
    "\"[[Gomu Gomu no Mi/Gear 5 Techniques|'''Gear 5''']]\". With his new form, Luffy emits a "
    "huge blast of [[Haki/Supreme King Haki|Supreme King Haki]], knocking out several "
    "[[Beasts Pirates]]."
)

# Extrait réel du chapitre 444 : lien vers une section
CH444_SCENE = (
    "With no stopping them, [[Franky]] decides to further explain the "
    "[[Thousand Sunny#Soldier Dock System|Soldier Dock System]] in regards to their new ship."
)

# Extrait réel du chapitre 4 : lien vers une section de la page Pirate
CH4_SCENE = (
    "Koby reveals to Zoro his desire to become a Marine who is just, as well as Luffy's dream "
    "of becoming [[Pirate#Pirate_King|Pirate King]]. While Zoro shows surprise for Luffy's "
    "ambition, Koby is suddenly shot."
)

# Extrait réel du chapitre 41 (+ une image du chapitre 633) : liens hors articles
CH41_SCENE = (
    "Elsewhere, [[Merry]] and Kaya show the [[Straw Hat Pirates]] the ship they intend to give "
    "them, the [[Going Merry]]. Nami comments on it being a [[wikipedia:Caravel|caravel]].\n\n"
    "[[File:Luffy Kicking Hody.png|thumb|left|210px|Luffy Kicks Hody.]]"
)

# Extrait réel du chapitre 929 : un ':' dans le titre d'une page d'article
CH929_SCENE = (
    "Specifically, [[X Drake]] and [[Page One]], both having eaten Ryu Ryu Ancient type "
    "[[Zoan]] fruits; Drake having the [[Ryu Ryu no Mi, Model: Allosaurus|allosaurus]] model."
)


# Extrait réel du chapitre 590 (abrégé) : 3 paragraphes de récit, un titre en gras
# isolé et deux sous-titres ===...=== collés à leur paragraphe.
CH590_LONG_SUMMARY = """'''East Blue-Foosha Village'''

Garp returns to Luffy's hometown only to hear that Makino's bar has been over-run by vicious mountain bandits. Those mountain bandits ended up being Dadan and her subordinates.

===Grand Line-New World===
The Whitebeard and Red Haired pirate crews bid a final farewell to Edward Newgate and Portgas D. Ace at their funeral where Marco thanks Red Haired Shanks for everything he has done for him and his crew.

===Calm Belt-Amazon Lily===
Jinbe tells Luffy to stop beating himself up over Ace's death."""


# Extrait réel du chapitre 528 (abrégé) : un titre en gras qui contient une apostrophe.
CH528_LONG_SUMMARY = """The Basilisk tries to bite Luffy, at which Luffy jumps, then prepares to fight the Basilisk head on.

'''Level 4, Chief Warden's office'''

[[Boa Hancock]] comments about the heat in Impel Down, saying it was too hot. [[Domino]] points out that beyond the walls of the Chief Warden's office, was an inferno."""


def bronze_record(number, long_summary):
    """Enregistrement bronze minimal, tel que lu depuis chapters.jsonl."""
    wikitext = (
        "{{Chapter Box\n| title = Test\n}}\n"
        "==Short Summary==\nCourt résumé.\n\n"
        f"==Long Summary==\n{long_summary}\n\n"
        "==Quick References==\n===Chapter Notes===\n*Note.\n"
    )
    return {"number": number, "revid": 1, "timestamp": "2026-01-01T00:00:00Z", "wikitext": wikitext}


def names_at(extraction, t):
    return {row.canonical_name for row in extraction.registry_at(t)}


def state_at(extraction, name, t):
    """(premier chapitre vu, dernier chapitre vu, nombre de Mentions) d'une Entity dans Registry(t)."""
    row = next(r for r in extraction.registry_at(t) if r.canonical_name == name)
    return row.first_chapter_seen, row.last_chapter_seen, row.mention_count


class TestScenes(unittest.TestCase):

    def test_each_paragraph_of_the_long_summary_is_a_scene(self):
        extraction = extract_entities([bronze_record(552, CH552_SCENE)], Reference())
        self.assertEqual(extraction.quality.scenes_per_chapter, {552: 1})

    def test_subheadings_do_not_create_scenes(self):
        extraction = extract_entities([bronze_record(590, CH590_LONG_SUMMARY)], Reference())
        self.assertEqual(extraction.quality.scenes_per_chapter, {590: 3})

    def test_bold_subheading_with_apostrophe_does_not_create_a_scene(self):
        extraction = extract_entities([bronze_record(528, CH528_LONG_SUMMARY)], Reference())
        self.assertEqual(extraction.quality.scenes_per_chapter, {528: 2})

    def test_lone_image_does_not_create_a_scene(self):
        extraction = extract_entities([bronze_record(41, CH41_SCENE)], Reference())
        self.assertEqual(extraction.quality.scenes_per_chapter, {41: 1})


class TestMentions(unittest.TestCase):

    def test_piped_link_is_a_mention_of_its_target(self):
        extraction = extract_entities([bronze_record(552, CH552_SCENE)], Reference())
        names = names_at(extraction, 552)
        self.assertIn("Polo Marco", names)
        self.assertNotIn("Marco", names)
        self.assertIn("Edward Newgate", names)

    def test_subpage_link_is_a_mention_of_the_parent_entity(self):
        extraction = extract_entities([bronze_record(1044, CH1044_SCENE)], Reference())
        names = names_at(extraction, 1044)
        self.assertIn("Gomu Gomu no Mi", names)
        self.assertIn("Haki", names)
        self.assertFalse(any("/" in n for n in names))

    def test_section_link_is_a_mention_of_the_parent_entity(self):
        extraction = extract_entities([bronze_record(444, CH444_SCENE)], Reference())
        names = names_at(extraction, 444)
        self.assertIn("Thousand Sunny", names)
        self.assertFalse(any("#" in n for n in names))

    def test_link_target_is_normalised_to_the_page_title(self):
        # Le wiki ignore la casse de la première lettre : [[pirate]] pointe vers Pirate.
        extraction = extract_entities(
            [bronze_record(552, CH552_SCENE), bronze_record(4, CH4_SCENE)], Reference()
        )
        names = names_at(extraction, 552)
        self.assertIn("Pirate", names)
        self.assertNotIn("pirate", names)
        self.assertEqual(state_at(extraction, "Pirate", 552)[2], 2)

    def test_links_outside_the_wiki_articles_are_not_mentions(self):
        extraction = extract_entities([bronze_record(41, CH41_SCENE)], Reference())
        self.assertEqual(names_at(extraction, 41), {"Merry", "Straw Hat Pirates", "Going Merry"})

    def test_colon_inside_a_page_title_is_kept(self):
        extraction = extract_entities([bronze_record(929, CH929_SCENE)], Reference())
        self.assertIn("Ryu Ryu no Mi, Model: Allosaurus", names_at(extraction, 929))


class TestRegistry(unittest.TestCase):
    """Fixture de 3 chapitres, ordre volontairement mélangé en entrée.

    ch. 1 : Polo Marco x1, Pirate x1
    ch. 2 : Franky x1, Thousand Sunny x1, Pirate x1   (2 Scenes)
    ch. 3 : Polo Marco x2, Pirate x2                   (2 Scenes)
    """

    @classmethod
    def setUpClass(cls):
        cls.extraction = extract_entities([
            bronze_record(3, CH552_SCENE + "\n\n" + CH552_SCENE),
            bronze_record(1, CH552_SCENE),
            bronze_record(2, CH444_SCENE + "\n\n" + CH4_SCENE),
        ], Reference())

    def test_registry_is_empty_before_the_first_chapter(self):
        self.assertEqual(self.extraction.registry_at(0), [])

    def test_entity_is_absent_before_its_first_mention(self):
        self.assertNotIn("Franky", names_at(self.extraction, 1))
        self.assertIn("Franky", names_at(self.extraction, 2))
        self.assertIn("Franky", names_at(self.extraction, 3))

    def test_one_row_per_entity_at_any_t(self):
        names = [r.canonical_name for r in self.extraction.registry_at(2)]
        self.assertEqual(len(names), len(set(names)))

    def test_state_carries_over_chapters_without_mention(self):
        self.assertEqual(state_at(self.extraction, "Polo Marco", 2), (1, 1, 1))

    def test_state_at_t_counts_mentions_up_to_t(self):
        self.assertEqual(state_at(self.extraction, "Polo Marco", 3), (1, 3, 3))
        self.assertEqual(state_at(self.extraction, "Pirate", 2), (1, 2, 2))
        self.assertEqual(state_at(self.extraction, "Pirate", 3), (1, 3, 4))

    def test_rows_are_dated_by_validity_interval(self):
        marco_rows = [
            (r.valid_from, r.valid_to) for r in self.extraction.registry
            if r.canonical_name == "Polo Marco"
        ]
        self.assertEqual(sorted(marco_rows, key=lambda v: v[0]), [(1, 2), (3, None)])


if __name__ == "__main__":
    unittest.main()

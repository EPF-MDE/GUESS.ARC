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

# Extraits réels : liens pipés dont le texte n'est pas un nom
CH223_SCENE = (
    "Just as Nami decides then to ask some more questions from the owner, Luffy and a "
    "[[Marshall D. Teach|man]] sitting next to him both suddenly make a remark about the "
    "cherry pie being served to them."
)
CH973_SCENE = (
    "After Oden returned from his travels, Oden spent time with his [[Kouzuki Family|family]], "
    "told [[Nine Red Scabbards|his retainers]] about [[Zou]], and listened to "
    "[[Kouzuki Hiyori|his daughter]] music."
)
CH1037_SCENE = (
    "This concerns the Five Elders as according to them, “[[Gomu Gomu no Mi|that]]” "
    "[[Devil Fruit]] hasn’t awakened in centuries and should only be a legend."
)
CH1159_SCENE = (
    "[[Magnolia|Their mother]] asks Garling to live with her on God Valley, but he declares "
    "that will not be possible as the island will disappear very soon."
)

# Extraits réels : texte de lien à nettoyer avant d'en faire un Alias
CH75_SCENE = (
    "Zoro explains that they have to hurry in order to save Usopp, who has been captured by "
    "[[Arlong|Arlong,]] before he is killed."
)
CH498_SCENE = (
    "Hatchan soon asks about the location of their friend "
    "[[Silvers Rayleigh|\"Rayleigh the Bubble Coater\"]] to get the [[Thousand Sunny]] coated."
)
CH927_SCENE = (
    "[[Nico Robin|Robin]], [[Franky]], and [[Usopp]] are each having a bowl while discussing "
    "[[Monkey D. Luffy|Luffy's]] whereabouts."
)
CH1123_SCENE = (
    "The [[Giants]] note that the burst was even stronger than [[Shanks|Shanks']] despite the "
    "lack of hostility in the Haki."
)
CH1046_SCENE = (
    "Usopp retorts that he feels he needs to do something as promised to [[Izou]] to save "
    "[[Kin'emon|Kin’emon]] and [[Kikunojo]]."
)

# Extrait réel du chapitre 620 : lien non pipé vers Edward Newgate
CH620_SCENE = (
    "Jinbe cuts in, saying the one who saved them from that horror was the now deceased "
    "[[Edward Newgate]]."
)

# Extrait réel du chapitre 1044 : Joy Boy est un Character distinct de Luffy
CH1044_JOY_BOY_SCENE = (
    "[[Kouzuki Momonosuke|Momonosuke]], meanwhile, has told [[Yamato]] what [[Zunesha]] told "
    "him: Luffy is [[Joy Boy]]."
)

# Extraits réels de Disguises, dans les trois sections lues pour les candidats
CH919_SCENE = (
    "Meanwhile, the money changer [[Denjiro|Kyoshiro]], while intoxicated, starts to laugh as "
    "he recalls a situation that Orochi has found himself in."
)
CH919_CHARACTERS = "*[[Denjiro|Kyoshiro]]"
CH927_SCENE_KOMURASAKI = (
    "She goes on to talk about the most famous courtesan in the country, "
    "[[Kouzuki Hiyori|Komurasaki]]."
)
CH927_NOTES = "**She works as a kamuro for the courtesan [[Kouzuki Hiyori|Komurasaki]]."
CH909_CHARACTERS = "*[[Kouzuki Hiyori|Komurasaki]]"
CH929_NOTES = (
    "*[[Nico Robin|Robin]], [[Kouzuki Hiyori|Komurasaki]], and [[Denjiro|Kyoshiro]] are at "
    "Orochi's banquet."
)
CH114_SCENE = (
    "The person is the mysterious figure that came out of explosion and is "
    "[[Nico Robin|Miss All Sunday]]."
)
CH114_NOTES = "*[[Nico Robin|Miss All Sunday]] is introduced."
CH114_CHARACTERS = "*[[Nico Robin|Miss All Sunday]]"
CH731_CHARACTERS = '*[[Sabo|"Lucy"]]'
CH735_NOTES = '*[[Sabo|"Lucy"]] enters the next match of the tournament.'
CH234_CHARACTERS = "*[[Polo Marco|Marco]]"
# Extrait réel du chapitre 436 (début abrégé) : surnom d'un navire, pas d'un Character
CH436_SCENE = (
    "[[Iceburg]] instead wakes, introducing the Straw Hats to their new ship, which he "
    "nicknames the \"[[Thousand Sunny|King of All Beasts]]\"."
)

COMMON_WORDS = frozenset({"the", "a", "an", "his", "her", "their", "this", "that"})


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


def bronze_record(number, long_summary, notes="*Note.", characters=""):
    """Enregistrement bronze minimal, tel que lu depuis chapters.jsonl."""
    wikitext = (
        "{{Chapter Box\n| title = Test\n}}\n"
        "==Short Summary==\nCourt résumé.\n\n"
        f"==Long Summary==\n{long_summary}\n\n"
        f"==Quick References==\n===Chapter Notes===\n{notes}\n"
        f'===Characters===\n{{|class="CharTable"\n|-\n|\n{characters}\n|}}\n'
    )
    return {"number": number, "revid": 1, "timestamp": "2026-01-01T00:00:00Z", "wikitext": wikitext}


def names_at(extraction, t):
    return {row.canonical_name for row in extraction.registry_at(t)}


def aliases_at(extraction, name, t):
    row = next(r for r in extraction.registry_at(t) if r.canonical_name == name)
    return set(row.aliases)


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


class TestAliases(unittest.TestCase):

    def extract(self, *records):
        return extract_entities(list(records), Reference(common_words=COMMON_WORDS))

    def test_piped_text_that_looks_like_a_name_is_an_alias(self):
        extraction = self.extract(bronze_record(552, CH552_SCENE))
        self.assertEqual(aliases_at(extraction, "Edward Newgate", 552), {"Whitebeard"})
        self.assertEqual(aliases_at(extraction, "Polo Marco", 552), {"Marco"})

    def test_lowercase_text_is_a_mention_but_not_an_alias(self):
        extraction = self.extract(
            bronze_record(223, CH223_SCENE),
            bronze_record(973, CH973_SCENE),
            bronze_record(1037, CH1037_SCENE),
        )
        for name, t in [("Marshall D. Teach", 223), ("Kouzuki Hiyori", 973), ("Gomu Gomu no Mi", 1037)]:
            self.assertEqual(aliases_at(extraction, name, t), set())
            self.assertEqual(state_at(extraction, name, t)[2], 1)

    def test_text_starting_with_a_common_word_is_not_an_alias(self):
        extraction = self.extract(bronze_record(1159, CH1159_SCENE))
        self.assertEqual(aliases_at(extraction, "Magnolia", 1159), set())
        self.assertEqual(state_at(extraction, "Magnolia", 1159)[2], 1)

    def test_subpage_or_section_text_is_never_an_alias(self):
        extraction = self.extract(bronze_record(1044, CH1044_SCENE), bronze_record(444, CH444_SCENE))
        self.assertEqual(aliases_at(extraction, "Gomu Gomu no Mi", 1044), set())
        self.assertEqual(aliases_at(extraction, "Haki", 1044), set())
        self.assertEqual(aliases_at(extraction, "Thousand Sunny", 444), set())

    def test_link_text_is_cleaned_before_becoming_an_alias(self):
        extraction = self.extract(
            bronze_record(75, CH75_SCENE),
            bronze_record(498, CH498_SCENE),
            bronze_record(927, CH927_SCENE),
        )
        self.assertEqual(aliases_at(extraction, "Arlong", 1193), set())
        self.assertEqual(
            aliases_at(extraction, "Silvers Rayleigh", 1193), {"Rayleigh the Bubble Coater"}
        )
        self.assertEqual(aliases_at(extraction, "Monkey D. Luffy", 1193), {"Luffy"})

    def test_possessive_and_typographic_apostrophe_are_normalised(self):
        extraction = self.extract(bronze_record(1123, CH1123_SCENE), bronze_record(1046, CH1046_SCENE))
        self.assertEqual(aliases_at(extraction, "Shanks", 1123), set())
        self.assertEqual(aliases_at(extraction, "Kin'emon", 1123), set())

    def test_alias_is_absent_before_its_first_use(self):
        extraction = self.extract(bronze_record(1, CH620_SCENE), bronze_record(2, CH552_SCENE))
        self.assertEqual(aliases_at(extraction, "Edward Newgate", 1), set())
        self.assertEqual(aliases_at(extraction, "Edward Newgate", 2), {"Whitebeard"})

    def test_alias_keeps_the_date_of_its_first_use(self):
        extraction = self.extract(
            bronze_record(1, CH552_SCENE), bronze_record(2, CH620_SCENE), bronze_record(3, CH552_SCENE)
        )
        rows = [r for r in extraction.registry if r.canonical_name == "Edward Newgate"]
        self.assertTrue(all(r.aliases == ("Whitebeard",) for r in rows))

    def test_joy_boy_and_nika_are_not_aliases_of_luffy(self):
        extraction = self.extract(
            bronze_record(927, CH927_SCENE), bronze_record(1044, CH1044_JOY_BOY_SCENE)
        )
        self.assertIn("Joy Boy", names_at(extraction, 1044))
        self.assertTrue(aliases_at(extraction, "Monkey D. Luffy", 1044).isdisjoint({"Joy Boy", "Nika"}))


class TestDisguiseCandidates(unittest.TestCase):
    """Chapitres réels où les liens du wiki résolvent des Disguises."""

    @classmethod
    def setUpClass(cls):
        cls.extraction = extract_entities([
            bronze_record(114, CH114_SCENE, notes=CH114_NOTES, characters=CH114_CHARACTERS),
            bronze_record(234, CH552_SCENE, characters=CH234_CHARACTERS),
            bronze_record(436, CH436_SCENE),
            bronze_record(731, CH620_SCENE, characters=CH731_CHARACTERS),
            bronze_record(735, CH620_SCENE, notes=CH735_NOTES),
            bronze_record(909, CH620_SCENE, characters=CH909_CHARACTERS),
            bronze_record(919, CH919_SCENE, characters=CH919_CHARACTERS),
            bronze_record(927, CH927_SCENE_KOMURASAKI, notes=CH927_NOTES),
            bronze_record(929, CH620_SCENE, notes=CH929_NOTES),
        ], Reference(common_words=COMMON_WORDS))
        cls.candidates = {
            (c.alias, c.canonical_name): c for c in cls.extraction.disguise_candidates
        }

    def test_hidden_identities_are_candidates(self):
        for pair in [("Kyoshiro", "Denjiro"), ("Komurasaki", "Kouzuki Hiyori"),
                     ("Lucy", "Sabo"), ("Miss All Sunday", "Nico Robin")]:
            self.assertIn(pair, self.candidates)

    def test_plain_aliases_are_not_candidates(self):
        self.assertNotIn(("Marco", "Polo Marco"), self.candidates)
        self.assertNotIn(("Robin", "Nico Robin"), self.candidates)

    def test_only_characters_are_candidates(self):
        # Thousand Sunny n'est dans aucune CharTable : ce n'est pas un Character.
        self.assertNotIn(("King of All Beasts", "Thousand Sunny"), self.candidates)

    def test_links_are_counted_in_long_summary_char_table_and_notes(self):
        kyoshiro = self.candidates[("Kyoshiro", "Denjiro")]
        self.assertEqual(
            (kyoshiro.link_count, kyoshiro.first_chapter, kyoshiro.last_chapter), (3, 919, 929)
        )
        lucy = self.candidates[("Lucy", "Sabo")]
        self.assertEqual((lucy.link_count, lucy.first_chapter, lucy.last_chapter), (2, 731, 735))

    def test_revelation_is_left_empty_for_a_human(self):
        self.assertTrue(all(c.revelation is None for c in self.extraction.disguise_candidates))

    def test_candidates_are_sorted_by_link_count(self):
        counts = [c.link_count for c in self.extraction.disguise_candidates]
        self.assertEqual(counts, sorted(counts, reverse=True))
        # Komurasaki : CharTable du 909, Long Summary et note du 927, note du 929
        self.assertEqual(self.extraction.disguise_candidates[0].alias, "Komurasaki")


if __name__ == "__main__":
    unittest.main()

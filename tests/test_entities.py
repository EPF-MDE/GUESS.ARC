"""Tests de l'extraction d'entités via son seul point d'entrée, sur des extraits réels du bronze. No network access."""
import pathlib
import tempfile
import unittest
from dataclasses import asdict

from guess_arc.entities import Reference, extract_entities
from guess_arc.entities.wiki_categories import load_category_cache, update_category_cache

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

# Extrait réel du chapitre 1027 (Wano Country Arc) : CharTable complète et les deux
# premiers paragraphes du Long Summary.
CH1027_CHARACTERS = """{| class="CharTable"
! colspan="2" |[[Pirates]]
! Citizens
|-
|
;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Roronoa Zoro]]
*[[Franky]]
----
;[[Roger Pirates]]
*[[Gol D. Roger]] ''(cover)''
*[[Shanks]] ''(cover)''
*[[Buggy]] ''(cover)''
|
;[[Beasts Pirates]]
*[[Kaidou]]
*[[King]]
*[[Queen]]
----
;[[Big Mom Pirates]]
*[[Charlotte Perospero]]
----
;Other
*[[Yamato]]
|
;[[Wano Country]]
*[[Kouzuki Momonosuke]]
*[[Kin'emon]] ''(flashback)''
----
;[[Mokomo Dukedom]]
*[[Nekomamushi]]
*[[Shishilian]]
*[[Wanda]]
*[[Carrot]]
|}"""
CH1027_LONG_SUMMARY = (
    "Following his victory, [[Nekomamushi]] covers his eyes to return to his normal form as "
    "[[Carrot]] hugs him in delight. He advises her and [[Wanda]] not to look at the moon or "
    "they will transform, just as he wonders how the skies parted and allowed the moon to "
    "return.\n\n"
    "On the roof, [[Yamato]] and [[Kouzuki Momonosuke|Momonosuke]] watch in awe at "
    "[[Monkey D. Luffy|Luffy]] and [[Kaidou]]'s clash, and Yamato and Momonosuke remember "
    "[[Kouzuki Oden|Oden]] writing about how [[Gol D. Roger|Roger]] and "
    "[[Edward Newgate|Whitebeard]]'s clash split the heavens."
)
# Extrait réel de la CharTable du chapitre 552 (Marineford Arc), abrégé
CH552_CHARACTERS = """;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Tony Tony Chopper]] ''(cover)''
----
;[[Whitebeard Pirates]]
*[[Edward Newgate]]
*[[Portgas D. Ace]]
*[[Polo Marco|Marco]]
*[[Thatch]] ''(flashback)''
----
;[[Red Hair Pirates]]
*[[Shanks]] ''(flashback)''"""

# Extrait réel du chapitre 1000 : deux premiers paragraphes du Long Summary (le second
# abrégé). Le wiki ne lie Luffy, Yamato, Oden, Momonosuke qu'à leur première occurrence.
CH1000_LONG_SUMMARY = (
    "Finally reaching the fifth floor, [[Monkey D. Luffy|Luffy]] comes across the "
    "[[Inuarashi Musketeer Squad]], who have cleared the way to the roof and ask him to continue "
    "onwards. Luffy thanks [[Shishilian]] and makes his way to the roof, while also telling all "
    "of them that he remembers how they defended [[Raizo]] with their lives, which causes "
    "Shishilian to tear up. On the Live Floor, [[Polo Marco|Marco]] uses his flames to hold "
    "[[Queen]] (who is shown to have a mechanical elongated neck) and [[King]] back while he "
    "throws [[Roronoa Zoro|Zoro]] up to the roof, much to his chagrin though.\n\n"
    "In the storage room, [[Yamato]] returns [[Kouzuki Oden|Oden]]'s journal to "
    "[[Kouzuki Momonosuke|Momonosuke]], revealing he had believed he had died twenty years ago, "
    "and he never expected a day he could meet him. Yamato also reveals he found the journal "
    "near the river at the foot of Oden's Castle that day long ago and says that someone must "
    "have protected it, since it has written about his life and time traveling the world. "
    "Yamato asks if Momonosuke was born on [[Edward Newgate|Whitebeard]]'s ship and he even "
    "sailed on [[Gol D. Roger|Roger]]'s ship and explains that Oden and the [[Roger Pirates]] "
    "predicted that a little over twenty years in the future, a new generation of pirates would "
    "advance to the [[New World]], and he believe they were talking about this very moment."
)
# Extrait réel de la CharTable du chapitre 1000, abrégé : Oden n'y est pas.
CH1000_CHARACTERS = """;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Roronoa Zoro]]
----
;Other
*[[Yamato]]
|
;[[Beasts Pirates]]
*[[King]]
*[[Queen]]
----
;[[Whitebeard Pirates]]
*[[Polo Marco|Marco]]
|
;[[Wano Country]]
*[[Kouzuki Momonosuke]]
*[[Raizo]]
----
;[[Mokomo Dukedom]]
*[[Shishilian]]"""
# Extraits réels : "queen" en minuscule (ch. 593), "Queen" non lié (ch. 991)
CH593_LOWERCASE_QUEEN = (
    "After arguing with the queen and getting beaten up by him, Sanji manages to learn the news "
    "regarding Luffy in a newspaper, being astonished by it."
)
CH991_UNLINKED_QUEEN = (
    "However, bullets suddenly come flying down onto the Live Floor from above, and Queen calls "
    "out to Drake from the Live Stage while holding a Gatling gun."
)

# Extrait réel du chapitre 11 : un Devil Fruit précis et le Concept générique
CH11_SCENE = (
    "Buggy floats behind Zoro as he finds himself fighting the hand and boasts about his "
    "[[Devil Fruit]] powers, the [[Bara Bara no Mi]]."
)

# Entrées réelles des datasets de reference/ (champs image, description, journey et
# relationships ôtés). Les attributs d'état (affiliation, status, bounty, ruler)
# sont gardés : ils ne doivent pas entrer dans Registry(t).
CHARACTERS = (
    {"name": "Edward Newgate [Whitebeard]", "epithet": "the Strongest Man in the World",
     "affiliation": "Whitebeard Pirates", "devil_fruit": "Gura Gura no Mi", "bounty": 5046000000,
     "origin": "Grand Line (Sphinx)", "first_appearance_arc": "Chapter 234", "race": "Human",
     "status": "Deceased"},
    {"name": "Scien [Queen]", "epithet": "the Plague", "affiliation": "Beasts Pirates",
     "bounty": 1320000000, "first_appearance_arc": "Chapter 920", "race": "Human",
     "status": "Alive"},
    {"name": "Sphinx", "affiliation": "Impel Down", "first_appearance_arc": "Chapter 529",
     "race": "Human", "status": "Alive"},
    {"name": "Bentham (Bon Clay) [Mr. 2]", "affiliation": "Baroque Works", "status": "Alive"},
)
ISLANDS = (
    {"name": "Dawn Island", "location": "East Blue", "current_ruler": "Sterry (Goa Kingdom)",
     "notable_members": ["Makino", "Woop Slap", "Sterry", "Curly Dadan", "Outlook III"]},
    {"name": "Sphinx", "location": "New World", "current_ruler": "Unknown",
     "notable_members": ["Marco", "Oide", "Tama"]},
)
DEVIL_FRUITS = (
    {"name": " Bara Bara no Mi", "english": "Chop-Chop Fruit", "type": "Paramecia",
     "user": "Buggy"},
    {"name": " Ope Ope no Mi (Awakened)", "english": "Op-Op Fruit", "type": "Paramecia",
     "user": "Trafalgar D. Water Law"},
)
CONCEPTS = frozenset({"Pirate", "Haki", "Devil Fruit", "Admiral", "Marine Ranks",
                      "Seven Warlords of the Sea"})

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


def bronze_record(number, long_summary, notes="*Note.", characters="", arc="Test Arc"):
    """Enregistrement bronze minimal, tel que lu depuis chapters.jsonl."""
    if not characters.startswith("{|"):
        characters = f'{{|class="CharTable"\n|-\n|\n{characters}\n|}}'
    wikitext = (
        "{{Chapter Box\n| title = Test\n}}\n"
        "==Short Summary==\nCourt résumé.\n\n"
        f"==Long Summary==\n{long_summary}\n\n"
        f"==Quick References==\n===Chapter Notes===\n{notes}\n"
        f"===Characters===\n{characters}\n\n"
        f"==Site Navigation==\n{{{{{arc}}}}}\n"
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


class TestCast(unittest.TestCase):
    """Chapitre 1027 (Wano) et 552 (Marineford) avec leur CharTable."""

    @classmethod
    def setUpClass(cls):
        cls.extraction = extract_entities([
            bronze_record(1027, CH1027_LONG_SUMMARY, characters=CH1027_CHARACTERS,
                          arc="Wano Country Arc"),
            bronze_record(552, CH552_SCENE, characters=CH552_CHARACTERS, arc="Marineford Arc"),
        ], Reference())

    def test_character_only_in_the_char_table_enters_the_registry(self):
        self.assertIn("Roronoa Zoro", names_at(self.extraction, 1027))
        self.assertIn("Shishilian", names_at(self.extraction, 1027))
        self.assertNotIn("Roronoa Zoro", names_at(self.extraction, 552))
        self.assertEqual(state_at(self.extraction, "Roronoa Zoro", 1027), (1027, 1027, 0))

    def test_recall_and_cover_appearance_enter_the_registry(self):
        self.assertIn("Kin'emon", names_at(self.extraction, 1027))      # (flashback)
        self.assertIn("Buggy", names_at(self.extraction, 1027))         # (cover)
        self.assertIn("Tony Tony Chopper", names_at(self.extraction, 552))  # (cover)

    def test_char_table_presence_updates_last_chapter_seen(self):
        # Shanks : 2 Mentions au 552 (le lien et "Shanks is coming"), puis seulement
        # une Cover appearance au 1027.
        self.assertEqual(state_at(self.extraction, "Shanks", 1027), (552, 1027, 2))

    def test_linked_faction_header_adds_its_group_without_a_mention(self):
        names = names_at(self.extraction, 1027)
        self.assertIn("Beasts Pirates", names)
        self.assertIn("Mokomo Dukedom", names)
        self.assertEqual(state_at(self.extraction, "Beasts Pirates", 1027)[2], 0)
        self.assertEqual(state_at(self.extraction, "Straw Hat Pirates", 1027), (552, 1027, 0))

    def test_unlinked_headers_and_column_titles_add_nothing(self):
        names = names_at(self.extraction, 1027)
        self.assertNotIn("Other", names)
        self.assertNotIn("Pirates", names)
        self.assertNotIn("Citizens", names)

    def test_recall_proxy_overall_and_per_arc(self):
        # 1027 : 13 Appearances, 7 avec une Mention (Nekomamushi, Carrot, Wanda, Yamato,
        # Momonosuke, Luffy, Kaidou). 552 : 4 Appearances (Luffy, Newgate, Ace, Marco),
        # 2 avec une Mention (Newgate, Marco).
        quality = self.extraction.quality
        self.assertAlmostEqual(quality.recall_proxy, 9 / 17)
        self.assertEqual(quality.recall_proxy_per_arc,
                         {"Marineford Arc": 2 / 4, "Wano Country Arc": 7 / 13})


def mention_count(extraction, name, t):
    return state_at(extraction, name, t)[2]


class TestAliasMatch(unittest.TestCase):

    def test_unlinked_occurrences_of_linked_entities_are_mentions(self):
        extraction = extract_entities([bronze_record(1000, CH1000_LONG_SUMMARY)], Reference())
        self.assertEqual(mention_count(extraction, "Monkey D. Luffy", 1000), 2)
        self.assertEqual(mention_count(extraction, "Shishilian", 1000), 2)
        self.assertEqual(mention_count(extraction, "Yamato", 1000), 3)
        self.assertEqual(mention_count(extraction, "Kouzuki Oden", 1000), 3)
        self.assertEqual(mention_count(extraction, "Kouzuki Momonosuke", 1000), 2)

    def test_each_mention_carries_its_source(self):
        extraction = extract_entities([bronze_record(1000, CH1000_LONG_SUMMARY)], Reference())
        # 15 liens d'articles ; Luffy, Shishilian, Momonosuke x1, Yamato, Oden x2 non liés.
        self.assertEqual(extraction.quality.mentions_by_source, {"link": 15, "alias_match": 7})

    def test_match_is_case_sensitive(self):
        extraction = extract_entities([bronze_record(
            1000, CH1000_LONG_SUMMARY + "\n\n" + CH593_LOWERCASE_QUEEN + " " + CH991_UNLINKED_QUEEN
        )], Reference())
        self.assertEqual(mention_count(extraction, "Queen", 1000), 2)  # le lien + "Queen calls"

    def test_entity_not_linked_in_the_chapter_is_not_matched(self):
        extraction = extract_entities([
            bronze_record(1000, CH1000_LONG_SUMMARY),
            bronze_record(991, CH991_UNLINKED_QUEEN),
        ], Reference())
        self.assertNotIn("Queen", names_at(extraction, 991))

    def test_alias_not_yet_dated_is_not_matched(self):
        # ch. 1 : [[Edward Newgate]] lié, "Whitebeard" écrit sans lien, pas encore un Alias.
        # ch. 2 : [[Edward Newgate|Whitebeard]] date l'Alias ; ses occurrences non liées comptent.
        ch1 = CH620_SCENE + "\n\n" + CH590_LONG_SUMMARY
        ch2 = CH552_SCENE + "\n\n" + CH590_LONG_SUMMARY
        extraction = extract_entities([bronze_record(1, ch1), bronze_record(2, ch2)], Reference())
        # ch. 1 : le lien + "Edward Newgate" en clair (Canonical name), pas "Whitebeard".
        self.assertEqual(mention_count(extraction, "Edward Newgate", 1), 2)
        # ch. 2 : le lien, "Whitebeard's men", "The Whitebeard and..." et "Edward Newgate".
        self.assertEqual(mention_count(extraction, "Edward Newgate", 2), 6)

    def test_precision_proxy_and_suspicious_aliases(self):
        extraction = extract_entities([
            bronze_record(1000, CH1000_LONG_SUMMARY, characters=CH1000_CHARACTERS),
            # Oden est un Character : il figure dans une autre CharTable.
            bronze_record(960, CH620_SCENE, characters="*[[Kouzuki Oden]]"),
        ], Reference())
        quality = extraction.quality
        # 7 Mentions par Alias match de Characters, dont 5 dans le Cast du 1000
        # (Oden x2 n'y est pas).
        self.assertAlmostEqual(quality.precision_proxy, 5 / 7)
        top = quality.suspicious_aliases[0]
        self.assertEqual((top.alias, top.canonical_name, top.matches, top.outside_cast),
                         ("Oden", "Kouzuki Oden", 2, 2))
        self.assertTrue(all(s.outside_cast > 0 for s in quality.suspicious_aliases))


def type_of(extraction, name, t):
    return next(r for r in extraction.registry_at(t) if r.canonical_name == name).entity_type


class TestEntityTypesFromDatasets(unittest.TestCase):

    def extract(self, *records):
        return extract_entities(list(records), Reference(
            characters=CHARACTERS, islands=ISLANDS, devil_fruits=DEVIL_FRUITS, concepts=CONCEPTS,
        ))

    def test_character_is_typed_without_its_bracketed_epithet(self):
        extraction = self.extract(bronze_record(552, CH552_SCENE))
        self.assertEqual(type_of(extraction, "Edward Newgate", 552), "Character")

    def test_bracketed_epithet_also_names_the_character(self):
        # Le wiki titre la page "Queen" ; le dataset écrit "Scien [Queen]".
        extraction = self.extract(bronze_record(1000, CH1000_LONG_SUMMARY))
        self.assertEqual(type_of(extraction, "Queen", 1000), "Character")

    def test_trailing_parenthesis_of_a_dataset_name_is_dropped(self):
        # "Bentham (Bon Clay) [Mr. 2]" et " Ope Ope no Mi (Awakened)" dans les datasets
        extraction = self.extract(
            bronze_record(534, "[[Bentham]] pleads with Luffy to get away from Magellan, "
                               "revealing that the Warden ate the [[Doku Doku no Mi]]."),
            bronze_record(661, "Smoker flies at Law, saying the [[Ope Ope no Mi]] allows the "
                               "consumer to make a space they can modify at will."),
        )
        self.assertEqual(type_of(extraction, "Bentham", 534), "Character")
        self.assertEqual(type_of(extraction, "Ope Ope no Mi", 661), "Devil Fruit")

    def test_devil_fruit_and_its_english_name_are_one_entity(self):
        # Le bronze ne lie jamais un fruit par son nom anglais : 2e phrase écrite pour le test.
        extraction = self.extract(
            bronze_record(11, CH11_SCENE),
            bronze_record(12, "Buggy has eaten the [[Chop-Chop Fruit]]."),
        )
        self.assertNotIn("Chop-Chop Fruit", names_at(extraction, 12))
        self.assertEqual(type_of(extraction, "Bara Bara no Mi", 12), "Devil Fruit")
        self.assertEqual(mention_count(extraction, "Bara Bara no Mi", 12), 2)

    def test_island_is_typed_place(self):
        extraction = self.extract(bronze_record(
            956, "On the way back to [[Dawn Island]], [[Sterry]] is also shocked by the fact "
                 "that Sabo was at [[Mary Geoise]]."
        ))
        self.assertEqual(type_of(extraction, "Dawn Island", 956), "Place")

    def test_name_in_two_datasets_stays_unknown(self):
        # "Sphinx" est à la fois un Character (Impel Down) et une île dans les datasets.
        # Phrase écrite pour le test.
        extraction = self.extract(bronze_record(529, "[[Sphinx]] guards Level 2."))
        self.assertEqual(type_of(extraction, "Sphinx", 529), "Unknown")

    def test_untyped_entity_is_unknown(self):
        extraction = self.extract(bronze_record(552, CH552_SCENE))
        self.assertEqual(type_of(extraction, "Marineford", 552), "Unknown")

    def test_concepts_and_titles_are_not_in_the_registry(self):
        extraction = self.extract(
            bronze_record(4, CH4_SCENE),
            bronze_record(11, CH11_SCENE),
            bronze_record(552, CH552_SCENE, characters=";[[Admiral]]s\n*[[Borsalino|Kizaru]]"),
        )
        names = {r.canonical_name for r in extraction.registry}
        for concept in ("Pirate", "Devil Fruit", "Admiral"):
            self.assertNotIn(concept, names)
        self.assertIn("Borsalino", names_at(extraction, 552))

    def test_no_dataset_state_attribute_enters_the_registry(self):
        extraction = self.extract(bronze_record(552, CH552_SCENE))
        row = next(r for r in extraction.registry if r.canonical_name == "Edward Newgate")
        published = " ".join(str(v) for v in asdict(row).values())
        for value in ("Whitebeard Pirates", "Deceased", "5046000000", "Gura Gura no Mi", "Human"):
            self.assertNotIn(value, published)

    def test_quality_report_has_the_unknown_share_of_mentions(self):
        # CH552 : Marineford, Marines, Shanks, Edward Newgate, Polo Marco ([[pirate]] exclu),
        # plus "Whitebeard's men" et "Shanks is coming" : 7 Mentions, dont les 2 d'Edward
        # Newgate typées.
        extraction = self.extract(bronze_record(552, CH552_SCENE))
        self.assertAlmostEqual(extraction.quality.unknown_mention_share, 5 / 7)


# Catégories réelles du wiki (API MediaWiki, catégories cachées exclues)
WIKI_CATEGORIES = {
    "Straw Hat Pirates": ("East Blue Pirate Crews", "Four Emperors Groups", "Straw Hat Pirates",
                          "Super Rookie Crews", "Worst Generation Crews"),
    "Thousand Sunny": ("Four Emperors' Ships", "Straw Hat Pirates' Ships",
                       "Worst Generation's Ships"),
    "Enma": ("Great Grade Blades", "Straw Hat Pirates' Weapons", "Swords"),
    "Marines": ("Antagonist Groups", "Fleets", "Marine", "Military Forces",
                "World Government Groups"),
    "Wano Country": ("Four Emperors Territories", "New World Locations", "Regimes"),
    "Den Den Mushi": ("Animal Species", "Technology"),
    "Gomu Gomu no Mi": ("Devil Fruits with Multiple Users", "Mythical Zoan", "Paramecia",
                        "Shown Devil Fruits"),
    "Sphinx": ("Impel Down Staff", "Summit War Saga Antagonists", "Talking Animals"),
    "Three Sword Style": ("Fighting Styles",),
    "Edward Newgate": ("Pirate Captains", "Fleets"),  # extrait fictif : le dataset l'emporte
}
# Phrase écrite pour le test, qui lie d'un coup les Entities ci-dessus
CH1065_SCENE = (
    "The [[Straw Hat Pirates]] arrive on the [[Thousand Sunny]], while [[Roronoa Zoro|Zoro]] "
    "holds [[Enma]]; the [[Marines]] contact them by [[Den Den Mushi]] from [[Wano Country]]."
)


def typed_extraction(*records, overrides=None):
    return extract_entities(list(records), Reference(
        characters=CHARACTERS, islands=ISLANDS, devil_fruits=DEVIL_FRUITS, concepts=CONCEPTS,
        wiki_categories=WIKI_CATEGORIES, type_overrides=overrides or {},
    ))


class TestEntityTypesFromWikiCategories(unittest.TestCase):

    def test_categories_type_what_the_datasets_do_not_cover(self):
        extraction = typed_extraction(bronze_record(1065, CH1065_SCENE))
        expected = {"Straw Hat Pirates": "Group", "Thousand Sunny": "Ship", "Enma": "Weapon",
                    "Marines": "Group", "Wano Country": "Place", "Den Den Mushi": "Object"}
        for name, entity_type in expected.items():
            self.assertEqual(type_of(extraction, name, 1065), entity_type, name)

    def test_devil_fruit_categories_beat_the_users_category(self):
        extraction = typed_extraction(bronze_record(1044, CH1044_SCENE))
        self.assertEqual(type_of(extraction, "Gomu Gomu no Mi", 1044), "Devil Fruit")

    def test_categories_settle_a_name_found_in_two_datasets(self):
        extraction = typed_extraction(bronze_record(529, "[[Sphinx]] guards Level 2."))
        self.assertEqual(type_of(extraction, "Sphinx", 529), "Character")

    def test_datasets_beat_the_categories(self):
        extraction = typed_extraction(bronze_record(552, CH552_SCENE))
        self.assertEqual(type_of(extraction, "Edward Newgate", 552), "Character")

    def test_unmapped_categories_leave_the_entity_unknown(self):
        extraction = typed_extraction(bronze_record(
            1, "[[Roronoa Zoro|Zoro]] uses [[Three Sword Style]]."
        ))
        self.assertEqual(type_of(extraction, "Three Sword Style", 1), "Unknown")

    def test_override_beats_datasets_and_categories(self):
        extraction = typed_extraction(
            bronze_record(552, CH552_SCENE), bronze_record(1065, CH1065_SCENE),
            overrides={"Edward Newgate": "Group", "Wano Country": "Group"},
        )
        self.assertEqual(type_of(extraction, "Edward Newgate", 552), "Group")
        self.assertEqual(type_of(extraction, "Wano Country", 1065), "Group")

    def test_override_with_an_unknown_type_is_refused(self):
        with self.assertRaises(ValueError):
            typed_extraction(bronze_record(552, CH552_SCENE), overrides={"Shanks": "Pirate"})

    def test_each_entity_has_one_type_for_the_whole_story(self):
        extraction = typed_extraction(
            bronze_record(552, CH552_SCENE), bronze_record(1000, CH1000_LONG_SUMMARY),
            bronze_record(1065, CH1065_SCENE),
        )
        types = {}
        for row in extraction.registry:
            types.setdefault(row.canonical_name, set()).add(row.entity_type)
        self.assertTrue(all(len(t) == 1 for t in types.values()))

    def test_quality_report_lists_the_top_entities_with_their_type(self):
        extraction = typed_extraction(
            bronze_record(552, CH552_SCENE), bronze_record(1000, CH1000_LONG_SUMMARY),
        )
        top = extraction.quality.top_entities
        self.assertLessEqual(len(top), 50)
        # 3 Mentions chacun ; à égalité, ordre alphabétique
        self.assertEqual([(e.canonical_name, e.mention_count) for e in top[:3]],
                         [("Edward Newgate", 3), ("Kouzuki Oden", 3), ("Yamato", 3)])
        counts = [e.mention_count for e in top]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(next(e for e in top if e.canonical_name == "Edward Newgate").entity_type,
                         "Character")


class TestWikiCategoryCache(unittest.TestCase):

    def test_categories_are_fetched_in_batches_then_read_from_the_cache(self):
        calls = []

        def fake_fetch(titles):
            calls.append(list(titles))
            return {t: ["Swords"] for t in titles}

        with tempfile.TemporaryDirectory() as tmp:
            cache = pathlib.Path(tmp) / "wiki_categories.json"
            titles = [f"Sword {i}" for i in range(120)]
            fetched = update_category_cache(cache, titles, fake_fetch, batch=50)
            self.assertEqual(fetched, 120)
            self.assertEqual([len(c) for c in calls], [50, 50, 20])
            self.assertEqual(load_category_cache(cache)["Sword 7"], ("Swords",))

            calls.clear()
            self.assertEqual(update_category_cache(cache, titles, fake_fetch, batch=50), 0)
            self.assertEqual(calls, [])


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

"""Contrôles des événements `llm` (preuve, fuite du futur, doublons), à travers le pipeline.

Mêmes chapitres synthétiques et même client factice que test_events_llm, plus
une mini-fiche d'entités : Kaido n'apparaît qu'au chapitre 900, la première
apparition d'Usopp n'est datée d'aucun chapitre.
"""
import json
import unittest

from guess_arc import paths
from test_events_llm import LlmTestCase, char, chapter, llm_event as _llm_event, response

CHARACTERS = [
    {"name": "Monkey D. Luffy", "first_appearance_arc": "Chapter 1"},
    {"name": "Roronoa Zoro", "first_appearance_arc": "Chapter 1"},
    {"name": "Kaido", "first_appearance_arc": "Chapter 900"},
    {"name": "Usopp", "first_appearance_arc": "Anime Episode 9"},
]


def llm_event(type_="combat", names=("Monkey D. Luffy", "Roronoa Zoro"), **fields):
    fields.setdefault("evidence", "fights Zoro.")
    return _llm_event(type_, names, **fields)


class ChecksTestCase(LlmTestCase):
    long_summary = 'Luffy shouts “I’m gonna be King of the Pirates!”  and\nfights Zoro.'

    def setUp(self):
        super().setUp()
        entity_dir = paths.entities_dir(self.data_dir)
        entity_dir.mkdir(parents=True)
        (entity_dir / "characters.json").write_text(json.dumps(CHARACTERS), encoding="utf-8")
        self.write_silver(chapter(1, char("Luffy"), char("Zoro"),
                                  long_summary=self.long_summary))

    def llm_events(self, *events, unlisted=()):
        self.extract(response(1, *events, unlisted=unlisted))
        self.document = self.output(1)
        return [e for e in self.document["events"] if e["origin"] == "llm"]

    def checks(self, **fields):
        [event] = self.llm_events(llm_event(**fields))
        return event["checks"]


class TestEvidence(ChecksTestCase):
    def test_evidence_copied_from_the_text_is_found(self):
        self.assertTrue(self.checks(evidence="fights Zoro.")["evidence_found"])

    def test_evidence_found_up_to_quotes_and_spaces(self):
        evidence = 'shouts "I\'m gonna be King of the Pirates!" and fights'
        self.assertTrue(self.checks(evidence=evidence)["evidence_found"])

    def test_evidence_absent_from_the_text(self):
        self.assertFalse(self.checks(evidence="Luffy eats meat.")["evidence_found"])


class TestFutureLeak(ChecksTestCase):
    def test_present_characters_are_no_leak(self):
        self.assertFalse(self.checks(description="Luffy fights Zoro.")["future_leak"])

    def test_future_character_in_description(self):
        self.assertTrue(self.checks(description="Luffy fights like Kaido.")["future_leak"])

    def test_undated_character_is_no_leak(self):
        self.assertFalse(self.checks(description="Luffy fights like Usopp.")["future_leak"])

    def test_future_words_in_description(self):
        for description in ("Zoro will join Luffy.", "Luffy later fights Zoro.",
                            "Luffy dreams of his Future crew."):
            with self.subTest(description=description):
                self.assertTrue(self.checks(description=description)["future_leak"])

    def test_future_word_inside_another_word_is_no_leak(self):
        self.assertFalse(self.checks(description="Zoro shows his willpower.")["future_leak"])

    def test_future_character_in_unlisted_entities(self):
        self.llm_events(llm_event(), unlisted=["Koby", "Kaido"])
        self.assertEqual(self.document["unlisted_checks"], {"future_leak": True})

    def test_future_character_in_lowercase_in_unlisted_entities(self):
        self.llm_events(llm_event(), unlisted=["kaido"])
        self.assertEqual(self.document["unlisted_checks"], {"future_leak": True})

    def test_unknown_unlisted_entity_is_no_leak(self):
        self.llm_events(llm_event(), unlisted=["Koby"])
        self.assertEqual(self.document["unlisted_checks"], {"future_leak": False})


class TestFailedChecksKept(ChecksTestCase):
    def test_failed_events_are_marked_not_removed(self):
        events = self.llm_events(
            llm_event(evidence="Luffy eats meat."),
            llm_event("defeat", ("Roronoa Zoro",), description="Kaido will defeat Zoro."),
        )
        self.assertEqual([e["checks"] for e in events], [
            {"evidence_found": False, "future_leak": False},
            {"evidence_found": True, "future_leak": True},
        ])

    def test_wiki_events_have_no_checks(self):
        self.llm_events(llm_event())
        wiki = [e for e in self.document["events"] if e["origin"] == "wiki"]
        self.assertTrue(wiki)
        self.assertTrue(all("checks" not in e for e in wiki))


class TestDuplicates(ChecksTestCase):
    def test_exact_duplicates_removed_and_counted(self):
        events = self.llm_events(llm_event(), llm_event("defeat", ("Roronoa Zoro",)),
                                 llm_event(), llm_event())
        self.assertEqual([e["type"] for e in events], ["combat", "defeat"])
        self.assertEqual(self.document["meta"]["duplicates_removed"], 2)

    def test_near_duplicates_are_kept(self):
        events = self.llm_events(llm_event(), llm_event(description="Again."))
        self.assertEqual(len(events), 2)
        self.assertEqual(self.document["meta"]["duplicates_removed"], 0)


if __name__ == "__main__":
    unittest.main()

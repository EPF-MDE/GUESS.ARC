"""Prompt système et schéma JSON de l'appel au modèle, à travers le pipeline `--dry-run`.

Chapitres silver synthétiques écrits dans un dossier de données temporaire,
puis lecture de ce que `--dry-run` écrit sous `data/event/` : prompt système et
schéma de base dans `prompt/`, schéma final par chapitre dans `schema/`.
Sans réseau ni modèle.
"""
import json
import re
import tempfile
import unittest

import jsonschema
from pathlib import Path

from guess_arc import paths
from guess_arc.events.pipeline import run
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

LLM_TYPES = {
    "combat", "defeat", "death", "injury", "capture", "escape_rescue", "recruitment",
    "departure", "arrival", "alliance", "betrayal", "revelation", "power_reveal",
    "reunion", "status_change", "declaration", "acquisition", "celebration",
    "world_reaction", "other",
}
EVENT_FIELDS = ["evidence", "source", "type", "description", "participants",
                "location", "status", "in_flashback"]
# Mots-clés de validation permis, plus `properties` et `items` qui décrivent la structure.
ALLOWED_KEYWORDS = {"type", "enum", "required", "additionalProperties", "properties", "items"}


def char(name, *appearance):
    excluded = {"cover", "flashback", "mentioned", "dream"}
    return {"name": name, "faction": "Some Faction",
            "on_panel": not excluded & set(appearance), "appearance": list(appearance)}


def chapter(number, *characters, text="Nothing happens."):
    return Chapter(number=number, title=f"Title {number}", arc="A Arc",
                   revision_id=1000 + number, revised_at="2025-01-01T00:00:00Z",
                   characters=list(characters), short_summary="Short summary.",
                   long_summary=text, notes=[], complete=True)


def keywords(schema):
    """Mots-clés utilisés à tous les niveaux du schéma (hors noms de propriétés)."""
    found = set(schema)
    for sub in schema.get("properties", {}).values():
        found |= keywords(sub)
    if isinstance(schema.get("items"), dict):
        found |= keywords(schema["items"])
    return found


class PromptTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_silver(self, *chapters):
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(self.data_dir))

    def dry_run(self):
        run(data_dir=self.data_dir, dry_run=True,
            review_path=self.data_dir / "no_review.json")

    def front(self, number):
        text = (paths.event_in_dir(self.data_dir) / f"events_{number:04d}.md").read_text(
            encoding="utf-8")
        return FRONT_MATTER_RE.match(text).group(1)

    def version(self, number, key):
        return re.search(rf'(?m)^{key}: "(v\d+)"$', self.front(number)).group(1)

    def allowed_names(self, number):
        block = re.search(r"(?ms)^allowed_names:(.*?)(?=^\S|\Z)", self.front(number)).group(1)
        if block.strip() == "[]":
            return []
        return [json.loads(line.strip()[2:]) for line in block.strip().splitlines()]

    def system_prompt(self, version):
        return (paths.event_prompt_dir(self.data_dir) / f"system_{version}.md").read_text(
            encoding="utf-8")

    def base_schema(self, version):
        return json.loads((paths.event_prompt_dir(self.data_dir) / f"schema_{version}.json")
                          .read_text(encoding="utf-8"))

    def chapter_schema(self, number):
        return json.loads((paths.event_schema_dir(self.data_dir) / f"events_{number:04d}.json")
                          .read_text(encoding="utf-8"))

    def event_schema(self, schema):
        return schema["properties"]["events"]["items"]


class TestFilesWritten(PromptTestCase):
    def test_dry_run_writes_prompt_base_schema_and_chapter_schemas(self):
        self.write_silver(chapter(1, char("Monkey D. Luffy")), chapter(2, char("Nami")))
        self.dry_run()
        prompt_version = self.version(1, "prompt_version")
        schema_version = self.version(1, "schema_version")
        self.assertTrue(self.system_prompt(prompt_version).strip())
        self.assertEqual(self.base_schema(schema_version)["type"], "object")
        for number in (1, 2):
            self.assertEqual(self.chapter_schema(number)["type"], "object")

    def test_versions_are_the_same_in_every_input(self):
        self.write_silver(chapter(1), chapter(2))
        self.dry_run()
        for key in ("prompt_version", "schema_version"):
            self.assertEqual(self.version(1, key), self.version(2, key))


class TestSchema(PromptTestCase):
    def setUp(self):
        super().setUp()
        self.write_silver(chapter(5, char("Monkey D. Luffy"), char("Roronoa Zoro"),
                                  char("Nami", "cover")))
        self.dry_run()
        self.base = self.base_schema(self.version(5, "schema_version"))
        self.final = self.chapter_schema(5)

    def test_participant_enum_is_exactly_the_allowed_names(self):
        names = self.allowed_names(5)
        self.assertEqual(names, ["Monkey D. Luffy", "Roronoa Zoro"])
        participant = self.event_schema(self.final)["properties"]["participants"]["items"]
        self.assertEqual(participant["properties"]["name"]["enum"], names)

    def test_final_schema_differs_from_base_only_by_the_names(self):
        participant = self.event_schema(self.base)["properties"]["participants"]["items"]
        participant["properties"]["name"]["enum"] = self.allowed_names(5)
        self.assertEqual(self.base, self.final)

    def test_only_permitted_keywords(self):
        for schema in (self.base, self.final):
            self.assertLessEqual(keywords(schema), ALLOWED_KEYWORDS)

    def test_root_fields_all_required(self):
        self.assertEqual(list(self.final["properties"]),
                         ["chapter", "events", "unlisted_entities"])
        self.assertEqual(self.final["required"], ["chapter", "events", "unlisted_entities"])
        self.assertIs(self.final["additionalProperties"], False)
        self.assertEqual(self.final["properties"]["chapter"]["type"], "integer")
        self.assertEqual(self.final["properties"]["unlisted_entities"]["items"]["type"],
                         "string")

    def test_event_fields_in_order_all_required_no_extra(self):
        event = self.event_schema(self.final)
        self.assertEqual(list(event["properties"]), EVENT_FIELDS)
        self.assertEqual(event["required"], EVENT_FIELDS)
        self.assertIs(event["additionalProperties"], False)
        participant = event["properties"]["participants"]["items"]
        self.assertEqual(participant["required"], ["name", "role"])
        self.assertIs(participant["additionalProperties"], False)

    def test_enums(self):
        props = self.event_schema(self.final)["properties"]
        self.assertEqual(props["source"]["enum"],
                         ["long_summary", "short_summary", "chapter_notes"])
        self.assertEqual(props["status"]["enum"], ["single", "start", "ongoing", "end"])
        self.assertEqual(props["participants"]["items"]["properties"]["role"]["enum"],
                         ["agent", "target", "other"])
        self.assertEqual(props["in_flashback"]["type"], "boolean")
        self.assertEqual(props["location"]["type"], "string")

    def test_type_enum_is_the_twenty_llm_types(self):
        types = self.event_schema(self.final)["properties"]["type"]["enum"]
        self.assertEqual(len(types), 20)
        self.assertEqual(set(types), LLM_TYPES)
        self.assertNotIn("first_appearance", types)
        self.assertNotIn("return", types)


class TestSystemPrompt(PromptTestCase):
    def setUp(self):
        super().setUp()
        self.write_silver(chapter(1, char("Monkey D. Luffy")))
        self.dry_run()
        self.prompt = self.system_prompt(self.version(1, "prompt_version"))

    def test_does_not_start_with_the_thinking_token(self):
        self.assertFalse(self.prompt.lstrip().startswith("<|"))
        self.assertNotIn("<|think|>", self.prompt)

    def test_defines_every_llm_type(self):
        for type_ in LLM_TYPES:
            self.assertRegex(self.prompt, rf"(?m)^- {type_}: \S")
        self.assertNotRegex(self.prompt, r"(?m)^- (first_appearance|return): ")

    def test_states_the_rules(self):
        for rule in ("granularity", "first appearance", "cover", "unlisted_entities",
                     "evidence", "in_flashback", "JSON"):
            self.assertIn(rule.lower(), self.prompt.lower())

    def test_chapter_97_example(self):
        self.assertIn('CHAPTER 97 — "Sandai Kitetsu" — Arc: Loguetown Arc', self.prompt)
        self.assertIn("Smoker is introduced.", self.prompt)


class TestChapter97Example(PromptTestCase):
    """La sortie attendue du ch. 97 est valide contre le schéma final du ch. 97."""

    def setUp(self):
        super().setUp()
        self.write_silver(chapter(1, char("Monkey D. Luffy")))
        self.dry_run()
        prompt = self.system_prompt(self.version(1, "prompt_version"))
        example_input = prompt.split("EXAMPLE INPUT:\n", 1)[1].split("\nEXAMPLE OUTPUT:\n", 1)
        self.example_names = re.findall(
            r"(?m)^- ([^(\n]+?)(?: \(.*\))?$",
            example_input[0].split("Characters:\n", 1)[1].split("Devil Fruits", 1)[0])
        self.example_text = example_input[0]
        self.example_output = json.loads(example_input[1].split("\n\n", 1)[0])

    def schema_for_example(self):
        """Le ch. 97 de l'exemple, avec ses personnages, passé dans le pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            self.data_dir = Path(tmp)
            self.write_silver(chapter(97, *(char(name) for name in self.example_names)))
            self.dry_run()
            self.assertEqual(self.allowed_names(97), self.example_names)
            return self.chapter_schema(97)

    def test_expected_output_is_valid(self):
        jsonschema.validate(self.example_output, self.schema_for_example())
        self.assertEqual(self.example_output["chapter"], 97)

    def test_example_shows_granularity_and_the_smoker_trap(self):
        events = self.example_output["events"]
        keys = [(e["type"], frozenset(p["name"] for p in e["participants"])) for e in events]
        self.assertEqual(len(keys), len(set(keys)))
        # « Smoker is introduced. » est une première apparition, pas un événement.
        self.assertNotIn("Smoker is introduced.", [e["evidence"] for e in events])
        for e in events:
            self.assertIn(e["evidence"], self.example_text)
            self.assertLessEqual(len(e["evidence"].split()), 20)
            self.assertLessEqual(len(e["description"].split()), 25)

    def test_invalid_outputs_are_rejected(self):
        schema = self.schema_for_example()
        event = dict(self.example_output["events"][0])
        bad = [
            dict(event, participants=[{"name": "Kaido", "role": "agent"}]),
            dict(event, type="first_appearance"),
            dict(event, extra="field"),
            {k: v for k, v in event.items() if k != "evidence"},
            dict(event, in_flashback="no"),
        ]
        for wrong in bad:
            output = dict(self.example_output, events=[wrong])
            with self.assertRaises(jsonschema.ValidationError, msg=wrong):
                jsonschema.validate(output, schema)


if __name__ == "__main__":
    unittest.main()

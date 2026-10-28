"""Extraction d'origine `llm`, à travers le pipeline, contre un client factice.

Chapitres silver synthétiques écrits dans un dossier de données temporaire, un
client LLM factice qui renvoie des réponses écrites à l'avance, puis lecture de
ce que le pipeline écrit sous `data/event/` : `out/`, `raw/` et `run.jsonl`.
Sans réseau ni modèle.
"""
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from guess_arc import paths
from guess_arc.events.llm import Completion, FakeClient
from guess_arc.events.pipeline import run
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown


def char(name, *appearance):
    excluded = {"cover", "flashback", "mentioned", "dream"}
    return {"name": name, "faction": "Some Faction",
            "on_panel": not excluded & set(appearance), "appearance": list(appearance)}


def chapter(number, *characters, **kwargs):
    defaults = dict(
        title=f"Title {number}", arc="A Arc", revision_id=1000 + number,
        revised_at="2025-01-01T00:00:00Z", characters=list(characters),
        short_summary="Luffy fights Zoro.", long_summary="Luffy fights Zoro and wins.",
        notes=[], complete=True,
    )
    defaults.update(kwargs)
    return Chapter(number=number, **defaults)


def llm_event(type_="combat", names=("Luffy", "Zoro"), **fields):
    event = {
        "evidence": "Luffy fights Zoro and wins.",
        "source": "long_summary",
        "type": type_,
        "description": "Luffy fights Zoro.",
        "participants": [{"name": n, "role": "agent"} for n in names],
        "location": "",
        "status": "single",
        "in_flashback": False,
    }
    event.update(fields)
    return event


def response(number, *events, unlisted=()):
    return json.dumps({"chapter": number, "events": list(events),
                       "unlisted_entities": list(unlisted)})


class LlmTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_silver(self, *chapters):
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(self.data_dir))

    def extract(self, *responses, dry_run=False, max_attempts=3, pause_s=0):
        self.client = FakeClient(list(responses), model="fake-gemma")
        return run(data_dir=self.data_dir, dry_run=dry_run, client=self.client,
                   review_path=self.data_dir / "no_review.json", pause_s=pause_s,
                   max_attempts=max_attempts)

    def out_path(self, number):
        return paths.event_out_dir(self.data_dir) / f"events_{number:04d}.json"

    def output(self, number):
        return json.loads(self.out_path(number).read_text(encoding="utf-8"))

    def raw(self, number, attempt):
        path = paths.event_raw_dir(self.data_dir) / f"events_{number:04d}_attempt_{attempt}.json"
        return path.read_text(encoding="utf-8")

    def log(self):
        lines = paths.event_run_log_path(self.data_dir).read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]


class TestCalls(LlmTestCase):
    def test_one_call_per_chapter_in_order(self):
        self.write_silver(chapter(2, char("Luffy"), char("Zoro")),
                          chapter(1, char("Luffy"), char("Zoro")))
        self.extract(response(1), response(2))
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual([c.user.splitlines()[0][:10] for c in self.client.calls],
                         ["CHAPTER 1 ", "CHAPTER 2 "])

    def test_call_sends_the_exact_files_written(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))
        self.extract(response(1))
        [call] = self.client.calls
        event_dir = paths.event_dir(self.data_dir)
        in_text = (event_dir / "in" / "events_0001.md").read_text(encoding="utf-8")
        self.assertTrue(in_text.endswith(call.user))
        self.assertEqual(call.schema, json.loads(
            (event_dir / "schema" / "events_0001.json").read_text(encoding="utf-8")))
        [system] = (event_dir / "prompt").glob("system_v*.md")
        self.assertEqual(call.system, system.read_text(encoding="utf-8"))

    def test_pause_between_calls_and_between_attempts(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")),
                          chapter(2, char("Luffy"), char("Zoro")))
        started = time.monotonic()
        self.extract("not json", response(1), response(2), pause_s=0.2)
        # 3 appels : 2 pauses, l'une entre deux essais, l'autre entre deux chapitres.
        self.assertGreaterEqual(time.monotonic() - started, 0.4)

    def test_dry_run_never_calls_the_client(self):
        self.write_silver(chapter(1, char("Luffy")), chapter(2, char("Zoro")))
        self.extract(dry_run=True)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.output(1)["meta"]["origins"], ["wiki"])
        self.assertFalse(paths.event_raw_dir(self.data_dir).exists())
        self.assertFalse(paths.event_run_log_path(self.data_dir).exists())

    def test_dry_run_keeps_llm_events_already_extracted(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))
        self.extract(response(1, llm_event()))
        before = self.output(1)
        self.extract(dry_run=True)
        self.assertEqual(self.output(1), before)


class TestRetries(LlmTestCase):
    def setUp(self):
        super().setUp()
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))

    def test_invalid_then_valid_writes_the_chapter_with_two_attempts(self):
        self.extract("not json", response(1, llm_event()))
        self.assertEqual(len(self.client.calls), 2)
        output = self.output(1)
        self.assertEqual(output["meta"]["attempts"], 2)
        self.assertEqual([e["type"] for e in output["events"] if e["origin"] == "llm"],
                         ["combat"])

    def test_three_invalid_responses_abandon_the_chapter(self):
        bad_schema = response(1, llm_event(type_="first_appearance"))
        self.extract("not json", bad_schema, response(1, llm_event(names=("Kaido",))))
        self.assertEqual(len(self.client.calls), 3)
        self.assertFalse(self.out_path(1).exists())
        log = self.log()
        self.assertEqual([line["attempt"] for line in log], [1, 2, 3])
        self.assertTrue(all(line["error"] for line in log))
        self.assertEqual([line["outcome"] for line in log], ["retry", "retry", "abandoned"])

    def test_abandoned_chapter_does_not_stop_the_next_one(self):
        self.write_silver(chapter(2, char("Luffy"), char("Zoro")))
        self.extract("x", "x", "x", response(2))
        self.assertFalse(self.out_path(1).exists())
        self.assertEqual(self.output(2)["meta"]["attempts"], 1)

    def test_client_error_counts_as_an_attempt(self):
        self.extract(TimeoutError("server timed out"), response(1))
        self.assertEqual(self.output(1)["meta"]["attempts"], 2)
        self.assertIn("server timed out", self.log()[0]["error"])

    def test_wrong_chapter_number_is_invalid(self):
        self.extract(response(2), response(1))
        self.assertEqual(self.output(1)["meta"]["attempts"], 2)

    def test_empty_thinking_block_is_stripped(self):
        for block in ("<think>\n</think>\n", "<|channel>thought\n<channel|>",
                      "<thought> </thought>"):
            with self.subTest(block=block):
                self.extract(block + response(1, llm_event()))
                self.assertEqual(self.output(1)["meta"]["attempts"], 1)

    def test_non_empty_thinking_block_is_invalid(self):
        self.extract("<think>Luffy wins.</think>" + response(1), response(1))
        self.assertEqual(self.output(1)["meta"]["attempts"], 2)


class TestRawAndLog(LlmTestCase):
    def test_raw_responses_saved_per_attempt(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))
        thinking = "<think></think>" + response(1)
        self.extract("not json", thinking)
        self.assertEqual(self.raw(1, 1), "not json")
        self.assertEqual(self.raw(1, 2), thinking)

    def test_one_log_line_per_call(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")),
                          chapter(2, char("Luffy"), char("Zoro")))
        self.extract("not json", response(1), response(2))
        log = self.log()
        self.assertEqual([(line["chapter"], line["attempt"]) for line in log],
                         [(1, 1), (1, 2), (2, 1)])
        self.assertEqual([line["outcome"] for line in log], ["retry", "ok", "ok"])
        self.assertEqual([line["error"] for line in log][1:], [None, None])
        for line in log:
            self.assertGreaterEqual(line["duration_s"], 0)
            self.assertIn("prompt_tokens", line)
            self.assertIn("completion_tokens", line)

    def test_tokens_reported_by_the_client_are_logged(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))
        self.extract(Completion(response(1), prompt_tokens=5000, completion_tokens=300))
        [line] = self.log()
        self.assertEqual((line["prompt_tokens"], line["completion_tokens"]), (5000, 300))

    def test_log_appends_across_runs(self):
        self.write_silver(chapter(1, char("Luffy"), char("Zoro")))
        self.extract(response(1))
        self.extract(response(1))
        self.assertEqual(len(self.log()), 2)

    def test_raw_dir_is_ignored_by_git(self):
        repo = paths.REPO_ROOT
        raw = paths.event_raw_dir(repo / "data") / "events_0001_attempt_1.json"
        result = subprocess.run(["git", "check-ignore", "-q", str(raw)], cwd=repo)
        self.assertEqual(result.returncode, 0)


class TestMerge(LlmTestCase):
    def setUp(self):
        super().setUp()
        self.write_silver(chapter(1, char("Luffy"), char("Zoro", "ko"), revision_id=4242))
        self.extract(response(1, llm_event(), llm_event("defeat", ("Zoro",)),
                              unlisted=["Kaido"]))
        self.document = self.output(1)

    def test_both_origins_in_the_same_file(self):
        types = [(e["origin"], e["type"]) for e in self.document["events"]]
        self.assertEqual(types, [
            ("wiki", "first_appearance"), ("wiki", "first_appearance"), ("wiki", "defeat"),
            ("llm", "combat"), ("llm", "defeat"),
        ])

    def test_llm_event_fields(self):
        event = self.document["events"][3]
        self.assertEqual(list(event), [
            "id", "origin", "type", "description", "participants", "location",
            "status", "in_flashback", "evidence", "source", "checks",
        ])
        self.assertEqual(event["evidence"], "Luffy fights Zoro and wins.")
        self.assertEqual(event["source"], "long_summary")

    def test_unlisted_entities_kept(self):
        self.assertEqual(self.document["unlisted_entities"], ["Kaido"])

    def test_meta_is_complete(self):
        meta = self.document["meta"]
        self.assertEqual(meta["chapter"], 1)
        self.assertEqual(meta["revision_id"], 4242)
        self.assertEqual(meta["model"], "fake-gemma")
        for key in ("prompt_version", "schema_version", "taxonomy_version",
                    "entities_version", "checks_version"):
            self.assertRegex(meta[key], r"^v\d+$", key)
        self.assertEqual(meta["attempts"], 1)
        self.assertEqual(meta["origins"], ["wiki", "llm"])

    def test_ids_are_stable_and_unique(self):
        ids = [e["id"] for e in self.document["events"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.extract("not json", response(1, llm_event(), llm_event("defeat", ("Zoro",)),
                                          unlisted=["Kaido"]))
        self.assertEqual([e["id"] for e in self.output(1)["events"]], ids)

    def test_same_type_and_participants_twice_get_distinct_ids(self):
        # Les doublons sont l'affaire des contrôles : la fusion garde tout, sans collision.
        self.extract(response(1, llm_event(), llm_event(description="Again.")))
        ids = [e["id"] for e in self.output(1)["events"] if e["origin"] == "llm"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)


if __name__ == "__main__":
    unittest.main()

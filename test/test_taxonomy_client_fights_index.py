"""Integration-shaped sanity check that taxonomy_client.tag_chapter keeps
data/taxonomy/fights_index.json in sync (issue #11), with requests.post
mocked out so it runs with no network access — same spirit as
test_taxonomy_client_benchmark_log.py.
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "API"))
from providers import GEMINI  # noqa: E402
from taxonomy_client import tag_chapter  # noqa: E402

from test_taxonomy_client_fallback import envelope_response  # noqa: E402
from test_taxonomy_envelope import VALID_ENVELOPE  # noqa: E402


class TestTagChapterUpdatesFightsIndex(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict("os.environ", {"GEMINI_API_KEY": "valid-key"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.silver_dir = pathlib.Path(self.tmpdir.name) / "silver"
        self.taxonomy_dir = pathlib.Path(self.tmpdir.name) / "taxonomy"
        self.silver_dir.mkdir()
        self.fights_index_path = self.taxonomy_dir / "fights_index.json"

    def _tag(self, number: int, envelope: dict):
        (self.silver_dir / f"chapter_{number:04d}.md").write_text("chapter text", encoding="utf-8")

        def fake_post(url, headers=None, json=None, timeout=None):
            return envelope_response(envelope)

        with patch("taxonomy_client.SILVER_DIR", self.silver_dir), patch(
            "taxonomy_client.TAXONOMY_DIR", self.taxonomy_dir
        ), patch("taxonomy_client.requests.post", side_effect=fake_post):
            return tag_chapter(number, [GEMINI], "system prompt", {"type": "object"})

    def test_a_chapter_with_a_fight_creates_the_fights_index_file(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 82
        self._tag(82, envelope)

        self.assertTrue(self.fights_index_path.is_file())
        index = json.loads(self.fights_index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["fight-0034"]["chapters"], [82])

    def test_a_later_chapter_extends_the_same_fight_entry(self):
        first = copy.deepcopy(VALID_ENVELOPE)
        first["chapter"]["number"] = 82
        self._tag(82, first)

        second = copy.deepcopy(VALID_ENVELOPE)
        second["chapter"]["number"] = 83
        self._tag(83, second)

        index = json.loads(self.fights_index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["fight-0034"]["chapters"], [82, 83])

    def test_a_chapter_with_no_fight_interaction_does_not_create_the_file(self):
        envelope = copy.deepcopy(VALID_ENVELOPE)
        envelope["chapter"]["number"] = 5
        envelope["interactions"] = []
        self._tag(5, envelope)

        self.assertFalse(self.fights_index_path.exists())


if __name__ == "__main__":
    unittest.main()

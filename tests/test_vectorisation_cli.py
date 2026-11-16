"""Tests de la commande `python -m guess_arc.vectorisation` et de l'encodeur réel.

La CLI est testée via `main`, avec un encodeur factice injecté et un .env
temporaire. L'adaptateur sentence-transformers n'est testé que si l'extra
[vectorisation] est installé et le modèle déjà en cache ; le test sur les vraies
données, que si data/silver/ existe.
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

from guess_arc import paths
from guess_arc.ingestion.silver import write_markdown
from guess_arc.vectorisation import load_chapter_embeddings, run
from guess_arc.vectorisation.cli import MissingSettingError, embedding_model, main
from guess_arc.vectorisation.sentence_encoder import MissingExtraError, SentenceTransformerEncoder

from test_vectorisation import DIM, LONG_2, LONG_7, LONG_10, HashEncoder, chapter

PIP_COMMAND = "pip install -e .[vectorisation]"


class EmbeddingModelSettingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.env_file = pathlib.Path(tmp.name) / ".env"

    def test_read_from_env_file(self):
        self.env_file.write_text("# commentaire\nLLM_MODEL=x\nEMBEDDING_MODEL = org/model \n", encoding="utf-8")

        self.assertEqual(embedding_model({}, self.env_file), "org/model")

    def test_quoted_value_in_env_file(self):
        self.env_file.write_text('EMBEDDING_MODEL="org/model"\n', encoding="utf-8")

        self.assertEqual(embedding_model({}, self.env_file), "org/model")

    def test_process_environment_wins_over_env_file(self):
        self.env_file.write_text("EMBEDDING_MODEL=org/from-file\n", encoding="utf-8")

        self.assertEqual(embedding_model({"EMBEDDING_MODEL": "org/from-env"}, self.env_file), "org/from-env")

    def test_absent_everywhere_is_an_explicit_error(self):
        for content in (None, "LLM_MODEL=x\n", "EMBEDDING_MODEL=\n"):
            with self.subTest(content=content):
                if content is None:
                    self.env_file.unlink(missing_ok=True)
                else:
                    self.env_file.write_text(content, encoding="utf-8")
                with self.assertRaises(MissingSettingError) as ctx:
                    embedding_model({}, self.env_file)
                self.assertIn("EMBEDDING_MODEL", str(ctx.exception))
                self.assertIn(".env", str(ctx.exception))


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.env_file = self.root / ".env"
        self.env_file.write_text("EMBEDDING_MODEL=fake/hash-encoder\n", encoding="utf-8")
        self.data_dir = self.root / "data"
        for ch in (chapter(10, LONG_10), chapter(2, LONG_2), chapter(7, LONG_7, complete=False)):
            write_markdown(ch, paths.silver_dir(self.data_dir))
        self.built_with: list[str] = []

    def make_encoder(self, model_name: str) -> HashEncoder:
        self.built_with.append(model_name)
        return HashEncoder()

    def main(self, *argv: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(list(argv), environ={}, env_file=self.env_file, make_encoder=self.make_encoder)
        return out.getvalue()

    def test_data_dir_option_vectorises_that_directory(self):
        self.main("--data-dir", str(self.data_dir))

        self.assertEqual(self.built_with, ["fake/hash-encoder"])
        emb = load_chapter_embeddings(self.data_dir)
        self.assertEqual(sorted(emb), [2, 10])
        self.assertEqual(emb[2].shape, (DIM,))

    def test_prints_a_summary_of_vectorised_and_skipped_chapters(self):
        output = self.main("--data-dir", str(self.data_dir))

        self.assertIn("vectorisés : 2", output)
        self.assertIn("sautés : 1", output)
        self.assertIn("7 (complete: false)", output)
        self.assertIn("chapter_embeddings.npz", output)
        self.assertIn("embeddings_quality.json", output)

    def test_missing_embedding_model_exits_with_message_and_writes_nothing(self):
        self.env_file.write_text("LLM_MODEL=x\n", encoding="utf-8")

        with self.assertRaises(SystemExit) as ctx:
            self.main("--data-dir", str(self.data_dir))

        self.assertIn("EMBEDDING_MODEL", str(ctx.exception.code))
        self.assertEqual(self.built_with, [])
        self.assertFalse(paths.vector_dir(self.data_dir).exists())

    def test_missing_extra_exits_with_the_pip_command(self):
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with self.assertRaises(SystemExit) as ctx:
                main(["--data-dir", str(self.data_dir)], environ={}, env_file=self.env_file)

        self.assertIn(PIP_COMMAND, str(ctx.exception.code))
        self.assertFalse(paths.vector_dir(self.data_dir).exists())


class MissingExtraTest(unittest.TestCase):
    def test_adapter_without_the_extra_names_the_pip_command(self):
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with self.assertRaises(MissingExtraError) as ctx:
                SentenceTransformerEncoder("org/model")

        self.assertIn(PIP_COMMAND, str(ctx.exception))


def _cached_model() -> str | None:
    """Le modèle du .env s'il est utilisable hors ligne, sinon None."""
    if importlib.util.find_spec("sentence_transformers") is None:
        return None
    try:
        model = embedding_model(os.environ, paths.REPO_ROOT / ".env")
    except MissingSettingError:
        return None
    from huggingface_hub import try_to_load_from_cache

    return model if isinstance(try_to_load_from_cache(model, "config.json"), str) else None


@unittest.skipUnless(_cached_model(), "extra [vectorisation] non installé, EMBEDDING_MODEL absent ou modèle pas en cache")
class SentenceTransformerEncoderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoder = SentenceTransformerEncoder(_cached_model())

    def test_one_vector_per_text_of_the_model_dimension(self):
        vectors = self.encoder.encode(["Luffy fights Kaido.", "Nami draws a map."])

        self.assertEqual(vectors.shape[0], 2)
        self.assertGreater(vectors.shape[1], 0)
        self.assertTrue(np.isfinite(vectors).all())

    def test_chapter_embedding_has_model_dimension_and_unit_norm(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_dir = pathlib.Path(tmp.name)
        write_markdown(chapter(10, LONG_10), paths.silver_dir(data_dir))

        run(data_dir, self.encoder)

        emb = load_chapter_embeddings(data_dir)
        dimension = self.encoder.encode(["Luffy."]).shape[1]
        self.assertEqual(emb[10].shape, (dimension,))
        self.assertEqual(emb.metadata.dimension, dimension)
        self.assertAlmostEqual(float(np.linalg.norm(emb[10])), 1.0, places=5)
        self.assertEqual(emb.metadata.model, self.encoder.model_name)

    def test_tokens_are_counted_with_the_model_tokenizer(self):
        self.assertGreater(self.encoder.count_tokens("Gomu Gomu no Pistol"), len("Gomu Gomu no Pistol".split()))
        self.assertGreater(self.encoder.max_tokens, 0)

    def test_max_tokens_is_the_text_window_without_special_tokens(self):
        too_long = " ".join(["pirate"] * 2000)
        kept = self.encoder._model.tokenize([too_long])["input_ids"].shape[1]
        self.assertEqual(self.encoder.max_tokens, kept - 2)


@unittest.skipUnless(paths.silver_dir().is_dir(), "data/silver/ absent : lancer d'abord l'ingestion")
class RealSilverTest(unittest.TestCase):
    def complete_chapters(self) -> set[int]:
        from guess_arc.vectorisation.pipeline import read_silver_chapter, scenes

        chapters = (read_silver_chapter(p) for p in paths.silver_dir().glob("chapter_*.md"))
        return {c.number for c in chapters if c.complete and scenes(c.long_summary)}

    def test_one_finite_vector_per_complete_silver_chapter(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_dir = pathlib.Path(tmp.name)
        shutil.copytree(paths.silver_dir(), paths.silver_dir(data_dir))

        run(data_dir, HashEncoder())

        emb = load_chapter_embeddings(data_dir)
        self.assertEqual(set(emb), self.complete_chapters())
        matrix = np.stack(list(emb.values()))
        self.assertFalse(np.isnan(matrix).any())
        np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0, rtol=1e-5)

    def test_real_dataset_if_generated(self):
        if not (paths.vector_dir() / "chapter_embeddings.npz").exists():
            self.skipTest("data/gold/vector/ absent : lancer python -m guess_arc.vectorisation")
        emb = load_chapter_embeddings()

        self.assertEqual(set(emb), self.complete_chapters())
        matrix = np.stack(list(emb.values()))
        self.assertEqual(matrix.shape[1], emb.metadata.dimension)
        self.assertFalse(np.isnan(matrix).any())
        np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0, rtol=1e-5)


if __name__ == "__main__":
    unittest.main()

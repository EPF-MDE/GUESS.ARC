"""Tests de la vectorisation via `run`, `load_chapter_embeddings` et le rapport qualité uniquement.

Silver synthétique écrite par le vrai writer de l'ingestion, dans un dossier
temporaire. Encodeurs factices : ni réseau, ni sentence-transformers.
"""
import datetime
import hashlib
import json
import pathlib
import tempfile
import unittest

import numpy as np

from guess_arc import paths
from guess_arc.ingestion.parser import Chapter
from guess_arc.ingestion.silver import write_markdown
from guess_arc.vectorisation import load_chapter_embeddings, run

DIM = 8


class HashEncoder:
    """Vecteur pseudo-aléatoire mais déterministe, dérivé du texte. 1 token = 1 mot."""

    model_name = "fake/hash-encoder"
    max_tokens = 512

    def __init__(self):
        self.seen: list[str] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def encode(self, texts: list[str]) -> np.ndarray:
        self.seen.extend(texts)
        rows = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")
            rows.append(np.random.default_rng(seed).normal(size=DIM))
        return np.array(rows, dtype=np.float32)


class KeywordEncoder:
    """Axe 0 si le texte parle d'alpha, axe 1 sinon : sorties prévisibles."""

    model_name = "fake/keyword-encoder"
    max_tokens = 512

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), 2), dtype=np.float32)
        for i, text in enumerate(texts):
            out[i, 0 if "alpha" in text else 1] = 1.0
        return out


class FailingEncoder(HashEncoder):
    def encode(self, texts):
        raise RuntimeError("encodeur en panne")


class SmallWindowEncoder(HashEncoder):
    """Petite fenêtre, et, comme le vrai modèle, ne voit que ses `max_tokens`
    premiers tokens : un texte trop long serait tronqué en silence."""

    model_name = "fake/small-window-encoder"
    max_tokens = 8

    def _truncated(self, texts: list[str]) -> list[str]:
        return [" ".join(t.split()[: self.max_tokens]) for t in texts]

    def encode(self, texts: list[str]) -> np.ndarray:
        return super().encode(self._truncated(texts))

    def encode_seen(self) -> np.ndarray:
        """Les vecteurs des Chunks reçus, recalculés sans les enregistrer."""
        return HashEncoder().encode(self._truncated(self.seen))


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def chapter(number: int, long_summary: str, **overrides) -> Chapter:
    values = dict(
        number=number,
        title=f"Title {number}",
        jname="",
        arc="Romance Dawn Arc",
        revision_id=1000 + number,
        revised_at="2026-11-01T00:00:00Z",
        characters=[{"name": "Monkey D. Luffy", "faction": "Straw Hat Pirates", "on_panel": True}],
        notes=["First appearance of something."],
        short_summary=f"Short summary of chapter {number}.",
        long_summary=long_summary,
        complete=True,
    )
    values.update(overrides)
    return Chapter(**values)


LONG_10 = "Luffy sets sail from his village.\n\nHe meets a huge sea monster.\n\nShanks loses his arm."
LONG_2 = "Zoro is tied to a post at the Marine base."
LONG_7 = "Nami steals a map.\n\nBuggy fires the Buggy Ball at the town."


class SilverTestCase(unittest.TestCase):
    """Une silver synthétique par test, dans un dossier temporaire."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)

    def data_dir(self, name: str, chapters: list[Chapter]) -> pathlib.Path:
        data_dir = self.root / name
        for ch in chapters:
            write_markdown(ch, paths.silver_dir(data_dir))
        return data_dir


class VectorisationTest(SilverTestCase):
    def embeddings(self, chapters, encoder=None, name="data"):
        data_dir = self.data_dir(name, chapters)
        run(data_dir, encoder or HashEncoder())
        return load_chapter_embeddings(data_dir)

    def test_one_unit_vector_of_dimension_d_per_complete_chapter(self):
        emb = self.embeddings([chapter(10, LONG_10), chapter(2, LONG_2), chapter(7, LONG_7)])

        self.assertEqual(sorted(emb), [2, 7, 10])
        for vector in emb.values():
            self.assertEqual(vector.shape, (DIM,))
            self.assertEqual(vector.dtype, np.float32)
            self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=5)

    def test_dataset_is_a_single_npz_under_gold_vector_next_to_its_quality_report(self):
        data_dir = self.data_dir("data", [chapter(1, LONG_2)])
        run(data_dir, HashEncoder())

        files = sorted(p.name for p in paths.vector_dir(data_dir).iterdir())
        self.assertEqual(files, ["chapter_embeddings.npz", "embeddings_quality.json"])

    def test_each_vector_is_found_by_its_chapter_number(self):
        corpus = self.embeddings([chapter(10, LONG_10), chapter(2, LONG_2), chapter(7, LONG_7)])

        for number, long_summary in ((10, LONG_10), (2, LONG_2), (7, LONG_7)):
            alone = self.embeddings([chapter(number, long_summary)], name=f"alone_{number}")
            np.testing.assert_allclose(corpus[number], alone[number], rtol=1e-6)

    def test_only_the_long_summary_is_encoded(self):
        encoder = HashEncoder()
        self.embeddings([chapter(10, LONG_10)], encoder=encoder)

        self.assertEqual(encoder.seen, LONG_10.split("\n\n"))

    def test_other_sections_and_front_matter_do_not_change_the_vector(self):
        reference = self.embeddings([chapter(10, LONG_10)], name="reference")[10]
        variants = {
            "short_summary": dict(short_summary="A completely different short summary."),
            "notes": dict(notes=["Another note.", "Chapter 1000 is referenced here."]),
            "front_matter": dict(
                title="Other title",
                jname="Betsu",
                arc="Wano Country Arc",
                revision_id=99999,
                revised_at="2030-01-01T00:00:00Z",
                characters=[{"name": "Roronoa Zoro", "faction": "", "on_panel": False}],
            ),
        }
        for name, overrides in variants.items():
            with self.subTest(name):
                vector = self.embeddings([chapter(10, LONG_10, **overrides)], name=name)[10]
                np.testing.assert_array_equal(vector, reference)

    def test_chapter_embedding_is_the_length_weighted_mean_of_scenes_then_l2(self):
        # Scene 1 : 3 tokens sur l'axe 0 ; Scene 2 : 1 token sur l'axe 1.
        long_summary = "alpha alpha alpha\n\nbeta"
        emb = self.embeddings([chapter(1, long_summary)], encoder=KeywordEncoder())

        expected = np.array([3.0, 1.0]) / np.sqrt(10.0)
        np.testing.assert_allclose(emb[1], expected, rtol=1e-6)

    def test_blank_lines_and_whitespace_paragraphs_are_not_scenes(self):
        long_summary = "alpha alpha alpha\n\n   \n\n\n\nbeta\n"
        emb = self.embeddings([chapter(1, long_summary)], encoder=KeywordEncoder())

        expected = np.array([3.0, 1.0]) / np.sqrt(10.0)
        np.testing.assert_allclose(emb[1], expected, rtol=1e-6)

    def test_incomplete_chapter_has_no_entry(self):
        emb = self.embeddings([chapter(1, LONG_2), chapter(2, LONG_7, complete=False), chapter(3, LONG_10)])

        self.assertEqual(sorted(emb), [1, 3])

    def test_complete_chapter_without_scene_has_no_entry(self):
        # Le writer silver écrit "_(absent)_" à la place d'un Long Summary vide.
        emb = self.embeddings([chapter(1, LONG_2), chapter(2, "")])

        self.assertEqual(sorted(emb), [1])

    def test_revision_ids_and_metadata_are_stored_and_read_back(self):
        before = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        emb = self.embeddings([chapter(10, LONG_10), chapter(2, LONG_2, revision_id=42)])

        self.assertEqual(emb.revision_ids, {2: 42, 10: 1010})
        self.assertEqual(emb.metadata.model, "fake/hash-encoder")
        self.assertEqual(emb.metadata.dimension, DIM)
        self.assertEqual(emb.metadata.pooling, "chunk-mean-token-weighted-l2")
        created = datetime.datetime.fromisoformat(emb.metadata.created_at)
        self.assertIsNotNone(created.tzinfo)
        self.assertGreaterEqual(created, before)

    def test_failed_run_leaves_no_partial_file_and_keeps_previous_dataset(self):
        data_dir = self.data_dir("data", [chapter(10, LONG_10), chapter(2, LONG_2)])
        run(data_dir, HashEncoder())
        vector_dir = paths.vector_dir(data_dir)
        previous = {p.name: p.read_bytes() for p in vector_dir.iterdir()}

        write_markdown(chapter(2, "Zoro is freed by Luffy.", revision_id=5000), paths.silver_dir(data_dir))
        with self.assertRaises(RuntimeError):
            run(data_dir, FailingEncoder())

        self.assertEqual({p.name: p.read_bytes() for p in vector_dir.iterdir()}, previous)

    def test_scene_longer_than_the_window_is_split_into_overlapping_chunks(self):
        encoder = SmallWindowEncoder()
        scene = words(30)
        self.embeddings([chapter(1, scene)], encoder=encoder)

        chunks = [c.split() for c in encoder.seen]
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(encoder.count_tokens(" ".join(chunk)), encoder.max_tokens)
        for previous, following in zip(chunks, chunks[1:]):
            self.assertTrue(set(previous) & set(following), f"{previous} / {following}")
        # Les Chunks, dans l'ordre, couvrent toute la Scene, jusqu'au dernier mot.
        covered = []
        for chunk in chunks:
            covered.extend(w for w in chunk if w not in covered)
        self.assertEqual(covered, scene.split())
        self.assertEqual(chunks[-1][-1], "w29")

    def test_changing_the_last_words_of_a_long_scene_changes_the_vector(self):
        long_scene = words(30)
        cliffhanger = words(27) + " Luffy is defeated"
        reference = self.embeddings([chapter(1, long_scene)], encoder=SmallWindowEncoder(), name="a")[1]
        changed = self.embeddings([chapter(1, cliffhanger)], encoder=SmallWindowEncoder(), name="b")[1]

        self.assertFalse(np.allclose(reference, changed))

    def test_chunks_are_weighted_by_their_token_count(self):
        encoder = SmallWindowEncoder()
        emb = self.embeddings([chapter(1, words(3, "short") + "\n\n" + words(19))], encoder=encoder)

        weights = np.array([encoder.count_tokens(c) for c in encoder.seen], dtype=np.float64)
        self.assertGreater(len(set(weights)), 1, "le test doit mêler des Chunks de tailles différentes")
        pooled = weights @ encoder.encode_seen().astype(np.float64)
        np.testing.assert_allclose(emb[1], pooled / np.linalg.norm(pooled), rtol=1e-5)

    def test_scene_that_fits_the_window_is_a_single_chunk(self):
        encoder = SmallWindowEncoder()
        fits = words(8)
        self.embeddings([chapter(1, fits + "\n\n" + "a short scene")], encoder=encoder)

        self.assertEqual(encoder.seen, [fits, "a short scene"])

    def test_failed_first_run_leaves_no_file(self):
        data_dir = self.data_dir("data", [chapter(1, LONG_2)])
        with self.assertRaises(RuntimeError):
            run(data_dir, FailingEncoder())

        vector_dir = paths.vector_dir(data_dir)
        self.assertEqual(list(vector_dir.iterdir()) if vector_dir.exists() else [], [])


class CountingEncoder(HashEncoder):
    """Compte les appels à `encode` et les textes reçus, appel par appel."""

    def __init__(self, model_name: str = HashEncoder.model_name):
        super().__init__()
        self.model_name = model_name
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return super().encode(texts)


class IncrementalUpdateTest(SilverTestCase):
    """Un `run` part du dataset existant : seuls les chapitres nouveaux ou
    modifiés passent par l'encodeur (docs/vectorisation.md, section 7)."""

    def setUp(self):
        super().setUp()
        self.data_dir = self.data_dir("data", [chapter(10, LONG_10), chapter(2, LONG_2), chapter(7, LONG_7)])
        run(self.data_dir, HashEncoder())
        self.first = load_chapter_embeddings(self.data_dir)

    def write(self, ch: Chapter) -> None:
        write_markdown(ch, paths.silver_dir(self.data_dir))

    def rerun(self, encoder=None, **options):
        encoder = encoder or CountingEncoder()
        result = run(self.data_dir, encoder, **options)
        return encoder, result, load_chapter_embeddings(self.data_dir)

    def assertKept(self, emb, chapters):
        for c in chapters:
            np.testing.assert_array_equal(emb[c], self.first[c])
            self.assertEqual(emb.revision_ids[c], self.first.revision_ids[c])

    def test_second_run_without_change_does_not_call_the_encoder(self):
        encoder, result, emb = self.rerun()

        self.assertEqual(encoder.calls, [])
        self.assertEqual(sorted(emb), [2, 7, 10])
        self.assertKept(emb, [2, 7, 10])
        self.assertEqual(result.vectorised, [])
        self.assertEqual(result.kept, [2, 7, 10])

    def test_new_chapter_is_vectorised_and_the_others_kept(self):
        self.write(chapter(11, "Luffy meets Koby."))

        encoder, result, emb = self.rerun()

        self.assertEqual(encoder.seen, ["Luffy meets Koby."])
        self.assertEqual(sorted(emb), [2, 7, 10, 11])
        self.assertKept(emb, [2, 7, 10])
        self.assertEqual(emb.revision_ids[11], 1011)
        self.assertEqual((result.vectorised, result.kept), ([11], [2, 7, 10]))

    def test_chapter_with_a_new_revision_id_is_revectorised_and_only_it(self):
        self.write(chapter(2, "Zoro is freed by Luffy.", revision_id=5000))

        encoder, result, emb = self.rerun()

        self.assertEqual(encoder.seen, ["Zoro is freed by Luffy."])
        self.assertEqual(emb.revision_ids[2], 5000)
        self.assertFalse(np.allclose(emb[2], self.first[2]))
        self.assertKept(emb, [7, 10])
        self.assertEqual((result.vectorised, result.kept), ([2], [7, 10]))

    def test_chapter_turned_incomplete_leaves_the_dataset(self):
        self.write(chapter(7, LONG_7, complete=False))

        encoder, result, emb = self.rerun()

        self.assertEqual(encoder.calls, [])
        self.assertEqual(sorted(emb), [2, 10])
        self.assertEqual(result.skipped, {7: "complete: false"})

    def test_chapter_removed_from_the_silver_leaves_the_dataset(self):
        (paths.silver_dir(self.data_dir) / "chapter_0007.md").unlink()

        encoder, _, emb = self.rerun()

        self.assertEqual(encoder.calls, [])
        self.assertEqual(sorted(emb), [2, 10])
        self.assertNotIn(7, emb.revision_ids)

    def test_model_change_revectorises_every_chapter(self):
        encoder, result, emb = self.rerun(CountingEncoder("fake/another-model"))

        self.assertEqual(sorted(encoder.seen), sorted(LONG_10.split("\n\n") + LONG_7.split("\n\n") + [LONG_2]))
        self.assertEqual(emb.metadata.model, "fake/another-model")
        self.assertEqual((result.vectorised, result.kept), ([2, 7, 10], []))

    def test_rebuild_revectorises_every_chapter(self):
        encoder, result, emb = self.rerun(rebuild=True)

        self.assertEqual(len(encoder.seen), 6)  # 3 + 1 + 2 Scenes
        self.assertEqual((result.vectorised, result.kept), ([2, 7, 10], []))
        for c in (2, 7, 10):
            np.testing.assert_allclose(emb[c], self.first[c], rtol=1e-6)

    def test_quality_report_separates_vectorised_from_kept_chapters(self):
        self.write(chapter(11, "Luffy meets Koby."))
        self.write(chapter(7, LONG_7, complete=False))

        self.rerun()

        chapters = report(self.data_dir)["chapters"]
        self.assertEqual(chapters["vectorised"], [11])
        self.assertEqual(chapters["kept"], [2, 10])
        self.assertEqual(chapters["skipped"], {"7": "complete: false"})
        self.assertEqual(chapters["total"], 3)



def report(data_dir: pathlib.Path) -> dict:
    return json.loads((paths.vector_dir(data_dir) / "embeddings_quality.json").read_text(encoding="utf-8"))


# KeywordEncoder : "alpha" sur l'axe 0, tout le reste sur l'axe 1. Les chapitres
# d'East Blue penchent vers l'axe 0, ceux d'Arlong Park vers l'axe 1.
EAST_BLUE = "East Blue Arc"
ARLONG = "Arlong Park Arc"
ARC_CHAPTERS = [
    (1, "alpha alpha alpha\n\nbeta", EAST_BLUE),
    (2, "alpha alpha alpha alpha\n\nbeta", EAST_BLUE),
    (3, "alpha alpha\n\nbeta", EAST_BLUE),
    (4, "gamma gamma gamma\n\nalpha", ARLONG),
    (5, "gamma gamma gamma gamma\n\nalpha", ARLONG),
]


def cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


class QualityReportTest(SilverTestCase):
    def run_and_report(self, chapters, encoder=None, name="data") -> dict:
        data_dir = self.data_dir(name, chapters)
        run(data_dir, encoder or HashEncoder())
        return report(data_dir)

    def test_lists_vectorised_and_skipped_chapters_with_their_reason(self):
        quality = self.run_and_report([
            chapter(1, LONG_2),
            chapter(2, LONG_7, complete=False),
            chapter(3, LONG_10),
            chapter(4, ""),
        ])

        self.assertEqual(quality["chapters"]["vectorised"], [1, 3])
        self.assertEqual(quality["chapters"]["kept"], [])
        self.assertEqual(quality["chapters"]["skipped"], {"2": "complete: false", "4": "Long Summary vide"})

    def test_gives_dimension_nan_count_and_norm_range(self):
        quality = self.run_and_report([chapter(10, LONG_10), chapter(2, LONG_2), chapter(7, LONG_7)])

        self.assertEqual(quality["model"], "fake/hash-encoder")
        self.assertEqual(quality["dimension"], DIM)
        self.assertEqual(quality["nan_count"], 0)
        self.assertAlmostEqual(quality["norm_min"], 1.0, places=5)
        self.assertAlmostEqual(quality["norm_max"], 1.0, places=5)

    def test_intra_arc_similarity_beats_inter_arc_similarity_on_separable_arcs(self):
        chapters = [chapter(n, text, arc=arc) for n, text, arc in ARC_CHAPTERS]
        data_dir = self.data_dir("data", chapters)
        run(data_dir, KeywordEncoder())
        coherence = report(data_dir)["semantic_coherence"]

        self.assertGreater(coherence["intra_arc_mean"], coherence["inter_arc_mean"])
        self.assertAlmostEqual(coherence["gap"], coherence["intra_arc_mean"] - coherence["inter_arc_mean"], places=6)

    def test_each_arc_weighs_the_same_whatever_its_number_of_chapters(self):
        # East Blue : 3 chapitres (3 paires), Arlong Park : 2 (1 paire), Loguetown : 1.
        loguetown = chapter(6, "delta\n\nalpha alpha alpha alpha alpha", arc="Loguetown Arc")
        chapters = [chapter(n, text, arc=arc) for n, text, arc in ARC_CHAPTERS] + [loguetown]
        data_dir = self.data_dir("data", chapters)
        run(data_dir, KeywordEncoder())
        coherence = report(data_dir)["semantic_coherence"]
        emb = load_chapter_embeddings(data_dir)

        def mean_cosine(pairs):
            return np.mean([cosine(emb[a], emb[b]) for a, b in pairs])

        east_blue, arlong, loguetown = (1, 2, 3), (4, 5), (6,)
        intra = np.mean([mean_cosine([(1, 2), (1, 3), (2, 3)]), mean_cosine([(4, 5)])])
        inter = np.mean([
            mean_cosine([(a, b) for a in east_blue for b in arlong]),
            mean_cosine([(a, b) for a in east_blue for b in loguetown]),
            mean_cosine([(a, b) for a in arlong for b in loguetown]),
        ])
        self.assertAlmostEqual(coherence["intra_arc_mean"], intra, places=5)
        self.assertAlmostEqual(coherence["inter_arc_mean"], inter, places=5)
        self.assertEqual(coherence["arcs"], 3)
        self.assertEqual(coherence["intra_arcs"], 2)
        self.assertEqual(coherence["arc_pairs"], 3)

    def test_arc_with_a_single_chapter_does_not_break_the_intra_arc_mean(self):
        chapters = [chapter(n, text, arc=arc) for n, text, arc in ARC_CHAPTERS[:4]]
        data_dir = self.data_dir("data", chapters)
        run(data_dir, KeywordEncoder())
        coherence = report(data_dir)["semantic_coherence"]
        emb = load_chapter_embeddings(data_dir)

        intra = [cosine(emb[a], emb[b]) for a, b in ((1, 2), (1, 3), (2, 3))]
        self.assertAlmostEqual(coherence["intra_arc_mean"], np.mean(intra), places=5)
        self.assertEqual(coherence["intra_arcs"], 1)

    def test_without_any_pair_the_means_are_null(self):
        quality = self.run_and_report([chapter(1, LONG_2, arc=EAST_BLUE), chapter(2, LONG_7, arc=ARLONG)])

        coherence = quality["semantic_coherence"]
        self.assertIsNone(coherence["intra_arc_mean"])
        self.assertIsNone(coherence["gap"])
        self.assertEqual(coherence["intra_arcs"], 0)
        self.assertEqual(coherence["arc_pairs"], 1)

    def test_empty_dataset_still_gets_a_report(self):
        quality = self.run_and_report([chapter(1, LONG_2, complete=False)])

        self.assertEqual(quality["chapters"]["vectorised"], [])
        self.assertIsNone(quality["norm_min"])
        self.assertIsNone(quality["semantic_coherence"]["inter_arc_mean"])


if __name__ == "__main__":
    unittest.main()

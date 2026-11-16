"""Vectorisation : de la silver au dataset des Chapter embeddings.

Pour chaque chapitre complet de la silver, le Long Summary est découpé en
Scenes, une Scene plus longue que la fenêtre de l'encodeur est découpée en
fenêtres qui se chevauchent, chaque Chunk est encodé, et le Chapter embedding
est la moyenne des vecteurs de Chunks pondérée par leur nombre de tokens,
normalisée L2.
Voir docs/vectorisation.md et l'ADR 0003.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from guess_arc import paths

from .dataset import ChapterEmbeddings, Metadata, dataset_path, write_dataset
from .encoder import Encoder
from .quality import quality_report, report_path, write_report

POOLING = "chunk-mean-token-weighted-l2"
# Les fenêtres d'une Scene trop longue se chevauchent d'environ 1/4 de fenêtre.
OVERLAP_DIVISOR = 4

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LONG_SUMMARY_RE = re.compile(r"^## Long Summary[ \t]*\n(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n")
# Ce que le writer silver met à la place d'un Long Summary vide.
ABSENT = "_(absent)_"


@dataclass(frozen=True)
class SilverChapter:
    number: int
    arc: str
    revision_id: int
    complete: bool
    long_summary: str


def _field(front_matter: str, name: str, path: Path) -> str:
    match = re.search(rf"^{name}:[ \t]*(.*?)[ \t]*$", front_matter, re.MULTILINE)
    if match is None:
        raise ValueError(f"{path.name} : champ '{name}' absent du front-matter")
    value = match.group(1)
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def read_silver_chapter(path: Path) -> SilverChapter:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    front = FRONT_MATTER_RE.match(text)
    if front is None:
        raise ValueError(f"{path.name} : front-matter absent")
    body = text[front.end():]
    section = LONG_SUMMARY_RE.search(body)
    long_summary = section.group(1).strip() if section else ""
    return SilverChapter(
        number=int(_field(front.group(1), "chapter", path)),
        arc=_field(front.group(1), "arc", path),
        revision_id=int(_field(front.group(1), "revision_id", path)),
        complete=_field(front.group(1), "complete", path) == "true",
        long_summary="" if long_summary == ABSENT else long_summary,
    )


def scenes(long_summary: str) -> list[str]:
    """Les Scenes d'un Long Summary : une par paragraphe non vide (CONTEXT.md)."""
    return [p.strip() for p in PARAGRAPH_BREAK_RE.split(long_summary) if p.strip()]


def _longest_fit(words: list[str], start: int, stop: int, budget: int, encoder: Encoder, *, from_end: bool) -> int:
    """Le plus grand k de [0, stop - start] tel que k mots, pris au début de
    words[start:stop] (ou à la fin si `from_end`), tiennent en `budget` tokens."""
    def fits(k: int) -> bool:
        piece = words[stop - k:stop] if from_end else words[start:start + k]
        return encoder.count_tokens(" ".join(piece)) <= budget

    low, high = 0, stop - start
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    return low


def chunks(scene: str, encoder: Encoder) -> list[str]:
    """Les Chunks d'une Scene : la Scene elle-même si elle tient dans la fenêtre
    de l'encodeur, sinon des fenêtres de mots qui se chevauchent (d'au moins un
    mot, d'environ 1/OVERLAP_DIVISOR de fenêtre), chacune d'au plus `max_tokens`
    tokens comptés par l'encodeur. La dernière fenêtre finit au dernier mot de la
    Scene. Seul un mot à lui seul plus long que la fenêtre la dépasse."""
    if encoder.count_tokens(scene) <= encoder.max_tokens:
        return [scene]
    words = scene.split()
    overlap = encoder.max_tokens // OVERLAP_DIVISOR
    chunks: list[str] = []
    start = 0
    while True:
        # Au moins un mot par fenêtre, même un mot seul plus long que la fenêtre.
        end = start + max(1, _longest_fit(words, start, len(words), encoder.max_tokens, encoder, from_end=False))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            return chunks
        shared = max(1, _longest_fit(words, start, end, overlap, encoder, from_end=True))
        start = max(start + 1, end - shared)


def chapter_embedding(scene_texts: list[str], encoder: Encoder) -> np.ndarray:
    """Moyenne des vecteurs de Chunks pondérée par leur nombre de tokens, puis L2."""
    texts = [chunk for scene in scene_texts for chunk in chunks(scene, encoder)]
    vectors = np.asarray(encoder.encode(texts), dtype=np.float64)
    if vectors.ndim != 2 or vectors.shape[0] != len(texts):
        raise ValueError(f"l'encodeur a renvoyé {vectors.shape} pour {len(texts)} textes")
    weights = np.array([encoder.count_tokens(c) for c in texts], dtype=np.float64)
    pooled = weights @ vectors / weights.sum()
    norm = np.linalg.norm(pooled)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError(f"Chapter embedding de norme {norm}, impossible à normaliser")
    return (pooled / norm).astype(np.float32)


@dataclass(frozen=True)
class RunResult:
    path: Path  # le dataset écrit
    quality_path: Path  # le rapport qualité écrit à côté
    vectorised: list[int]
    skipped: dict[int, str]  # chapitre -> raison


def run(data_dir: Path, encoder: Encoder) -> RunResult:
    """Vectorise tous les chapitres complets de la silver, écrit le dataset et
    son rapport qualité.

    Un chapitre `complete: false`, ou sans Scene, n'a aucune entrée dans le dataset.
    """
    embeddings: dict[int, np.ndarray] = {}
    revision_ids: dict[int, int] = {}
    skipped: dict[int, str] = {}
    arcs: dict[int, str] = {}
    for path in sorted(paths.silver_dir(data_dir).glob("chapter_*.md")):
        chapter = read_silver_chapter(path)
        arcs[chapter.number] = chapter.arc
        scene_texts = scenes(chapter.long_summary)
        if not chapter.complete:
            skipped[chapter.number] = "complete: false"
            continue
        if not scene_texts:
            skipped[chapter.number] = "Long Summary vide"
            continue
        embeddings[chapter.number] = chapter_embedding(scene_texts, encoder)
        revision_ids[chapter.number] = chapter.revision_id

    dimensions = {v.shape[0] for v in embeddings.values()}
    if len(dimensions) > 1:
        raise ValueError(f"dimensions incohérentes entre chapitres : {sorted(dimensions)}")
    metadata = Metadata(
        model=encoder.model_name,
        dimension=dimensions.pop() if dimensions else 0,
        pooling=POOLING,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    dataset = ChapterEmbeddings(embeddings, revision_ids, metadata)
    report = quality_report(dataset, arcs, kept=[], skipped=skipped)
    target, quality_target = dataset_path(data_dir), report_path(data_dir)
    write_dataset(target, dataset)
    write_report(quality_target, report)
    return RunResult(path=target, quality_path=quality_target, vectorised=sorted(embeddings), skipped=skipped)

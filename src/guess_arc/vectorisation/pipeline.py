"""Vectorisation : de la silver au dataset des Chapter embeddings.

Pour chaque chapitre complet de la silver, le Long Summary est découpé en
Scenes, chaque Scene est encodée, et le Chapter embedding est la moyenne des
vecteurs de Scenes pondérée par leur nombre de tokens, normalisée L2.
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

POOLING = "scene-mean-token-weighted-l2"

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


def chapter_embedding(scene_texts: list[str], encoder: Encoder) -> np.ndarray:
    """Moyenne des vecteurs de Scenes pondérée par leur nombre de tokens, puis L2."""
    vectors = np.asarray(encoder.encode(scene_texts), dtype=np.float64)
    if vectors.ndim != 2 or vectors.shape[0] != len(scene_texts):
        raise ValueError(f"l'encodeur a renvoyé {vectors.shape} pour {len(scene_texts)} textes")
    weights = np.array([encoder.count_tokens(s) for s in scene_texts], dtype=np.float64)
    pooled = weights @ vectors / weights.sum()
    norm = np.linalg.norm(pooled)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError(f"Chapter embedding de norme {norm}, impossible à normaliser")
    return (pooled / norm).astype(np.float32)


@dataclass(frozen=True)
class RunResult:
    path: Path  # le dataset écrit
    vectorised: list[int]
    skipped: dict[int, str]  # chapitre -> raison


def run(data_dir: Path, encoder: Encoder) -> RunResult:
    """Vectorise tous les chapitres complets de la silver et écrit le dataset.

    Un chapitre `complete: false`, ou sans Scene, n'a aucune entrée dans le dataset.
    """
    embeddings: dict[int, np.ndarray] = {}
    revision_ids: dict[int, int] = {}
    skipped: dict[int, str] = {}
    for path in sorted(paths.silver_dir(data_dir).glob("chapter_*.md")):
        chapter = read_silver_chapter(path)
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
    target = dataset_path(data_dir)
    write_dataset(target, ChapterEmbeddings(embeddings, revision_ids, metadata))
    return RunResult(path=target, vectorised=sorted(embeddings), skipped=skipped)

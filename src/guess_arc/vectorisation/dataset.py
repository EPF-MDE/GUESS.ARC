"""Le dataset des Chapter embeddings : un .npz unique sous data/gold/vector/.

La ligne i de `embeddings` est le Chapter embedding du chapitre `chapters[i]`.
Le chargeur rend un dict chapitre -> Chapter embedding, pour que personne ne lise un
Chapter embedding par sa position.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np

from guess_arc import paths

FILENAME = "chapter_embeddings.npz"


def dataset_path(data_dir: Path = paths.DATA_DIR) -> Path:
    return paths.vector_dir(data_dir) / FILENAME


@dataclass(frozen=True)
class Metadata:
    model: str
    dimension: int
    pooling: str
    created_at: str  # ISO 8601, UTC


class ChapterEmbeddings(dict[int, np.ndarray]):
    """{chapitre: Chapter embedding}, avec le revision_id silver de chaque
    chapitre et les métadonnées du dataset."""

    def __init__(self, embeddings: dict[int, np.ndarray], revision_ids: dict[int, int], metadata: Metadata):
        super().__init__(embeddings)
        self.revision_ids = revision_ids
        self.metadata = metadata


def atomic_write(path: Path, write: Callable[[BinaryIO], None]) -> None:
    """Écriture atomique : un fichier temporaire du même dossier, renommé à la
    fin. En cas d'erreur, l'ancien fichier reste intact et rien d'autre ne reste."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            write(fh)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_dataset(path: Path, embeddings: ChapterEmbeddings) -> None:
    chapters = sorted(embeddings)
    dimension = embeddings.metadata.dimension
    matrix = np.array([embeddings[c] for c in chapters], dtype=np.float32).reshape(len(chapters), dimension)
    atomic_write(path, lambda fh: np.savez(
        fh,
        chapters=np.array(chapters, dtype=np.int64),
        revision_ids=np.array([embeddings.revision_ids[c] for c in chapters], dtype=np.int64),
        embeddings=matrix,
        model=np.array(embeddings.metadata.model),
        dimension=np.array(dimension, dtype=np.int64),
        pooling=np.array(embeddings.metadata.pooling),
        created_at=np.array(embeddings.metadata.created_at),
    ))


def load_chapter_embeddings(data_dir: Path = paths.DATA_DIR) -> ChapterEmbeddings:
    """{chapitre: Chapter embedding float32 de dimension d}, avec `.revision_ids` et `.metadata`."""
    with np.load(dataset_path(data_dir), allow_pickle=False) as npz:
        chapters = [int(c) for c in npz["chapters"]]
        matrix = npz["embeddings"]
        revision_ids = [int(r) for r in npz["revision_ids"]]
        metadata = Metadata(
            model=str(npz["model"]),
            dimension=int(npz["dimension"]),
            pooling=str(npz["pooling"]),
            created_at=str(npz["created_at"]),
        )
    return ChapterEmbeddings(
        embeddings={c: matrix[i] for i, c in enumerate(chapters)},
        revision_ids=dict(zip(chapters, revision_ids)),
        metadata=metadata,
    )

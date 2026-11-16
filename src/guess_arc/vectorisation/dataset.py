"""Le dataset des Chapter embeddings : un .npz unique sous data/gold/vector/.

La ligne i de `embeddings` est le Chapter embedding du chapitre `chapters[i]`.
Le chargeur rend un dict chapitre -> Chapter embedding, pour que personne ne lise un
Chapter embedding par sa position. Il refuse un dataset corrompu
(`corrupt_verification`) au lieu de rendre des vecteurs faux.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Callable, Mapping
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


class CorruptDatasetError(ValueError):
    """Le dataset existe mais est illisible ou incohérent."""


REQUIRED = ("chapters", "revision_ids", "embeddings", "model", "dimension", "pooling", "created_at")
# Tolérance sur la norme L2 : les vecteurs sont stockés en float32.
NORM_TOLERANCE = 1e-3


def corrupt_verification(npz: Mapping[str, np.ndarray]) -> str | None:
    """None si le contenu du .npz est un dataset sain, sinon ce qui ne va pas :
    tableau manquant, lignes désalignées avec les chapitres, dimension différente
    des métadonnées, chapitre en double, NaN, norme différente de 1."""
    missing = [key for key in REQUIRED if key not in npz]
    if missing:
        return f"tableaux manquants : {', '.join(missing)}"
    chapters, revision_ids, matrix = npz["chapters"], npz["revision_ids"], npz["embeddings"]
    dimension = int(npz["dimension"])
    if chapters.ndim != 1 or revision_ids.shape != chapters.shape:
        return f"chapters {chapters.shape} et revision_ids {revision_ids.shape} désalignés"
    if matrix.shape != (len(chapters), dimension):
        return f"embeddings {matrix.shape} au lieu de ({len(chapters)}, {dimension})"
    if len(np.unique(chapters)) != len(chapters):
        return "chapitre en double"
    if not np.isfinite(matrix).all():
        return "valeurs non finies (NaN ou infini)"
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if norms.size and np.abs(norms - 1.0).max() > NORM_TOLERANCE:
        return f"normes entre {norms.min():.4f} et {norms.max():.4f}, au lieu de 1"
    return None


def load_chapter_embeddings(data_dir: Path = paths.DATA_DIR) -> ChapterEmbeddings:
    """{chapitre: Chapter embedding float32 de dimension d}, avec `.revision_ids` et `.metadata`.

    FileNotFoundError si le dataset n'existe pas ; CorruptDatasetError s'il ne
    passe pas `corrupt_verification`."""
    path = dataset_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        with np.load(path, allow_pickle=False) as npz:
            arrays = {key: npz[key] for key in npz.files}
    except (OSError, ValueError, EOFError, zipfile.BadZipFile) as exc:
        raise CorruptDatasetError(f"{path} : archive illisible ({exc}) ; relancer avec --rebuild") from exc
    problem = corrupt_verification(arrays)
    if problem is not None:
        raise CorruptDatasetError(f"{path} : {problem} ; relancer avec --rebuild")
    chapters = [int(c) for c in arrays["chapters"]]
    matrix = arrays["embeddings"]
    metadata = Metadata(
        model=str(arrays["model"]),
        dimension=int(arrays["dimension"]),
        pooling=str(arrays["pooling"]),
        created_at=str(arrays["created_at"]),
    )
    return ChapterEmbeddings(
        embeddings={c: matrix[i] for i, c in enumerate(chapters)},
        revision_ids={c: int(r) for c, r in zip(chapters, arrays["revision_ids"])},
        metadata=metadata,
    )

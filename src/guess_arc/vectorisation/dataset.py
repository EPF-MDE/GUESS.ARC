"""Le dataset des Chapter embeddings : un .npz unique sous data/gold/vector/.

La ligne i de `embeddings` est le Chapter embedding du chapitre `chapters[i]`.
Le chargeur rend un dict chapitre -> Chapter embedding, pour que personne ne lise un
Chapter embedding par sa position. Il refuse un dataset corrompu
(`dataset_problem`) au lieu de rendre des Chapter embeddings faux.
"""

from __future__ import annotations

import os
import tempfile
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
TEXT_FIELDS = ("model", "pooling", "created_at")
# Tolérance sur la norme L2 : les vecteurs sont stockés en float32.
NORM_TOLERANCE = 1e-3


def _integer_scalar_problem(array: np.ndarray) -> str | None:
    if array.ndim != 0:
        return f"tableau de forme {array.shape} au lieu d'un scalaire"
    if array.dtype.kind not in "iu":
        return f"type {array.dtype} au lieu d'un entier"
    return None


def dataset_problem(npz: Mapping[str, np.ndarray]) -> str | None:
    """None si le contenu du .npz est un dataset sain, sinon ce qui ne va pas :
    tableau manquant, tableau d'une forme ou d'un type inattendu (dimension qui
    n'est pas un entier scalaire, chapitres ou revision_ids qui ne sont pas des
    entiers 1-D, matrice qui n'est pas 2-D de flottants...), lignes désalignées
    avec les chapitres, dimension différente des métadonnées, chapitre en
    double, NaN, norme différente de 1. Ne lève jamais d'exception : après un
    None, le chargeur peut convertir chaque tableau sans risque."""
    missing = [key for key in REQUIRED if key not in npz]
    if missing:
        return f"tableaux manquants : {', '.join(missing)}"
    dimension_problem = _integer_scalar_problem(npz["dimension"])
    if dimension_problem:
        return f"dimension : {dimension_problem}"
    for key in TEXT_FIELDS:
        if npz[key].ndim != 0 or npz[key].dtype.kind != "U":
            return f"{key} : tableau {npz[key].dtype} de forme {npz[key].shape} au lieu d'un texte"
    chapters, revision_ids, matrix = npz["chapters"], npz["revision_ids"], npz["embeddings"]
    for key, array in (("chapters", chapters), ("revision_ids", revision_ids)):
        if array.ndim != 1 or array.dtype.kind not in "iu":
            return f"{key} : tableau {array.dtype} de forme {array.shape} au lieu d'entiers 1-D"
    if revision_ids.shape != chapters.shape:
        return f"chapters {chapters.shape} et revision_ids {revision_ids.shape} désalignés"
    if matrix.ndim != 2 or matrix.dtype.kind != "f":
        return f"embeddings : tableau {matrix.dtype} de forme {matrix.shape} au lieu d'une matrice 2-D de flottants"
    dimension = int(npz["dimension"])
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

    FileNotFoundError si le dataset n'existe pas ; CorruptDatasetError si
    l'archive est illisible ou si `dataset_problem` y trouve un problème."""
    path = dataset_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        with np.load(path, allow_pickle=False) as npz:
            arrays = {key: npz[key] for key in npz.files}
    except Exception as exc:  # zip, zlib, en-tête .npy : toute archive illisible
        raise CorruptDatasetError(f"{path} : archive illisible ({exc}) ; relancer avec --rebuild") from exc
    problem = dataset_problem(arrays)
    if problem is not None:
        raise CorruptDatasetError(f"{path} : {problem} ; relancer avec --rebuild")
    chapters = [int(c) for c in arrays["chapters"]]
    matrix = arrays["embeddings"].astype(np.float32)
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

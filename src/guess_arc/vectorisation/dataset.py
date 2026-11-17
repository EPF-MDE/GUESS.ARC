"""Le dataset des Chapter embeddings : un .npz unique sous data/gold/vector/.

La ligne i de `embeddings` est le Chapter embedding du chapitre `chapters[i]`.
Les chapitres sans Chapter embedding n'ont pas de ligne (jamais de vecteur nul) :
ils sont listés dans `skipped_chapters`, avec leur raison au même indice de
`skipped_reasons`. Le chargeur rend un dict chapitre -> Chapter embedding, pour
que personne ne lise un Chapter embedding par sa position. Il refuse un dataset corrompu
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
    chapitre, les chapitres sautés ({chapitre: raison}, sans Chapter embedding)
    et les métadonnées du dataset."""

    def __init__(
        self,
        embeddings: dict[int, np.ndarray],
        revision_ids: dict[int, int],
        metadata: Metadata,
        skipped: dict[int, str],
    ):
        super().__init__(embeddings)
        self.revision_ids = revision_ids
        self.metadata = metadata
        self.skipped = skipped


Writer = Callable[[BinaryIO], None]


def write_together(writers: Mapping[Path, Writer]) -> None:
    """Écrit plusieurs fichiers ensemble : chacun est d'abord écrit en entier
    dans un fichier temporaire de son dossier, puis, une fois tous prêts, ils
    remplacent les anciens l'un après l'autre. Si l'écriture d'un fichier
    temporaire échoue, aucun ancien fichier n'est touché et aucun fichier
    temporaire ne reste. Seul un échec entre deux remplacements laisse un
    nouveau fichier à côté d'un ancien."""
    temporaries: dict[Path, Path] = {}
    try:
        for path, write in writers.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            temporaries[path] = Path(tmp_name)
            try:
                fh = os.fdopen(fd, "wb")
            except BaseException:
                os.close(fd)
                raise
            with fh:
                write(fh)
        for path, tmp in temporaries.items():
            os.replace(tmp, path)
    finally:
        for tmp in temporaries.values():
            tmp.unlink(missing_ok=True)


def dataset_writer(embeddings: ChapterEmbeddings) -> Writer:
    """Ce qui écrit le .npz du dataset dans un fichier ouvert (voir `write_together`)."""
    chapters = sorted(embeddings)
    dimension = embeddings.metadata.dimension
    matrix = np.array([embeddings[c] for c in chapters], dtype=np.float32).reshape(len(chapters), dimension)
    skipped = sorted(embeddings.skipped)
    return lambda fh: np.savez(
        fh,
        chapters=np.array(chapters, dtype=np.int64),
        revision_ids=np.array([embeddings.revision_ids[c] for c in chapters], dtype=np.int64),
        embeddings=matrix,
        model=np.array(embeddings.metadata.model),
        dimension=np.array(dimension, dtype=np.int64),
        pooling=np.array(embeddings.metadata.pooling),
        created_at=np.array(embeddings.metadata.created_at),
        skipped_chapters=np.array(skipped, dtype=np.int64),
        # dtype=str : un tableau vide reste un tableau de textes.
        skipped_reasons=np.array([embeddings.skipped[c] for c in skipped], dtype=str),
    )


class CorruptDatasetError(ValueError):
    """Le dataset existe mais est illisible ou incohérent."""


REQUIRED = (
    "chapters", "revision_ids", "embeddings", "model", "dimension", "pooling", "created_at",
    "skipped_chapters", "skipped_reasons",
)
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
    double, NaN, norme différente de 1 ; chapitres sautés qui ne sont pas des
    entiers 1-D, raisons qui ne sont pas des textes 1-D, chapitres sautés et
    raisons désalignés, chapitre sauté en double ou aussi vectorisé. Ne lève jamais d'exception : après un
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
    skipped, reasons = npz["skipped_chapters"], npz["skipped_reasons"]
    for key, array in (("chapters", chapters), ("revision_ids", revision_ids), ("skipped_chapters", skipped)):
        if array.ndim != 1 or array.dtype.kind not in "iu":
            return f"{key} : tableau {array.dtype} de forme {array.shape} au lieu d'entiers 1-D"
    if reasons.ndim != 1 or reasons.dtype.kind != "U":
        return f"skipped_reasons : tableau {reasons.dtype} de forme {reasons.shape} au lieu de textes 1-D"
    if revision_ids.shape != chapters.shape:
        return f"chapters {chapters.shape} et revision_ids {revision_ids.shape} désalignés"
    if reasons.shape != skipped.shape:
        return f"skipped_chapters {skipped.shape} et skipped_reasons {reasons.shape} désalignés"
    if matrix.ndim != 2 or matrix.dtype.kind != "f":
        return f"embeddings : tableau {matrix.dtype} de forme {matrix.shape} au lieu d'une matrice 2-D de flottants"
    dimension = int(npz["dimension"])
    if matrix.shape != (len(chapters), dimension):
        return f"embeddings {matrix.shape} au lieu de ({len(chapters)}, {dimension})"
    if len(np.unique(chapters)) != len(chapters):
        return "chapitre en double"
    if len(np.unique(skipped)) != len(skipped):
        return "chapitre sauté en double"
    both = np.intersect1d(chapters, skipped)
    if both.size:
        return f"chapitres à la fois vectorisés et sautés : {', '.join(str(c) for c in both)}"
    if not np.isfinite(matrix).all():
        return "valeurs non finies (NaN ou infini)"
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if norms.size and np.abs(norms - 1.0).max() > NORM_TOLERANCE:
        return f"normes entre {norms.min():.4f} et {norms.max():.4f}, au lieu de 1"
    return None


def load_chapter_embeddings(data_dir: Path = paths.DATA_DIR) -> ChapterEmbeddings:
    """{chapitre: Chapter embedding float32 de dimension d}, avec `.revision_ids`,
    `.skipped` ({chapitre sauté: raison}) et `.metadata`.

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
        skipped={int(c): str(r) for c, r in zip(arrays["skipped_chapters"], arrays["skipped_reasons"])},
    )

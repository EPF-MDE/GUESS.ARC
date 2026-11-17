"""Le rapport qualité de la vectorisation : embeddings_quality.json, à côté du dataset.

Il sert à repérer un trou ou un dataset corrompu (chapitres sautés, NaN,
normes différentes de 1), et à montrer que les Chapter embeddings capturent le
sens de l'histoire : deux chapitres d'un même arc doivent être plus proches que
deux chapitres d'arcs différents. Voir docs/vectorisation.md (section 8).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import BinaryIO

import numpy as np

from guess_arc import paths

from .dataset import ChapterEmbeddings, Writer

FILENAME = "embeddings_quality.json"


def report_path(data_dir: Path = paths.DATA_DIR) -> Path:
    return paths.vector_dir(data_dir) / FILENAME


def _finite_or_none(value: float) -> float | None:
    """JSON n'a ni NaN ni infini : une valeur non finie devient null."""
    return float(value) if math.isfinite(value) else None


def _mean_or_none(values: list[float]) -> float | None:
    return _finite_or_none(float(np.mean(values))) if values else None


def _semantic_coherence(matrix: np.ndarray, arcs: list[str]) -> dict:
    """Moyenne par Arc, chaque Arc pesant autant quelle que soit sa longueur.

    Intra-arc : la moyenne, sur les Arcs d'au moins deux chapitres, de la
    similarité cosinus moyenne entre deux chapitres de l'Arc. Inter-arc : la
    moyenne, sur les couples d'Arcs différents, de la similarité moyenne entre
    un chapitre de l'un et un chapitre de l'autre. Un Arc d'un seul chapitre
    n'a pas de moyenne intra-arc ; sans aucune moyenne, la valeur est null."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    unit = matrix / np.where(norms == 0, 1.0, norms)
    similarity = unit @ unit.T
    members = {arc: np.flatnonzero(np.array(arcs, dtype=object) == arc) for arc in sorted(set(arcs))}

    intra = []
    for rows in members.values():
        if len(rows) >= 2:
            block = similarity[np.ix_(rows, rows)]
            intra.append(float(block[np.triu_indices(len(rows), k=1)].mean()))
    groups = list(members.values())
    inter = [
        float(similarity[np.ix_(a, b)].mean())
        for i, a in enumerate(groups)
        for b in groups[i + 1:]
    ]
    intra_mean, inter_mean = _mean_or_none(intra), _mean_or_none(inter)
    gap = intra_mean - inter_mean if intra_mean is not None and inter_mean is not None else None
    return {
        "arcs": len(members),
        "intra_arc_mean": intra_mean,
        "inter_arc_mean": inter_mean,
        "gap": gap,
        "intra_arcs": len(intra),  # Arcs d'au moins deux chapitres
        "arc_pairs": len(inter),  # couples d'Arcs différents
    }


def quality_report(
    embeddings: ChapterEmbeddings,
    arcs: dict[int, str],
    kept: list[int],
) -> dict:
    """Le rapport sur le dataset tel qu'écrit. Ses chapitres sont les `kept`,
    repris du dataset précédent, et les vectorisés à cette exécution ; `arcs`
    donne l'arc silver de chacun. Les chapitres sautés et leurs raisons sont
    ceux du dataset."""
    chapters = sorted(embeddings)
    matrix = np.array([embeddings[c] for c in chapters], dtype=np.float64).reshape(
        len(chapters), embeddings.metadata.dimension
    )
    norms = np.linalg.norm(matrix, axis=1)
    return {
        "model": embeddings.metadata.model,
        "pooling": embeddings.metadata.pooling,
        "created_at": embeddings.metadata.created_at,
        "chapters": {
            "total": len(chapters),
            "vectorised": sorted(set(chapters) - set(kept)),
            "kept": sorted(kept),
            "skipped": {str(c): why for c, why in sorted(embeddings.skipped.items())},
        },
        "dimension": embeddings.metadata.dimension,
        "nan_count": int(np.isnan(matrix).sum()),
        "norm_min": _finite_or_none(norms.min()) if norms.size else None,
        "norm_max": _finite_or_none(norms.max()) if norms.size else None,
        "semantic_coherence": _semantic_coherence(matrix, [arcs[c] for c in chapters]),
    }


def report_writer(report: dict) -> Writer:
    """Ce qui écrit le rapport en JSON dans un fichier ouvert (voir `write_together`)."""
    def write(fh: BinaryIO) -> None:
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        fh.write(text.encode("utf-8"))

    return write

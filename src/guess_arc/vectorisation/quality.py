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

import numpy as np

from guess_arc import paths

from .dataset import ChapterEmbeddings, atomic_write

FILENAME = "embeddings_quality.json"


def report_path(data_dir: Path = paths.DATA_DIR) -> Path:
    return paths.vector_dir(data_dir) / FILENAME


def _finite_or_none(value: float) -> float | None:
    """JSON n'a ni NaN ni infini : une valeur non finie devient null."""
    return float(value) if math.isfinite(value) else None


def _semantic_coherence(matrix: np.ndarray, arcs: list[str]) -> dict:
    """Similarité cosinus moyenne sur toutes les paires de chapitres d'un même
    arc, contre toutes les paires d'arcs différents. Un arc d'un seul chapitre
    n'apporte aucune paire intra-arc ; sans paire, la moyenne vaut null."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    unit = matrix / np.where(norms == 0, 1.0, norms)
    similarity = unit @ unit.T
    labels = np.array(arcs, dtype=object)
    upper = np.triu(np.ones_like(similarity, dtype=bool), k=1)
    same_arc = labels[:, None] == labels[None, :]

    intra = similarity[upper & same_arc]
    inter = similarity[upper & ~same_arc]
    intra_mean = _finite_or_none(intra.mean()) if intra.size else None
    inter_mean = _finite_or_none(inter.mean()) if inter.size else None
    gap = intra_mean - inter_mean if intra_mean is not None and inter_mean is not None else None
    return {
        "arcs": len(set(arcs)),
        "intra_arc_mean": intra_mean,
        "inter_arc_mean": inter_mean,
        "gap": gap,
        "intra_arc_pairs": int(intra.size),
        "inter_arc_pairs": int(inter.size),
    }


def quality_report(
    embeddings: ChapterEmbeddings,
    arcs: dict[int, str],
    kept: list[int],
    skipped: dict[int, str],
) -> dict:
    """Le rapport sur le dataset tel qu'écrit. Ses chapitres sont les `kept`,
    repris du dataset précédent, et les vectorisés à cette exécution ; `arcs`
    donne l'arc silver de chacun."""
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
            "skipped": {str(c): why for c, why in sorted(skipped.items())},
        },
        "dimension": embeddings.metadata.dimension,
        "nan_count": int(np.isnan(matrix).sum()),
        "norm_min": _finite_or_none(norms.min()) if norms.size else None,
        "norm_max": _finite_or_none(norms.max()) if norms.size else None,
        "semantic_coherence": _semantic_coherence(matrix, [arcs[c] for c in chapters]),
    }


def write_report(path: Path, report: dict) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    atomic_write(path, lambda fh: fh.write(text.encode("utf-8")))

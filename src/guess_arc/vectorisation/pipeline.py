"""Vectorise la silver en Chapter embeddings, dans data/gold/vector/.

Pour chaque chapitre complet de la silver, le Long Summary est découpé en
Scenes, une Scene plus longue que la fenêtre de l'encodeur est découpée en
fenêtres qui se chevauchent, chaque Chunk est encodé, et le Chapter embedding
est la moyenne des vecteurs de Chunks pondérée par leur nombre de tokens,
normalisée L2. Voir docs/vectorisation.md et l'ADR 0003.

Le modèle se règle dans le .env (EMBEDDING_MODEL). Nécessite l'extra
[vectorisation] : pip install -e .[vectorisation]

Incrémental par défaut : seuls les chapitres nouveaux, ou dont le revision_id
silver a changé, passent par l'encodeur. --rebuild recalcule tout.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from guess_arc import paths
from guess_arc.ingestion.silver import SilverChapter, read_chapter

from .dataset import (
    ChapterEmbeddings,
    CorruptDatasetError,
    Metadata,
    dataset_path,
    dataset_writer,
    load_chapter_embeddings,
    write_together,
)
from .encoder import Encoder
from .quality import quality_report, report_path, report_writer
from .sentence_encoder import MissingExtraError, SentenceTransformerEncoder

POOLING = "chunk-mean-token-weighted-l2"
# Les fenêtres d'une Scene trop longue se chevauchent d'environ 1/4 de fenêtre.
OVERLAP_DIVISOR = 4

PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n")


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
    vectorised: list[int]  # passés par l'encodeur à cette exécution
    kept: list[int]  # repris tels quels du dataset précédent
    skipped: dict[int, str]  # chapitre -> raison
    rebuild_reason: str | None = None  # pourquoi rien n'a été repris ; None si incrémental


def _previous_dataset(data_dir: Path, encoder: Encoder, rebuild: bool) -> tuple[ChapterEmbeddings | None, str | None]:
    """Le dataset précédent, si ses Chapter embeddings peuvent être conservés,
    sinon None et la raison du recalcul complet : `rebuild`, dataset corrompu,
    ou changement de modèle ou de pooling (les Chapter embeddings de deux
    modèles ne sont pas comparables). Pas de dataset précédent : (None, None)."""
    if rebuild:
        return None, "--rebuild demandé"
    try:
        previous = load_chapter_embeddings(data_dir)
    except FileNotFoundError:
        return None, None
    except CorruptDatasetError as exc:
        return None, f"dataset précédent corrompu ({exc})"
    if previous.metadata.model != encoder.model_name:
        return None, f"modèle changé : {previous.metadata.model} -> {encoder.model_name}"
    if previous.metadata.pooling != POOLING:
        return None, f"pooling changé : {previous.metadata.pooling} -> {POOLING}"
    return previous, None


@dataclass
class _Update:
    """Le contenu du dataset à écrire, chapitre par chapitre."""
    embeddings: dict[int, np.ndarray]
    revision_ids: dict[int, int]
    vectorised: list[int]
    kept: list[int]
    skipped: dict[int, str]


def _update(
    silver: list[SilverChapter],
    previous: ChapterEmbeddings | None,
    encode: Callable[[SilverChapter, list[str]], np.ndarray],
) -> _Update:
    update = _Update({}, {}, [], [], {})
    for chapter in silver:
        scene_texts = scenes(chapter.long_summary)
        if not chapter.complete:
            update.skipped[chapter.number] = "complete: false"
            continue
        if not scene_texts:
            update.skipped[chapter.number] = "Long Summary vide"
            continue
        if previous is not None and previous.revision_ids.get(chapter.number) == chapter.revision_id:
            update.embeddings[chapter.number] = previous[chapter.number]
            update.kept.append(chapter.number)
        else:
            update.embeddings[chapter.number] = encode(chapter, scene_texts)
            update.vectorised.append(chapter.number)
        update.revision_ids[chapter.number] = chapter.revision_id
    return update


def run(data_dir: Path, encoder: Encoder, *, rebuild: bool = False) -> RunResult:
    """Met à jour le dataset des chapitres complets de la silver, et son rapport qualité.

    Incrémental par défaut : un chapitre déjà dans le dataset avec le même
    revision_id est conservé avec son Chapter embedding, les autres sont
    (re)vectorisés. Tout est recalculé si `rebuild`, si le dataset précédent est
    corrompu, si le modèle de l'encodeur diffère de celui du dataset, ou si
    l'encodeur rend désormais des vecteurs d'une autre dimension. Un chapitre
    `complete: false` ou sans Scene n'a pas de Chapter embedding : il est
    listé dans les chapitres sautés du dataset, avec sa raison. Un chapitre
    absent de la silver n'a aucune entrée dans le dataset.
    """
    silver = [read_chapter(path) for path in sorted(paths.silver_dir(data_dir).glob("chapter_*.md"))]
    previous, rebuild_reason = _previous_dataset(data_dir, encoder, rebuild)

    # Un chapitre n'est encodé qu'une fois, même si l'on recommence sans reprise.
    encoded: dict[int, np.ndarray] = {}

    def encode(chapter: SilverChapter, scene_texts: list[str]) -> np.ndarray:
        if chapter.number not in encoded:
            encoded[chapter.number] = chapter_embedding(scene_texts, encoder)
        return encoded[chapter.number]

    update = _update(silver, previous, encode)
    if previous is not None:
        new_dimensions = {update.embeddings[c].shape[0] for c in update.vectorised} - {previous.metadata.dimension}
        if new_dimensions and update.kept:
            # Même nom de modèle, autre dimension : on ne mélange pas les deux.
            rebuild_reason = f"dimension de l'encodeur changée : {previous.metadata.dimension} -> {min(new_dimensions)}"
            update = _update(silver, None, encode)

    dimensions = {v.shape[0] for v in update.embeddings.values()}
    if len(dimensions) > 1:
        raise ValueError(f"dimensions incohérentes entre chapitres : {sorted(dimensions)}")
    metadata = Metadata(
        model=encoder.model_name,
        dimension=dimensions.pop() if dimensions else 0,
        pooling=POOLING,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    dataset = ChapterEmbeddings(update.embeddings, update.revision_ids, metadata, skipped=update.skipped)
    arcs = {chapter.number: chapter.arc for chapter in silver}
    report = quality_report(dataset, arcs, kept=update.kept)
    target, quality_target = dataset_path(data_dir), report_path(data_dir)
    # Le dataset et son rapport sont remplacés ensemble, une fois tous deux prêts.
    write_together({target: dataset_writer(dataset), quality_target: report_writer(report)})
    return RunResult(
        path=target,
        quality_path=quality_target,
        vectorised=sorted(update.vectorised),
        kept=sorted(update.kept),
        skipped=update.skipped,
        rebuild_reason=rebuild_reason,
    )


SETTING = "EMBEDDING_MODEL"
ENV_FILE = paths.REPO_ROOT / ".env"


class _MissingSettingError(RuntimeError):
    """EMBEDDING_MODEL n'est réglé ni dans l'environnement ni dans le .env."""


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.is_file():
        return {}
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _embedding_model(environ: Mapping[str, str], env_file: Path) -> str:
    """Le modèle à utiliser : variable d'environnement, sinon ligne du .env."""
    model = environ.get(SETTING) or _read_env_file(env_file).get(SETTING)
    if not model:
        raise _MissingSettingError(
            f"{SETTING} absent : l'ajouter au fichier {env_file}, par exemple "
            f"{SETTING}=<identifiant Hugging Face du modèle> (exemple documenté dans .env.example)"
        )
    return model


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] = os.environ,
    env_file: Path = ENV_FILE,
    make_encoder: Callable[[str], Encoder] = SentenceTransformerEncoder,
) -> None:
    p = argparse.ArgumentParser(prog="python -m guess_arc.vectorisation", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches silver/gold (défaut : data/ à la racine du repo)")
    p.add_argument("--rebuild", action="store_true",
                   help="revectorise tous les chapitres, sans reprendre le dataset existant")
    args = p.parse_args(argv)

    try:
        encoder = make_encoder(_embedding_model(environ, env_file))
    except (_MissingSettingError, MissingExtraError) as exc:
        raise SystemExit(f"erreur : {exc}") from exc

    result = run(args.data_dir, encoder, rebuild=args.rebuild)
    if result.rebuild_reason:
        print(f"recalcul complet : {result.rebuild_reason}")
    print(f"chapitres vectorisés : {len(result.vectorised)}, conservés : {len(result.kept)}, "
          f"sautés : {len(result.skipped)} "
          f"-> {result.path}")
    if result.skipped:
        listed = ", ".join(f"{c} ({why})" for c, why in sorted(result.skipped.items()))
        print(f"AVERTISSEMENT : {len(result.skipped)} chapitres sautés : {listed}")
    print(f"rapport qualité -> {result.quality_path}")


if __name__ == "__main__":
    main()

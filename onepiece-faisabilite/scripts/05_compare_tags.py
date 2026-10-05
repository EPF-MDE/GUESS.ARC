#!/usr/bin/env python3
"""Étape 5 — comparaison de deux ensembles de tags (prédiction vs réalité).

Prend deux fichiers JSON produits par `04_tag_text.py` (une liste de
{"category", "tag", ...}), calcule un score de Jaccard par catégorie
(intersection / union des tags de cette catégorie), affiche un tableau
récapitulatif dans le terminal, puis une moyenne pondérée globale.

Les poids par catégorie viennent de `weights.json` (event et rel pèsent plus
que lieu par défaut — un événement manqué compte plus qu'un lieu manqué pour
juger la qualité d'une prédiction). Catégorie absente du fichier de poids ->
poids 1.0.

Usage :
    python 05_compare_tags.py prediction.json realite.json [--weights weights.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from taxonomy.console import ensure_utf8_stdout

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHT = 1.0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prediction", type=Path, help="Fichier JSON de tags prédits.")
    parser.add_argument("realite", type=Path, help="Fichier JSON de tags réels.")
    parser.add_argument("--weights", type=Path, default=BASE_DIR / "weights.json")
    return parser


def _load_tags(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tags_by_category(tags: list[dict]) -> dict[str, set[str]]:
    by_category: dict[str, set[str]] = {}
    for t in tags:
        by_category.setdefault(t["category"], set()).add(t["tag"])
    return by_category


def _jaccard(a: set[str], b: set[str]) -> tuple[int, int, float]:
    """Retourne (taille intersection, taille union, score de Jaccard)."""
    inter, union = a & b, a | b
    score = len(inter) / len(union) if union else 1.0  # deux ensembles vides = accord parfait
    return len(inter), len(union), score


def compare(pred_tags: list[dict], real_tags: list[dict], weights: dict[str, float]) -> list[dict]:
    """Calcule le tableau de comparaison par catégorie. Réutilisable hors CLI."""
    pred_by_cat = _tags_by_category(pred_tags)
    real_by_cat = _tags_by_category(real_tags)
    categories = sorted(set(pred_by_cat) | set(real_by_cat))

    rows = []
    for category in categories:
        pred_set = pred_by_cat.get(category, set())
        real_set = real_by_cat.get(category, set())
        n_common, n_total, score = _jaccard(pred_set, real_set)
        rows.append(
            {
                "category": category,
                "n_common": n_common,
                "n_total": n_total,
                "score": score,
                "weight": weights.get(category, DEFAULT_WEIGHT),
            }
        )
    return rows


def weighted_average(rows: list[dict]) -> float:
    total_weight = sum(r["weight"] for r in rows)
    if total_weight == 0:
        return 0.0
    return sum(r["score"] * r["weight"] for r in rows) / total_weight


def print_table(rows: list[dict], average: float) -> None:
    header = f"{'catégorie':<12} {'communs':>8} {'total':>8} {'score':>8} {'poids':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['category']:<12} {r['n_common']:>8} {r['n_total']:>8} {r['score']:>8.2%} {r['weight']:>7.2f}")
    print("-" * len(header))
    print(f"{'MOYENNE PONDÉRÉE':<12} {'':>8} {'':>8} {average:>8.2%}")


def main() -> None:
    args = build_arg_parser().parse_args()

    weights = {}
    if args.weights.exists():
        weights = json.loads(args.weights.read_text(encoding="utf-8"))
    else:
        print(f"[05_compare_tags] {args.weights} introuvable -> poids par défaut ({DEFAULT_WEIGHT}) pour toutes les catégories.")

    pred_tags = _load_tags(args.prediction)
    real_tags = _load_tags(args.realite)

    rows = compare(pred_tags, real_tags, weights)
    average = weighted_average(rows)
    print_table(rows, average)


if __name__ == "__main__":
    main()

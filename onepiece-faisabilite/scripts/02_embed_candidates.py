#!/usr/bin/env python3
"""Étape 2 — encodage vectoriel des termes candidats uniques.

Regroupe les candidats de `candidates.csv` par (catégorie, terme), calcule
leur fréquence, puis encode chaque terme unique avec un modèle d'embedding
multilingue local (repli TF-IDF sur n-grams de caractères si le modèle n'est
pas téléchargeable — voir taxonomy/embedding.py).

Sorties :
    output/embeddings.npy       — matrice (n_termes_uniques, dim)
    output/terms.json           — métadonnées alignées ligne à ligne avec embeddings.npy
    output/embedder_meta.json   — mode utilisé, pour que 04_tag_text.py réencode pareil

Usage :
    python 02_embed_candidates.py [--candidates output/candidates.csv] [--output-dir output]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from taxonomy.console import ensure_utf8_stdout
from taxonomy.embedding import Embedder

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=BASE_DIR / "output" / "candidates.csv")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.candidates, dtype=str).fillna("")
    print(f"[02_embed_candidates] {len(df)} lignes de candidats chargées.")

    # Un terme "perso" issu du front-matter (source fiable à 100 %, cf. 01_extract_candidates.py)
    # sert d'ancre de canonicalisation en étape 3 : on le distingue des candidats NER bruités.
    df["is_frontmatter"] = df["context_snippet"].str.startswith("frontmatter:")

    grouped = (
        df.groupby(["category_guess", "raw_term"])
        .agg(
            count=("chapter_id", "size"),
            n_chapters=("chapter_id", "nunique"),
            sample_context=("context_snippet", "first"),
            from_frontmatter=("is_frontmatter", "any"),
        )
        .reset_index()
        .sort_values(["category_guess", "count"], ascending=[True, False])
        .reset_index(drop=True)
    )
    print(f"[02_embed_candidates] {len(grouped)} termes uniques (catégorie, terme).")

    terms = [
        {
            "id": i,
            "category": row.category_guess,
            "term": row.raw_term,
            "count": int(row.count),
            "n_chapters": int(row.n_chapters),
            "sample_context": row.sample_context,
            "from_frontmatter": bool(row.from_frontmatter),
        }
        for i, row in enumerate(grouped.itertuples(index=False))
    ]

    embedder = Embedder.build(fit_corpus=[t["term"] for t in terms])
    embeddings = embedder.encode([t["term"] for t in terms])
    print(f"[02_embed_candidates] embeddings calculés : {embeddings.shape}")

    np.save(args.output_dir / "embeddings.npy", embeddings)
    (args.output_dir / "terms.json").write_text(
        json.dumps(terms, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    embedder.save(args.output_dir)

    print(f"[02_embed_candidates] terminé -> {args.output_dir}")


if __name__ == "__main__":
    main()

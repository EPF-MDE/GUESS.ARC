#!/usr/bin/env python3
"""Étape 4 — réduction d'un texte libre en tags typés, via la taxonomie construite.

`tag_text()` est la fonction réutilisable demandée par la spec : elle
reprend l'extraction de candidats de l'étape 1 (même module `taxonomy.extraction`,
donc même logique que sur le corpus) sur un texte isolé — un résumé source
OU une prédiction écrite à la main — puis mappe chaque candidat vers le tag
canonique le plus proche de la taxonomie (similarité cosinus, avec un seuil
minimal ; en dessous, le tag reste "brut").

Usage CLI :
    python 04_tag_text.py --file mon_resume.md
    python 04_tag_text.py --text "Luffy et Zoro affrontent un nouvel ennemi..."
    -> JSON sur stdout : [{"category": "event", "tag": "combat", "confidence": 0.87}, ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from taxonomy.console import ensure_utf8_stdout
from taxonomy.embedding import Embedder
from taxonomy.extraction import extract_candidates, load_nlp

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _flatten_taxonomy(taxonomy: dict) -> dict[str, list[str]]:
    """{category: [tous les labels canoniques de cette catégorie]}."""
    return {category: list(labels.keys()) for category, labels in taxonomy.items()}


def _exact_match_lookup(taxonomy: dict) -> dict[tuple[str, str], str]:
    """{(category, forme_de_surface_en_minuscules): canonique} pour un raccourci sans embedding."""
    lookup: dict[tuple[str, str], str] = {}
    for category, labels in taxonomy.items():
        for canonical, variants in labels.items():
            lookup[(category, canonical.lower())] = canonical
            for variant in variants:
                lookup[(category, variant.lower())] = canonical
    return lookup


def tag_text(
    text: str,
    taxonomy: dict,
    embedder: Embedder,
    nlp=None,
    min_similarity: float = 0.5,
) -> list[dict]:
    """Réduit un texte libre en tags typés à partir de la taxonomie fournie.

    Pour chaque candidat extrait : correspondance exacte (insensible à la
    casse) avec un label ou une variante connue en priorité ; sinon,
    similarité cosinus au label canonique le plus proche de la même
    catégorie. Sous `min_similarity`, le tag reste la forme brute extraite
    (mapped=False).
    """
    candidates = extract_candidates(text, nlp=nlp)
    if not candidates:
        return []

    exact_lookup = _exact_match_lookup(taxonomy)
    canonical_by_category = _flatten_taxonomy(taxonomy)

    # Embeddings des labels canoniques, un seul appel par catégorie présente.
    canonical_vectors: dict[str, np.ndarray] = {}
    for category, labels in canonical_by_category.items():
        if labels:
            canonical_vectors[category] = embedder.encode(labels)

    raw_terms = [c.raw_term for c in candidates]
    candidate_vectors = embedder.encode(raw_terms)

    results = []
    for cand, vector in zip(candidates, candidate_vectors):
        exact = exact_lookup.get((cand.category_guess, cand.raw_term.lower()))
        if exact is not None:
            results.append(
                {"category": cand.category_guess, "tag": exact, "confidence": 1.0, "raw_term": cand.raw_term}
            )
            continue

        labels = canonical_by_category.get(cand.category_guess, [])
        vectors = canonical_vectors.get(cand.category_guess)
        if not labels or vectors is None or vectors.shape[0] == 0:
            results.append(
                {"category": cand.category_guess, "tag": cand.raw_term, "confidence": 0.0, "raw_term": cand.raw_term, "mapped": False}
            )
            continue

        vec_norm = np.linalg.norm(vector) or 1.0
        label_norms = np.linalg.norm(vectors, axis=1)
        label_norms[label_norms == 0] = 1.0
        sims = (vectors @ vector) / (label_norms * vec_norm)
        best = int(np.argmax(sims))
        confidence = float(sims[best])

        if confidence >= min_similarity:
            results.append(
                {"category": cand.category_guess, "tag": labels[best], "confidence": round(confidence, 4), "raw_term": cand.raw_term}
            )
        else:
            results.append(
                {
                    "category": cand.category_guess,
                    "tag": cand.raw_term,
                    "confidence": round(confidence, 4),
                    "raw_term": cand.raw_term,
                    "mapped": False,
                }
            )
    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Fichier texte/Markdown à taguer.")
    source.add_argument("--text", type=str, help="Texte brut à taguer.")
    parser.add_argument("--taxonomy", type=Path, default=BASE_DIR / "output" / "taxonomy.json")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output", help="Dossier contenant embedder_meta.json.")
    parser.add_argument("--min-similarity", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=None, help="Fichier de sortie JSON (sinon stdout).")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    text = args.text if args.text is not None else _read_text_file(args.file)

    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    embedder = Embedder.load(args.output_dir)
    nlp, mode = load_nlp()
    print(f"[04_tag_text] mode d'extraction : {mode}")

    tags = tag_text(text, taxonomy, embedder, nlp=nlp, min_similarity=args.min_similarity)
    output = json.dumps(tags, ensure_ascii=False, indent=2)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"[04_tag_text] {len(tags)} tags -> {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Étape 3 — clusterisation des termes candidats en taxonomie canonique.

Pour chaque catégorie (perso, lieu, objet, event, rel), regroupe les termes
sémantiquement proches (ex. "Luffy", "Monkey D. Luffy", "le capitaine") en
clusters, sans fixer leur nombre à l'avance : HDBSCAN, ou à défaut
AgglomerativeClustering à seuil de distance fixe (voir --distance-threshold).

Le label canonique d'un cluster est son terme le plus fréquent dans le corpus.
Les clusters dont la fréquence totale vaut 1 (un seul terme, vu une seule
fois) sont considérés comme du bruit probable et écrits à part, pas
supprimés : output/taxonomy_noise.json.

HDBSCAN chaîne parfois des noms propres courts qui n'ont rien à voir entre eux
(deux personnages différents peuvent avoir des embeddings proches simplement
parce que ce sont de courtes chaînes "à consonance de nom"). On purifie donc
chaque cluster après coup : un membre dont la similarité cosinus au canonique
(le terme le plus fréquent) tombe sous --min-similarity est éjecté dans son
propre cluster plutôt que fusionné à tort.

Pour perso/lieu/objet, une étape préalable interroge le wiki Fandom (mêmes
redirections que `onepiece_ingest.py`) pour résoudre chaque candidat vers son
nom canonique de page (ex. "Zoro" -> "Roronoa Zoro") : c'est une vérité
terrain gratuite et fiable, qui évite l'effet de chaînage de l'embedding sur
les noms propres hors-vocabulaire. Seuls les candidats sans page wiki
retombent dans le clustering par embedding décrit ci-dessus (voir
taxonomy/gazetteer.py et --no-gazetteer).

Usage :
    python 03_cluster_taxonomy.py [--output-dir output] [--distance-threshold 0.35]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from taxonomy.console import ensure_utf8_stdout
from taxonomy.gazetteer import WikiGazetteer

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent

# Catégories où un candidat correspond à une page wiki (personnage, lieu,
# objet). "event"/"rel" sont des tags de lexique déjà canoniques : la
# résolution wiki ne les concerne pas.
GAZETTEER_CATEGORIES = {"perso", "lieu", "objet"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output")
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.35,
        help="Distance cosinus max au sein d'un cluster (repli AgglomerativeClustering uniquement).",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.55,
        help="Similarité cosinus minimale au canonique pour rester dans son cluster.",
    )
    parser.add_argument(
        "--gazetteer-cache",
        type=Path,
        default=BASE_DIR / "output" / "gazetteer_wiki_cache.json",
        help="Cache disque des résolutions wiki (terme -> nom canonique).",
    )
    parser.add_argument(
        "--no-gazetteer",
        action="store_true",
        help="Désactive la résolution par redirections wiki (clustering par embedding pur).",
    )
    return parser


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _cluster_labels(vectors: np.ndarray, distance_threshold: float) -> tuple[np.ndarray, str]:
    """Retourne (labels, méthode utilisée). -1 = point non clusterisé (bruit HDBSCAN)."""
    n = vectors.shape[0]
    if n < 2:
        return np.zeros(n, dtype=int), "trivial"

    try:
        from hdbscan import HDBSCAN

        # min_samples=min_cluster_size (plutôt que 1) : évite l'effet de chaînage du
        # single-linkage, qui fusionnait des noms propres proches en embedding mais
        # sans rapport (ex. tous les personnages courts regroupés ensemble).
        labels = HDBSCAN(min_cluster_size=2, min_samples=2, metric="euclidean").fit_predict(
            _l2_normalize(vectors)
        )
        return labels, "hdbscan"
    except ImportError:
        print("[03_cluster_taxonomy] hdbscan indisponible -> repli AgglomerativeClustering.")
        from sklearn.cluster import AgglomerativeClustering

        labels = AgglomerativeClustering(
            n_clusters=None, distance_threshold=distance_threshold, metric="cosine", linkage="average"
        ).fit_predict(vectors)
        return labels, "agglomerative"


def _build_clusters(
    category_terms: list[dict], vectors: np.ndarray, labels: np.ndarray
) -> list[list[tuple[dict, np.ndarray]]]:
    """Regroupe (terme, vecteur) par label. Chaque point de bruit (-1) forme son propre cluster."""
    groups: dict[int, list[tuple[dict, np.ndarray]]] = {}
    next_noise_id = -1
    for term, vector, label in zip(category_terms, vectors, labels):
        key = label
        if label == -1:
            key = next_noise_id
            next_noise_id -= 1
        groups.setdefault(key, []).append((term, vector))
    return list(groups.values())


def _canonical_index(cluster: list[tuple[dict, np.ndarray]]) -> int:
    """Index (dans le cluster) du terme le plus fréquent, qui sert de canonique."""
    return min(
        range(len(cluster)),
        key=lambda i: (-cluster[i][0]["count"], -len(cluster[i][0]["term"]), cluster[i][0]["term"]),
    )


def _purify_cluster(
    cluster: list[tuple[dict, np.ndarray]], min_similarity: float
) -> list[list[tuple[dict, np.ndarray]]]:
    """Éjecte dans leur propre cluster les membres trop éloignés du canonique.

    Corrige l'effet de chaînage de HDBSCAN : deux points peuvent finir dans le
    même cluster via une chaîne de voisins proches sans jamais être proches
    l'un de l'autre. On revérifie donc chaque membre contre le canonique
    choisi (terme le plus fréquent), pas contre ses seuls voisins directs.
    """
    if len(cluster) < 2:
        return [cluster]
    canonical_vector = cluster[_canonical_index(cluster)][1]
    canonical_norm = np.linalg.norm(canonical_vector) or 1.0
    kept, evicted = [], []
    for term, vector in cluster:
        sim = float(np.dot(vector, canonical_vector) / ((np.linalg.norm(vector) or 1.0) * canonical_norm))
        (kept if sim >= min_similarity else evicted).append((term, vector))
    if not kept:
        kept, evicted = evicted, []
    return [kept] + [[e] for e in evicted]


def _canonical_and_variants(
    cluster: list[tuple[dict, np.ndarray]], forced_canonical: str | None = None
) -> tuple[str, list[str]]:
    """Label canonique = terme le plus fréquent (ou `forced_canonical` s'il est fourni)."""
    canonical = forced_canonical or cluster[_canonical_index(cluster)][0]["term"]
    variants = sorted({term["term"] for term, _ in cluster if term["term"] != canonical})
    return canonical, variants


def _gazetteer_clusters(
    category_terms: list[dict], vectors: np.ndarray, gazetteer: WikiGazetteer
) -> tuple[list[tuple[list[tuple[dict, np.ndarray]], str]], list[int]]:
    """Regroupe les termes résolus par le wiki (page canonique commune).

    Retourne (clusters ancrés sur leur canonique wiki, indices des termes
    sans page wiki -> à clusteriser par embedding en repli).
    """
    resolved = gazetteer.resolve_many([t["term"] for t in category_terms])

    buckets: dict[str, list[int]] = {}
    leftover_indices: list[int] = []
    for i, term in enumerate(category_terms):
        canonical = resolved.get(term["term"])
        if canonical:
            buckets.setdefault(canonical, []).append(i)
        else:
            leftover_indices.append(i)

    clusters = [
        ([(category_terms[i], vectors[i]) for i in idxs], canonical)
        for canonical, idxs in buckets.items()
    ]
    return clusters, leftover_indices


def _cluster_category(
    category_terms: list[dict], vectors: np.ndarray, args
) -> tuple[list[list[tuple[dict, np.ndarray]]], str]:
    """Clusterise une catégorie par HDBSCAN/Agglomerative + purification. Retourne (clusters, méthode)."""
    labels, method = _cluster_labels(vectors, args.distance_threshold)
    raw_clusters = _build_clusters(category_terms, vectors, labels)
    clusters = [
        purified for cluster in raw_clusters for purified in _purify_cluster(cluster, args.min_similarity)
    ]
    return clusters, method


def _anchor_clusters(
    category_terms: list[dict], vectors: np.ndarray, args
) -> tuple[list[tuple[list[tuple[dict, np.ndarray]], str | None]], str]:
    """Canonicalisation "perso" ancrée sur le front-matter (source fiable à 100 %).

    Chaque nom de personnage vu dans le front-matter d'au moins un chapitre
    devient une ancre fixe : jamais fusionnée avec une autre ancre, jamais
    reléguée au bruit. Les candidats NER libres (surnoms, mentions partielles)
    sont rattachés à l'ancre la plus proche en similarité cosinus si elle
    dépasse --min-similarity ; sinon ils repartent dans le clustering standard.
    """
    anchor_idx = [i for i, t in enumerate(category_terms) if t.get("from_frontmatter")]
    free_idx = [i for i, t in enumerate(category_terms) if not t.get("from_frontmatter")]
    if not anchor_idx:
        clusters, method = _cluster_category(category_terms, vectors, args)
        return [(c, None) for c in clusters], method

    anchor_vectors = vectors[anchor_idx]
    anchor_norms = np.linalg.norm(anchor_vectors, axis=1)
    anchor_norms[anchor_norms == 0] = 1.0
    anchor_buckets: list[list[tuple[dict, np.ndarray]]] = [
        [(category_terms[i], vectors[i])] for i in anchor_idx
    ]

    leftover_indices = []
    for i in free_idx:
        vec = vectors[i]
        vec_norm = np.linalg.norm(vec) or 1.0
        sims = (anchor_vectors @ vec) / (anchor_norms * vec_norm)
        best = int(np.argmax(sims))
        if sims[best] >= args.min_similarity:
            anchor_buckets[best].append((category_terms[i], vec))
        else:
            leftover_indices.append(i)

    result = [
        (bucket, category_terms[anchor_idx[b]]["term"]) for b, bucket in enumerate(anchor_buckets)
    ]

    if leftover_indices:
        leftover_terms = [category_terms[i] for i in leftover_indices]
        leftover_vectors = vectors[leftover_indices]
        leftover_clusters, method = _cluster_category(leftover_terms, leftover_vectors, args)
        result.extend((c, None) for c in leftover_clusters)
    else:
        method = "ancré front-matter"

    return result, method


def main() -> None:
    args = build_arg_parser().parse_args()

    terms = json.loads((args.output_dir / "terms.json").read_text(encoding="utf-8"))
    embeddings = np.load(args.output_dir / "embeddings.npy")

    gazetteer = None if args.no_gazetteer else WikiGazetteer(args.gazetteer_cache)

    taxonomy: dict[str, dict[str, list[str]]] = {}
    taxonomy_noise: dict[str, dict[str, list[str]]] = {}

    categories = sorted({t["category"] for t in terms})
    for category in categories:
        indices = [i for i, t in enumerate(terms) if t["category"] == category]
        category_terms = [terms[i] for i in indices]
        vectors = embeddings[indices]

        total_terms = len(category_terms)
        gaz_clusters: list[tuple[list[tuple[dict, np.ndarray]], str]] = []
        if gazetteer is not None and category in GAZETTEER_CATEGORIES:
            gaz_clusters, leftover_indices = _gazetteer_clusters(category_terms, vectors, gazetteer)
            print(
                f"[03_cluster_taxonomy] {category} : {len(gaz_clusters)} noms canoniques résolus par le "
                f"wiki, {len(leftover_indices)} termes en repli embedding."
            )
            category_terms = [category_terms[i] for i in leftover_indices]
            vectors = vectors[leftover_indices] if leftover_indices else vectors[:0]

        if category == "perso":
            clusters_with_anchor, method = _anchor_clusters(category_terms, vectors, args)
        else:
            clusters, method = _cluster_category(category_terms, vectors, args)
            clusters_with_anchor = [(c, None) for c in clusters]

        clusters_with_anchor = list(gaz_clusters) + clusters_with_anchor
        if gaz_clusters:
            method = f"gazetteer+{method}"

        n_clusters = len(clusters_with_anchor)
        print(f"[03_cluster_taxonomy] {category} : {total_terms} termes, {n_clusters} clusters ({method}).")

        taxonomy[category] = {}
        taxonomy_noise[category] = {}
        for cluster, forced_canonical in clusters_with_anchor:
            total_freq = sum(term["count"] for term, _ in cluster)
            canonical, variants = _canonical_and_variants(cluster, forced_canonical)
            # Une ancre front-matter est une source fiable à 100 % : jamais reléguée au bruit,
            # même vue une seule fois dans le corpus.
            is_noise = total_freq <= 1 and forced_canonical is None
            target = taxonomy_noise if is_noise else taxonomy
            target[category][canonical] = variants

    (args.output_dir / "taxonomy.json").write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "taxonomy_noise.json").write_text(
        json.dumps(taxonomy_noise, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    n_labels = sum(len(v) for v in taxonomy.values())
    n_noise = sum(len(v) for v in taxonomy_noise.values())
    print(f"[03_cluster_taxonomy] terminé : {n_labels} labels retenus, {n_noise} exclus comme bruit.")


if __name__ == "__main__":
    main()

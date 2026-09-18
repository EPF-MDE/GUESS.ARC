#!/usr/bin/env python3
"""Étape 1 — extraction des candidats de tags depuis data/silver/*.md.

Parcourt tous les résumés silver, extrait des candidats de tags typés
(perso, lieu, objet, event, rel) via spaCy (anglais, le corpus est en
anglais — cf. faisabilite-etat-de-lart.md) ou, à défaut, via l'extracteur
regex de repli (voir taxonomy/extraction.py).

En plus du texte libre (résumés + notes factuelles), on exploite le
front-matter YAML de chaque chapitre : la liste de personnages qu'il
contient est une source "perso" fiable à 100 %, gratuite, qui vient
compléter (et non remplacer) la détection par NER.

Le front-matter sert aussi à vérifier deux types de relations ("rel") entre
personnages, en plus (pas à la place) de la détection par mot-clé de
proximité de taxonomy/extraction.py (REL_LEXICON) : celle-ci reste
nécessaire pour taguer un texte libre sans front-matter (04_tag_text.py) et
pour les relations sans source structurée (alliance, rivalité, amitié,
trahison, mariage, mentorat) :
  - camaraderie : deux personnages du même chapitre qui partagent le même
    `faction` de front-matter (même équipage) ;
  - filiation : deux personnages qui partagent la même catégorie de famille
    du wiki Fandom (ex. "Category:Shimotsuki Family" pour Zoro), interrogée
    et mise en cache comme le reste du gazetteer (cf. taxonomy/gazetteer.py).
Ces paires vérifiées viennent s'ajouter à celles que la détection par
mot-clé aura pu trouver dans le texte libre du même chapitre : les deux
sources alimentent le même tag canonique, sans conflit.

Usage :
    python 01_extract_candidates.py [--input-dir data/silver] [--output output/candidates.csv]
"""

from __future__ import annotations

import argparse
import csv
from itertools import combinations
from pathlib import Path

from taxonomy.console import ensure_utf8_stdout
from taxonomy.extraction import PersonLookup, extract_candidates, load_nlp
from taxonomy.gazetteer import WikiGazetteer
from taxonomy.md_parser import iter_chapters

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=BASE_DIR / "data" / "silver")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "output" / "candidates.csv")
    parser.add_argument(
        "--gazetteer-cache",
        type=Path,
        default=BASE_DIR / "output" / "gazetteer_wiki_cache.json",
        help="Cache disque des résolutions wiki, partagé avec 03_cluster_taxonomy.py.",
    )
    parser.add_argument(
        "--no-gazetteer",
        action="store_true",
        help="Désactive la vérification de filiation par famille wiki (camaraderie par front-matter reste active).",
    )
    return parser


def _family_by_name(chapters: list, gazetteer: WikiGazetteer | None) -> dict[str, str | None]:
    """{nom de personnage: catégorie de famille wiki, ou None} pour tout le front-matter.

    Une seule requête groupée (avec cache disque) pour tous les personnages du
    corpus, plutôt qu'une requête par chapitre.
    """
    if gazetteer is None:
        return {}
    names = sorted({c["name"] for ch in chapters for c in ch.characters if c.get("name")})
    resolved = gazetteer.resolve_many(names)
    return {name: r.family for name, r in resolved.items()}


def _relation_rows(chapter, family_by_name: dict[str, str | None]) -> list[tuple[str, str, str]]:
    """Lignes "rel" vérifiées (filiation, camaraderie) pour les paires de personnages du chapitre."""
    rows = []
    names = [(c.get("name"), c.get("faction")) for c in chapter.characters if c.get("name")]
    for (name_a, faction_a), (name_b, faction_b) in combinations(names, 2):
        family_a = family_by_name.get(name_a)
        if family_a and family_a == family_by_name.get(name_b):
            rows.append(("filiation", f"{name_a} & {name_b} ({family_a})"))
        if faction_a and faction_a == faction_b:
            rows.append(("camaraderie", f"{name_a} & {name_b} ({faction_a})"))
    return rows


def main() -> None:
    args = build_arg_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    nlp, mode = load_nlp()
    print(f"[01_extract_candidates] mode d'extraction : {mode}")

    chapters = list(iter_chapters(args.input_dir))
    gazetteer = None if args.no_gazetteer else WikiGazetteer(args.gazetteer_cache)
    family_by_name = _family_by_name(chapters, gazetteer)
    if gazetteer is not None:
        n_families = len({f for f in family_by_name.values() if f})
        print(f"[01_extract_candidates] {n_families} familles wiki résolues pour {len(family_by_name)} personnages.")

    n_chapters = 0
    n_rows = 0
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["chapter_id", "category_guess", "raw_term", "context_snippet"])

        for chapter in chapters:
            n_chapters += 1

            # Source 1 : liste de personnages du front-matter (fiable à 100 %).
            for character in chapter.characters:
                name = character.get("name")
                if not name:
                    continue
                faction = character.get("faction", "")
                writer.writerow([chapter.chapter_id, "perso", name, f"frontmatter:{faction}"])
                n_rows += 1

            # Source 2 : annotations de Chapter Notes (ex. "Gold Roger (flashback)")
            # -> un flashback impliquant ce personnage est un événement narratif.
            for name, annotation in chapter.character_annotations:
                if annotation.lower() == "flashback":
                    writer.writerow(
                        [chapter.chapter_id, "event", "flashback", f"{name} (flashback)"]
                    )
                    n_rows += 1

            # Source 3 : extraction NLP sur le texte libre (résumés + notes factuelles).
            # `persons` corrige les entités "lieu" qui sont en fait des personnages
            # du chapitre mal étiquetés par spaCy (cf. PersonLookup) : ex. "Zoro"
            # étiqueté GPE/LOC par en_core_web_sm alors que "Roronoa Zoro" est
            # présent dans le front-matter.
            persons = PersonLookup({c["name"] for c in chapter.characters if c.get("name")})
            for cand in extract_candidates(chapter.full_text, nlp=nlp, persons=persons):
                writer.writerow(
                    [chapter.chapter_id, cand.category_guess, cand.raw_term, cand.context_snippet]
                )
                n_rows += 1

            # Source 4 : relations vérifiées (filiation par famille wiki, camaraderie
            # par équipage de front-matter) entre chaque paire de personnages du
            # chapitre -- vient s'ajouter aux relations trouvées par mot-clé dans
            # la Source 3, pas les remplacer (cf. docstring du module).
            for tag, context in _relation_rows(chapter, family_by_name):
                writer.writerow([chapter.chapter_id, "rel", tag, context])
                n_rows += 1

            if n_chapters % 100 == 0:
                print(f"[01_extract_candidates] {n_chapters} chapitres traités...")

    print(f"[01_extract_candidates] terminé : {n_chapters} chapitres, {n_rows} candidats -> {args.output}")


if __name__ == "__main__":
    main()

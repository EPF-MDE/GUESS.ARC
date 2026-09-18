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

Usage :
    python 01_extract_candidates.py [--input-dir data/silver] [--output output/candidates.csv]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from taxonomy.console import ensure_utf8_stdout
from taxonomy.extraction import extract_candidates, load_nlp
from taxonomy.md_parser import iter_chapters

ensure_utf8_stdout()
BASE_DIR = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=BASE_DIR / "data" / "silver")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "output" / "candidates.csv")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    nlp, mode = load_nlp()
    print(f"[01_extract_candidates] mode d'extraction : {mode}")

    n_chapters = 0
    n_rows = 0
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["chapter_id", "category_guess", "raw_term", "context_snippet"])

        for chapter in iter_chapters(args.input_dir):
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
            for cand in extract_candidates(chapter.full_text, nlp=nlp):
                writer.writerow(
                    [chapter.chapter_id, cand.category_guess, cand.raw_term, cand.context_snippet]
                )
                n_rows += 1

            if n_chapters % 100 == 0:
                print(f"[01_extract_candidates] {n_chapters} chapitres traités...")

    print(f"[01_extract_candidates] terminé : {n_chapters} chapitres, {n_rows} candidats -> {args.output}")


if __name__ == "__main__":
    main()

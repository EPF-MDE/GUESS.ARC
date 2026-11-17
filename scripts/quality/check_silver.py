"""Vérifie que le corpus silver est une entrée saine pour l'Embedding Gold (QUALITY.md, REQ-5 à REQ-8).

Lit chaque fichier avec `read_chapter`, le lecteur silver de l'ingestion
(paquet guess_arc installé : pip install -r requirements.txt). Sans réseau.
Code de sortie 0 si tout passe, 1 sinon.

    python scripts/quality/check_silver.py [--silver data/silver] [--expected 1193]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from guess_arc.ingestion.silver import read_chapter

# Ancré sur la racine du repo (comme guess_arc.paths), pas sur le dossier courant :
# le script donne le même résultat d'où qu'on le lance.
DEFAULT_SILVER = Path(__file__).resolve().parents[2] / "data" / "silver"

FILE_NAME = re.compile(r"chapter_(\d{4})\.md")


def check_file(path: Path, number: int) -> tuple[list[str], int | None]:
    """Renvoie les problèmes du fichier et le nombre de mots de son Long Summary
    (None si le fichier est illisible : front-matter, champ ou section manquant)."""
    try:
        chapter = read_chapter(path)
    except ValueError as exc:
        return [str(exc).removeprefix(f"{path.name} : ")], None

    problems: list[str] = []
    if chapter.number != number:
        problems.append(f"champ chapter={chapter.number} ≠ nom de fichier")
    if not chapter.complete:
        problems.append("complete n'est pas true")
    if chapter.character_count != len(chapter.characters):
        problems.append(f"character_count={chapter.character_count} mais {len(chapter.characters)} personnages listés")
    words = len(chapter.long_summary.split())
    if words == 0:
        problems.append("Long Summary vide")
    return problems, words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER,
                        help="dossier silver (défaut : data/silver à la racine du repo)")
    parser.add_argument("--expected", type=int, default=1193)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    files = sorted(args.silver.glob("chapter_*.md"))
    numbers = [int(FILE_NAME.fullmatch(f.name).group(1)) for f in files]
    missing = sorted(set(range(1, args.expected + 1)) - set(numbers))

    failures: dict[str, list[str]] = {}
    word_counts: list[int] = []
    for path, number in zip(files, numbers):
        problems, words = check_file(path, number)
        if words is not None:
            word_counts.append(words)
        if problems:
            failures[path.name] = problems

    print(f"Fichiers silver           : {len(files)} (attendu {args.expected})")
    print(f"Chapitres manquants       : {missing or 'aucun'}")
    print(f"Fichiers en échec         : {len(failures)}")
    if word_counts:
        ordered = sorted(word_counts)
        print(
            "Mots du Long Summary      : "
            f"min {ordered[0]}, médiane {ordered[len(ordered) // 2]}, max {ordered[-1]}"
        )
    for name, problems in failures.items():
        print(f"  {name}: {'; '.join(problems)}")

    ok = len(files) == args.expected and not missing and not failures
    print("RÉSULTAT                  :", "OK" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

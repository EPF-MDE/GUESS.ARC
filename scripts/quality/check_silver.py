"""Vérifie que le corpus silver est une entrée saine pour l'Embedding Gold (QUALITY.md, REQ-5 à REQ-8).

Bibliothèque standard uniquement, sans réseau. Code de sortie 0 si tout passe, 1 sinon.

    python scripts/quality/check_silver.py [--silver data/silver] [--expected 1193]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SECTION = re.compile(r"^## (.+)$", re.MULTILINE)
FILE_NAME = re.compile(r"chapter_(\d{4})\.md")


def split_front_matter(text: str) -> tuple[str, str]:
    """Sépare le front-matter YAML (entre les deux `---`) du corps Markdown."""
    if not text.startswith("---"):
        raise ValueError("pas de front-matter")
    _, header, body = text.split("---", 2)
    return header, body


def scalar(header: str, key: str) -> str | None:
    match = re.search(rf"^{key}: (.+)$", header, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def sections(body: str) -> dict[str, str]:
    """Associe chaque titre `## ...` au texte qui le suit jusqu'au titre suivant."""
    parts = SECTION.split(body)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def check_file(path: Path, number: int) -> tuple[list[str], int]:
    """Renvoie les problèmes du fichier et le nombre de mots de son Long Summary."""
    problems: list[str] = []
    header, body = split_front_matter(path.read_text(encoding="utf-8"))

    if scalar(header, "chapter") != str(number):
        problems.append(f"champ chapter={scalar(header, 'chapter')} ≠ nom de fichier")
    if scalar(header, "complete") != "true":
        problems.append("complete n'est pas true")
    if not scalar(header, "revision_id"):
        problems.append("revision_id manquant")

    declared = scalar(header, "character_count")
    listed = len(re.findall(r"^  - name: ", header, re.MULTILINE))
    if declared is None or int(declared) != listed:
        problems.append(f"character_count={declared} mais {listed} personnages listés")

    found = sections(body)
    for name in ("Short Summary", "Long Summary", "Chapter Notes"):
        if name not in found:
            problems.append(f"section « {name} » absente")
    words = len(found.get("Long Summary", "").split())
    if words == 0:
        problems.append("Long Summary vide")
    return problems, words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver", type=Path, default=Path("data/silver"))
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

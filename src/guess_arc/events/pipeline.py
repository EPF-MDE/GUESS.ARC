"""
One Piece — extraction des événements, de la silver vers data/event/.

Pour l'instant, seul le préparsing est livré : `--dry-run` écrit, pour chaque
chapitre, data/event/in/events_NNNN.md (le prompt utilisateur exact), sans
appeler le modèle.

Usage :
    python -m guess_arc.events --dry-run                       # tous les chapitres
    python -m guess_arc.events --dry-run --from 90 --to 100    # une plage
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from guess_arc import paths

from .inputs import write_input
from .preparse import preparse
from .silver import read_chapter

SILVER_NAME_RE = re.compile(r"^chapter_(\d+)\.md$")


def silver_chapters(silver_dir: Path, first: int | None, last: int | None) -> list[Path]:
    """Fichiers silver de la plage [first, last], dans l'ordre des chapitres."""
    selected = []
    for path in silver_dir.glob("chapter_*.md"):
        match = SILVER_NAME_RE.match(path.name)
        if not match:
            continue
        num = int(match.group(1))
        if (first is None or num >= first) and (last is None or num <= last):
            selected.append((num, path))
    return [path for _, path in sorted(selected)]


def run(data_dir: Path = paths.DATA_DIR, first: int | None = None,
        last: int | None = None, dry_run: bool = False) -> int:
    if not dry_run:
        raise NotImplementedError("extraction llm pas encore disponible : utiliser --dry-run")
    in_dir = paths.event_in_dir(data_dir)
    files = silver_chapters(paths.silver_dir(data_dir), first, last)
    removed = {}
    for path in files:
        p = preparse(read_chapter(path))
        write_input(p, in_dir)
        for name, count in p.flags.items():
            removed[name] = removed.get(name, 0) + count
    print(f"Entrées : {in_dir}/ ({len(files)} fichiers écrits)")
    for name, count in removed.items():
        print(f"  {name} : {count}")
    return len(files)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=paths.DATA_DIR,
                   help="racine des couches silver/event (défaut : data/ à la racine du repo)")
    p.add_argument("--dry-run", action="store_true",
                   help="écrit les fichiers d'entrée sans appeler le modèle")
    p.add_argument("--from", dest="first", type=int, default=None,
                   help="premier chapitre traité (défaut : le premier de la silver)")
    p.add_argument("--to", dest="last", type=int, default=None,
                   help="dernier chapitre traité (défaut : le dernier de la silver)")
    args = p.parse_args(argv)
    if not args.dry_run:
        p.error("l'extraction llm n'est pas encore disponible : utiliser --dry-run")
    run(args.data_dir, args.first, args.last, dry_run=True)


if __name__ == "__main__":
    main()

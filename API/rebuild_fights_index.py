#!/usr/bin/env python3
"""Rebuild fights_index.json from already-tagged chapters (issue #11 gap).

update_fights_index_file() (fights_index.py) only updates the index as
tag_chapter *writes* a new chapter_NNNN.json — a chapter tagged before the
Fights Index existed (or one copied/regenerated out of band) never
retroactively populates it. This script closes that gap: it rebuilds the
index from scratch by scanning every chapter_NNNN.json already present in a
taxonomy directory, in chapter order, reusing the exact same pure merge
logic (`update_index_with_chapter`) tag_chapter uses live — so a rebuilt
index is identical in shape/content to one built incrementally.

Scoped to one directory at a time, non-recursive: with the benchmark's
per-model layout (data/taxonomy/<provider>/chapter_NNNN.json), each model
has its own fight_id continuity and its own fights_index.json — run this
once per model directory to rebuild each independently, never merge them.

Usage:
    python API/rebuild_fights_index.py                       # data/taxonomy/
    python API/rebuild_fights_index.py --taxonomy-dir data/taxonomy/gemini
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fights_index import save_fights_index, update_index_with_chapter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY_DIR = REPO_ROOT / "data" / "taxonomy"
CHAPTER_FILE_RE = re.compile(r"^chapter_(\d+)\.json$")


def rebuild_index(taxonomy_dir: Path) -> dict:
    """Fresh index built from every chapter_NNNN.json directly under
    `taxonomy_dir` (not recursive — a per-model subdirectory is a separate
    corpus), processed in ascending chapter-number order so `chapters`/
    `resolved`/`winner` end up exactly as an incremental run would have left
    them (merge_fight_interaction is order-independent regardless, but
    ascending order keeps `label`/history easiest to eyeball)."""
    chapter_files = sorted(
        ((int(match.group(1)), path) for path in taxonomy_dir.glob("chapter_*.json")
         if (match := CHAPTER_FILE_RE.match(path.name))),
        key=lambda pair: pair[0],
    )
    index: dict = {}
    for number, path in chapter_files:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        update_index_with_chapter(index, number, envelope)
    return index


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--taxonomy-dir", type=Path, default=DEFAULT_TAXONOMY_DIR,
        help="directory holding chapter_NNNN.json files to scan (default: %(default)s)",
    )
    p.add_argument(
        "--out", type=Path, default=None,
        help="output path for fights_index.json (default: <taxonomy-dir>/fights_index.json)",
    )
    args = p.parse_args()

    out_path = args.out or (args.taxonomy_dir / "fights_index.json")
    index = rebuild_index(args.taxonomy_dir)
    save_fights_index(index, path=out_path)
    fight_count = len(index)
    chapter_count = sum(len(entry["chapters"]) for entry in index.values())
    print(f"rebuilt {out_path}: {fight_count} fight(s) across {chapter_count} chapter-fight record(s)")


if __name__ == "__main__":
    main()

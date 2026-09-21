"""Fights Index maintenance (issue #11) — keeps data/taxonomy/fights_index.json
in sync as data/taxonomy/chapter_NNNN.json files are (re-)written.

A Fight (ADR 0004) commonly spans many consecutive chapters (30+ runs of 3-7+
chapters were found in the existing corpus). Without this index, each
chapter's `interactions[]` segment for that Fight is a disconnected record —
this module is what lets every segment sharing a `fight_id` be reconstructed
as one entity (ADR 0006).

`merge_fight_interaction`/`update_index_with_chapter` are pure (no filesystem
or network access), mirroring the taxonomy_core.py split, so they can be unit
tested directly. `load_fights_index`/`save_fights_index` handle the JSON file
on disk and are called from taxonomy_client.tag_chapter right after a chapter
file with at least one `type: fight` interaction is written.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGHTS_INDEX_PATH = REPO_ROOT / "data" / "taxonomy" / "fights_index.json"


def load_fights_index(path: Path = FIGHTS_INDEX_PATH) -> dict[str, Any]:
    """Empty index if the file doesn't exist yet — the first chapter with a
    fight interaction creates it, it isn't a prerequisite."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_fights_index(index: dict[str, Any], path: Path = FIGHTS_INDEX_PATH) -> None:
    """Write via a temp file + atomic rename so a run interrupted mid-write
    (batch tagging is long-running and gets killed/crashes — issue #11 AC:
    resuming after a cut must not corrupt the index) can never leave a
    truncated fights_index.json for the next load_fights_index() to choke on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise


def _humanize(participant_id: str) -> str:
    """`character_id`/`faction_id` are wiki slugs (ADR 0003, e.g.
    `monkey-d-luffy`); the Character Registry that would resolve them to a
    canonical display name is deliberately unpopulated for now (issue #2 /
    docs/taxonomy-schema.md section 3), so the label is derived straight from
    the slug rather than depending on it."""
    return " ".join(word.capitalize() for word in participant_id.split("-"))


def _label_for_sides(sides: list[list[str]]) -> str:
    return " vs. ".join(", ".join(_humanize(p) for p in side) for side in sides)


def _merge_sides(existing_sides: list[list[str]], new_sides: list[list[str]]) -> list[list[str]]:
    """Merge side-by-side (index 0 with index 0, etc.) — the same ongoing
    Fight is assumed to keep the same side partition across chapters, only
    gaining participants as they're introduced. Each side is deduplicated and
    sorted so the result is identical no matter which chapter of the Fight is
    merged in first (issue #11 AC: out-of-order/resumed processing must not
    corrupt the index)."""
    merged = [list(side) for side in existing_sides]
    for i, side in enumerate(new_sides):
        if i < len(merged):
            merged[i] = sorted(set(merged[i]) | set(side))
        else:
            merged.append(sorted(set(side)))
    return merged


def merge_fight_interaction(index: dict[str, Any], chapter_number: int, interaction: dict) -> dict[str, Any]:
    """Merge one `type: fight` interaction from a chapter into `index` in
    place. Returns `index` for convenient chaining.

    Order-independent by construction:
    - `chapters` is a deduplicated, sorted union — reprocessing the same
      chapter, or processing a Fight's chapters out of chronological order,
      never duplicates or drops a chapter already recorded.
    - `resolved` only ever flips False -> True, never back: a chapter
      processed later that doesn't itself end the Fight can't un-resolve an
      already-resolved entry.
    - `sides` merge additively and are re-sorted (see `_merge_sides`).
    """
    fight_id = interaction["fight_id"]
    sides = interaction["battle"]["sides"]
    ends_this_chapter = bool(interaction.get("ends_this_chapter"))
    winner = interaction.get("winner")

    entry = index.get(fight_id)
    if entry is None:
        entry = {
            "label": _label_for_sides(sides),
            "chapters": [chapter_number],
            "sides": [sorted(set(side)) for side in sides],
            "resolved": False,
            "winner": None,
        }
        index[fight_id] = entry
    else:
        if chapter_number not in entry["chapters"]:
            entry["chapters"].append(chapter_number)
            entry["chapters"].sort()
        entry["sides"] = _merge_sides(entry["sides"], sides)
        entry["label"] = _label_for_sides(entry["sides"])

    if ends_this_chapter:
        entry["resolved"] = True
        entry["winner"] = winner

    return index


def update_index_with_chapter(index: dict[str, Any], chapter_number: int, envelope: dict) -> dict[str, Any]:
    """Merge every `type: fight` interaction of one chapter envelope into
    `index` in place. Returns `index` for convenient chaining. A no-op if the
    chapter has no fight interaction."""
    for interaction in envelope.get("interactions", []):
        if interaction.get("type") == "fight":
            merge_fight_interaction(index, chapter_number, interaction)
    return index


def update_fights_index_file(chapter_number: int, envelope: dict, path: Path = FIGHTS_INDEX_PATH) -> None:
    """Load, merge one chapter in, and save back — what taxonomy_client.tag_chapter
    calls right after writing data/taxonomy/chapter_NNNN.json."""
    index = load_fights_index(path)
    update_index_with_chapter(index, chapter_number, envelope)
    save_fights_index(index, path)

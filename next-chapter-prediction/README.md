# One Piece Next-Chapter Forecasting

See `CLAUDE.md` for project principles and `SPEC.md` for the full research
specification.

## Setup

```bash
pip install -e ".[dev]"
```

## Obtaining the silver corpus

This project reads chapters from `onepiece-faisabilite/data/silver/`, a
sibling directory produced by the separate `onepiece-faisabilite/` ingestion
pipeline (SPEC §4). That directory is **not checked into git** — the root
`.gitignore` excludes `onepiece-faisabilite/data/` — so a fresh clone does
not have it. Generate it locally before running anything that reads the
dataset (`configs/dataset/silver.yaml`, or tests that depend on it):

```bash
cd ../onepiece-faisabilite
pip install requests pyyaml cloudscraper
python scripts/onepiece_ingest.py --max-chapter 1193
```

This fetches chapter summaries from the English One Piece Fandom wiki via
the MediaWiki API (CC BY-SA, academic use with attribution) and writes:

- `data/bronze/chapters.jsonl` — raw wikitext archive.
- `data/silver/chapter_NNNN.md` — one Markdown file per chapter, the format
  `configs/dataset/silver.yaml` expects.

A full run fetches 1193 chapters and is rate-limited (`--delay`, default
0.5s between requests), so expect it to take a while. Tests that need the
corpus (e.g. `tests/test_dataset_config.py`'s `resolved_path` check) skip
themselves with a clear message if it hasn't been generated yet.

## Running tests

```bash
pytest
```

Run from this directory (`next-chapter-prediction/`) — dataset and output
paths in the committed configs are relative to it.

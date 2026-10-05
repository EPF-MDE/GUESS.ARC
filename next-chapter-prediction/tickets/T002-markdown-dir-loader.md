# T002 - `markdown_dir` loader for silver chapter files

## Objective

Implement and register a `markdown_dir` loader (`ncp.data.loaders.markdown`)
that reads every `chapter_NNNN.md` file, parses its YAML front-matter and its
Markdown body (`Short Summary`, `Long Summary`, `Chapter Notes` bullets, the
trailing plain-text character list), and yields one `RawRecord` dict per
chapter for `RecordMapper` to convert into a `ChapterRecord`.

## Context

SPEC §4 and §7 describe this exact file format and name `markdown_dir` as
"the intended source for the markdown_dir loader, with YAML front-matter
fields mapped into `ChapterRecord.metadata`." No such loader exists yet —
`src/ncp/data/loaders/` currently only has `text.py` (jsonl/json) and
`tabular.py` (csv/parquet); this is the first ticket that lets any real
chapter text enter the pipeline.

## Scope

- Register a loader under the name `markdown_dir` via
  `register_loader("markdown_dir", extensions=(".md",), directory=True, ...)`
  in a new `src/ncp/data/loaders/markdown.py`, following the existing
  `LoaderSpec`/`Loader` contract in `loaders/base.py`.
- Parse the YAML front-matter block (delimited by `---` lines) with
  `yaml.safe_load`.
- Parse the Markdown body into: `short_summary` (str), `long_summary` (str,
  becomes the `summary` field via `field_map.summary`), `chapter_notes`
  (`list[str]`, one entry per bullet), and `characters` (parsed from the
  trailing plain-text list into `[{name, faction, on_panel, cover,
  flashback}]`, distinct from the front-matter `characters` table — keep
  both, namespaced, since SPEC §4 notes they encode different information).
- Surface `jname` as-is (including the corrupted `"{{Ruby"` cases, SPEC §4)
  — do not attempt to repair it in this ticket.
- Raise `LoaderError` with the file path on any file missing the front-matter
  delimiter or the `Long Summary` section.

## Non-goals

- Do not resolve the cover/flashback granularity decision (SPEC §26) —
  parse and preserve both signals in the output; T005/T031 decide how they
  are used downstream.
- Do not validate corpus-level invariants (contiguity, no duplicates) — that
  is T003.
- Do not attempt to repair `jname` corruption — just pass it through.

## Inputs

- `onepiece-faisabilite/data/silver/chapter_NNNN.md` (1193 files).
- T001's `configs/dataset/local.yaml`.
- `src/ncp/data/loaders/base.py` (`register_loader`, `LoaderSpec`).

## Outputs

- `src/ncp/data/loaders/markdown.py`
- Updated `src/ncp/data/loaders/__init__.py` import so the loader registers
  on package import (matching the existing pattern for `text`/`tabular`).

## Acceptance criteria

- Running the loader over the real silver directory via T001's config
  yields exactly 1193 `RawRecord`s.
- Every yielded record has non-empty `long_summary` and a `chapter` number
  matching the filename's `NNNN`.
- A record whose body is missing `Long Summary` raises `LoaderError` naming
  the file, rather than silently yielding an empty summary.

## Tests

- Unit tests against 3-5 fixture `.md` files (one normal, one with corrupted
  `jname`, one with a flashback-annotated character, one deliberately
  malformed) stored under `tests/fixtures/silver_sample/`.
- A test asserting `chapter_notes` is a list, not a single blob string.
- A test asserting the loader is reachable via `detect_format`/`get_loader`
  under the name `markdown_dir`.

## Dependencies

T001 (dataset config declares the path/format this loader reads).

## Risks

- **Temporal:** none directly — this loader reads only chapter t's own file
  per record; it does not look at other chapters. The real temporal-causality
  work starts once records are grouped/split (T005+). Noted here only
  because SPEC §23 flags retrospective wiki edits as a labeling-integrity
  risk inherited from this raw source — out of scope to fix in this ticket,
  but the loader must not mask it (e.g. must not silently overwrite
  `revised_at`).

## Definition of done

- [ ] `markdown_dir` loader registered and importable.
- [ ] Full silver directory loads to exactly 1193 records with no
      `LoaderError`.
- [ ] Fixture-based unit tests pass, including the malformed-file negative
      test.
- [ ] `ncp inspect` (existing CLI, if present) or an equivalent smoke script
      runs against T001's config and prints a sane field-map report.

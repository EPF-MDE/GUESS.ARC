# T003 - Dataset integrity validation command

## Objective

Implement a validation routine (and a thin CLI/entry point to run it) that
checks the loaded corpus against the invariants SPEC §4 claims are already
verified, and fails loudly if a future data refresh breaks them.

## Context

SPEC §4 states, as already-verified facts: "1193 chapters, numbered 1–1193,
contiguous, no missing chapters, no duplicate chapters" and "every inspected
chapter has `arc`, `complete: true`, and a non-empty `Long Summary`." Every
later ticket (splits, extraction, state) assumes these hold. This ticket is
the gate that turns "assumed to hold" into "mechanically checked," per the
project rule "Dataset validation must happen before modeling."

## Scope

- `ncp.data.validation.validate_corpus(corpus: Corpus) -> ValidationReport`
  checking: contiguous `index` range per book with no gaps/duplicates (using
  `Book.indices`); every `ChapterRecord` has non-empty `summary`; every
  record's `metadata` has `arc` set and `complete is True`; a count and list
  of chapters with corrupted `jname` (`"{{Ruby"` literal) reported as a
  **warning**, not a failure, matching SPEC §4's framing that this does not
  affect `Long Summary`/`Chapter Notes`.
- `ValidationReport` is a dataclass with `errors: list[str]`,
  `warnings: list[str]`, `ok: bool` (`True` iff `errors` is empty).
- A CLI command (e.g. `ncp validate --config ...`) that loads the corpus via
  T002's loader, runs the check, prints the report, and exits non-zero on
  any error.

## Non-goals

- Do not attempt to repair any violation found (missing chapter, corrupted
  field) — report it and stop; repair is a data-pipeline decision outside
  this project's scope (SPEC §4: `onepiece-faisabilite/` is "not part of
  this project's codebase").
- Do not validate event/entity/state correctness — only the raw corpus
  shape. Taxonomy/label validation is T014/T040.

## Inputs

- T002's loader output (a `Corpus` of one `Book` with 1193 chapters).
- `src/ncp/data/schema.py` (`Corpus`, `Book`, `ChapterRecord`).

## Outputs

- `src/ncp/data/validation.py` (`ValidationReport`, `validate_corpus`).
- CLI wiring (new or extended subcommand).

## Acceptance criteria

- Running validation against the real silver corpus (via T001+T002) returns
  `ok=True` with zero errors and a `jname`-corruption warning count equal to
  the number SPEC §4 reports is wrong today (the ticket must re-measure this
  number against the live data, not hard-code "195").
- A synthetic corpus missing chapter 500 produces exactly one error naming
  the gap.
- A synthetic corpus with two records at the same index produces exactly
  one error naming the duplicate.
- A synthetic corpus with an empty `summary` produces an error naming the
  chapter.

## Tests

- Unit tests for each of the four synthetic-corpus cases above.
- An integration test running validation against the real corpus (marked
  slow/integration if the project has such a marker) asserting `ok=True`.

## Dependencies

T002 (needs loaded records to validate).

## Risks

- **Temporal causality:** none — this check is corpus-wide and
  split-agnostic by design (it runs before any split exists). It must not
  be confused with a leakage check: confirming "chapter 500 exists" is not
  the same as "chapter 500's data is usable as a feature for predicting
  chapter 499" — that distinction belongs to T005/T007, not here.

## Definition of done

- [ ] `validate_corpus` implemented with the four checks above.
- [ ] CLI command runs against the real corpus and reports `ok=True`.
- [ ] All four synthetic-case unit tests pass.
- [ ] The report's `jname`-corruption count is logged, not asserted to equal
      a hard-coded historical number (data may have been fixed/changed since
      SPEC.md was written).

# T009 - Layer 1 raw-notes accessor & integrity report

## Objective

Provide a typed accessor for Layer 1 ("Raw Chapter Notes") that wraps the
bullet list T002 already parsed into `ChapterRecord.metadata`, plus a report
on notes coverage/length across the corpus, without treating the notes as
validated annotations.

## Context

SPEC §10, Layer 1: "Contains: editorial bullet points as stored in silver
`.md`... Classification: **raw material** — not a feature or target
directly... No layer below Layer 1 is assumed to already be ground truth."
This ticket exists purely to give Layer 2 (T010) a stable, typed entry point
and to surface data-quality facts about the raw notes (e.g. chapters with
zero or unusually short notes) before extraction logic is built on top of
them.

## Scope

- `ncp.annotations.layer1.RawNotes`: a thin wrapper
  (`chapter_index`, `bullets: tuple[str, ...]`, `source_chapter_id`) over
  `ChapterRecord.metadata["chapter_notes"]` (produced by T002).
- `ncp.annotations.layer1.iter_raw_notes(corpus: Corpus) -> Iterator[RawNotes]`.
- `ncp.annotations.layer1.notes_coverage_report(corpus: Corpus) -> dict`:
  counts of chapters with zero bullets, bullet-count distribution
  (min/median/max), to flag outliers for later manual spot-checking (T011).

## Non-goals

- Do not interpret, classify, or extract structured events from the notes
  — that is Layer 2 (T010).
- Do not attempt to detect retrospective/hindsight editing (SPEC §23, §26)
  — only report raw coverage statistics.

## Inputs

- T002 (loader output with `chapter_notes` populated).

## Outputs

- `src/ncp/annotations/layer1.py`

## Acceptance criteria

- `iter_raw_notes` yields exactly one `RawNotes` per chapter in the corpus,
  in chapter order.
- `notes_coverage_report` correctly counts zero-bullet chapters against a
  hand-checked sample.

## Tests

- Unit test on a small fixture corpus with known bullet counts, asserting
  the report's numbers match a hand computation.
- Test that `RawNotes` is read-only (frozen dataclass) — Layer 1 must never
  be mutated in place by later layers.

## Dependencies

T002.

## Risks

- **Temporal causality:** none directly (this is a per-chapter accessor
  with no cross-chapter aggregation). The relevant SPEC risk is integrity,
  not leakage: §23's "retrospective wiki annotations" risk applies to this
  raw material and is inherited by every layer built on top of it; this
  ticket's report is the first place that risk becomes visible as data
  (e.g. unusually detailed notes on a chapter might warrant future
  scrutiny), though no corrective action is in scope here.

## Definition of done

- [ ] `layer1.py` implemented with both functions.
- [ ] Coverage report run once against the full real corpus and its output
      reviewed (not just unit-tested) for any chapter with zero notes.

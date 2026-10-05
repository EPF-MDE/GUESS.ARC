# T011 - Layer 2 extraction quality spot-check tooling

## Objective

Build a lightweight sampling/scoring tool that measures Layer 2 extraction
precision/recall against a small hand-labeled chapter subset, so the
project has a concrete, re-runnable number for the "imperfect event labels"
risk named in SPEC §23.

## Context

SPEC §23: "Imperfect event labels — extraction (§10 Layer 2)
precision/recall errors set a ceiling independent of model quality." SPEC
§10 states extraction is "not yet validated" at the schema level. Without
this ticket, the project would have no evidence for how good/bad Layer 2 is
before building Layer 3/4 on top of it, violating the general principle
"No fabricated experiment results" (`CLAUDE.md`) applied to an implicit
claim of extraction quality.

## Scope

- A fixed, versioned hand-labeled sample: 20-30 chapters (drawn **only**
  from the designated construction set / train split once T005 exists —
  coordinate ordering with T012 so this sample never includes test-split
  chapters) with manually annotated expected event candidates (participants,
  rough type, evidence sentence).
- `ncp.annotations.layer2_eval.score_candidates(predicted, gold) -> dict`
  computing simple set-overlap precision/recall over
  (event trigger, participant set) tuples — approximate matching is
  acceptable and should be documented (exact-match event extraction scoring
  is itself an open research problem; this is a sanity instrument, not a
  publishable metric).
- A CLI/script entry point that runs T010's extractor over the hand-labeled
  sample and prints the score.

## Non-goals

- Do not treat this as a formal, held-out test set for any reported
  experiment metric (§16's metrics are defined on Layer 4 event labels, not
  on Layer 2 candidate-matching) — this is a development-time diagnostic
  only.
- Do not attempt to achieve any specific precision/recall target — report
  whatever is measured; SPEC §22 explicitly allows reporting ceilings as
  findings, not failures.

## Inputs

- T010 (extractor), T005 (train-split boundary, to source the sample only
  from train chapters once available — if T005 is not yet merged when this
  ticket starts, draw the sample from the first ~80% of chapters by index
  as a provisional stand-in, and re-verify against T005's actual boundary
  once it lands).

## Outputs

- `tests/fixtures/layer2_gold/` (hand-labeled sample, versioned).
- `src/ncp/annotations/layer2_eval.py`

## Acceptance criteria

- The gold sample is drawn exclusively from chapters that are, or will be,
  inside the train split — never from val/test.
- `score_candidates` runs end-to-end against T010's live extractor and
  produces a precision/recall pair without crashing.
- The measured numbers are written to a report file, not just printed, so
  they are reviewable later without re-running.

## Tests

- Unit test for `score_candidates`'s matching logic on a tiny synthetic
  predicted/gold pair with a hand-computed expected score.
- A test asserting none of the gold sample's chapter indices fall in the
  test split once `SplitBoundaries` exists (skip/xfail gracefully if T005
  is not yet available at the time this ticket is implemented, with a
  tracked follow-up).

## Dependencies

T010.

## Risks

- **Temporal causality:** the gold sample's chapter selection must respect
  the same train/test boundary as every other construction-set-scoped
  artifact — selecting a "representative" sample without checking this
  would let a human implicitly peek at the taxonomy's eventual test set
  while hand-labeling, a subtle leakage path SPEC §23 does not name
  explicitly but which follows directly from §6/§8's general rule.

## Definition of done

- [ ] Gold sample committed, chapter list documented and confirmed
      train-only.
- [ ] `score_candidates` implemented and tested.
- [ ] A first report run against T010's extractor exists and is reviewed.

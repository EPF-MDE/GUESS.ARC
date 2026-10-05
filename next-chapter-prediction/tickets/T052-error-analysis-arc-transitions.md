# T052 - Error analysis: arc-transition breakdown

## Objective

Produce a dedicated breakdown of Tier D's (and, for comparison, Tier B's)
prediction quality at arc-transition chapters, as a diagnostic over
already-produced results.

## Context

SPEC §19: "Dedicated breakdown at arc-transition chapters (documented in
the feasibility doc as disproportionately hard: F1 drops from ~54.2% to
~37.5% at arc boundaries, affecting 32/1192 transitions)." Like T051, this
is explicitly diagnostic, not a new run.

## Scope

- `ncp.evaluation.error_analysis.arc_transition_chapters(corpus: Corpus) -> list[int]`:
  identifies chapters where the `arc` front-matter field (T002) changes
  from the previous chapter — this project's own, independently computed
  arc-transition list (not copied from the feasibility doc's number,
  which must be re-derived here against the live corpus, matching §4's
  general instruction to re-measure feasibility-doc numbers with this
  project's own code).
- `arc_transition_breakdown(predictions, gold, transitions: list[int]) -> dict`:
  computes T018's metrics separately for examples whose target chapter is
  an arc-transition chapter vs. all others.
- A report (`experiments/reports/error_arc_transitions.md`) presenting
  both groups' metrics for Tier B and Tier D, and comparing the measured
  transition count/F1 drop against the feasibility doc's cited numbers as
  context (not as ground truth to match).

## Non-goals

- Do not retrain or re-run any model.
- Do not treat the feasibility doc's 54.2%/37.5%/32-of-1192 numbers as
  targets to reproduce exactly — they were measured on the entity target
  in a different codebase; this ticket's own numbers, measured on the
  event target with this project's own pipeline, are the authoritative
  ones for this report.

## Inputs

- T044 (or T050), T002 (arc metadata), T018.

## Outputs

- Additions to `src/ncp/evaluation/error_analysis.py`,
  `experiments/reports/error_arc_transitions.md`.

## Acceptance criteria

- `arc_transition_chapters` correctly identifies every chapter where `arc`
  changes, verified against a manually spot-checked sample of the real
  corpus.
- The breakdown report presents separate, clearly labeled metrics for
  transition vs. non-transition chapters.

## Tests

- Unit test on a synthetic corpus with known arc boundaries, asserting
  correct transition-chapter detection.
- A test confirming the breakdown function only reads already-archived
  predictions, never retrains.

## Dependencies

T044, T002.

## Risks

- **Temporal causality:** none new — read-only diagnostic.
- **Arc distribution shift (§23):** this ticket directly measures the risk
  SPEC names explicitly ("known performance cliffs at arc transitions") —
  its findings feed interpretation of H1/H2/H3, not a new leakage concern.

## Definition of done

- [ ] `arc_transition_chapters`, `arc_transition_breakdown` implemented
      and tested.
- [ ] Report generated over real predictions and committed, with the
      feasibility-doc numbers cited only as context.

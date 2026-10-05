# T049 - Feature-overlap confound check (§18)

## Objective

Run the feature-overlap/correlation analysis SPEC §18 requires before
interpreting any ablation delta: quantify redundancy between text
embeddings and the derived entity/event/state features used in Tier C/D.

## Context

SPEC §18: "Required confound check before interpreting any delta:
feature-overlap/correlation analysis between text embeddings and derived
entity/event/state features — a small ablation delta may reflect
redundancy, not low informativeness." Without this ticket, a null result
in T045/T046/T048 (e.g. "Tier D barely beats Tier B") would be
uninterpretable — it could mean narrative state genuinely adds little, or
it could mean narrative state is highly correlated with what TF-IDF
already captures from the same text. This ticket is what lets the project
tell those two explanations apart, as §22 requires ("H1–H4 are each tested
with a reported effect size and direction" — direction is only meaningful
once this confound is addressed).

## Scope

- `ncp.evaluation.confounds.feature_overlap_report(tier_b_features, tier_c_features, tier_d_features) -> OverlapReport`:
  computes, per derived feature (entity/event/state dimension), its
  correlation (e.g. canonical correlation or simple linear-probe R²)
  against the Tier B text-feature space, on the **train split only** (this
  is itself a construction-set-scoped computation — fit any probe only on
  train, per §15's general rule).
- A report (`experiments/reports/feature_overlap.md`) summarizing which
  derived features are highly redundant with text features (candidates
  for "redundancy, not low informativeness" explanations of a small delta)
  versus which are largely orthogonal (candidates for genuine added
  information).

## Non-goals

- Do not use this analysis to retroactively adjust T045/T046/T048's
  reported numbers — it is an interpretive aid cited alongside those
  reports, not a correction to them.
- Do not compute this on val/test data — train-only, matching every other
  construction-set-scoped artifact in the project.

## Inputs

- T026 (Tier B features), T030 (Tier C features), T040 (Tier D features),
  T005 (train boundary).

## Outputs

- `src/ncp/evaluation/confounds.py`,
  `experiments/reports/feature_overlap.md`.

## Acceptance criteria

- The overlap computation is fit exclusively on train-split examples —
  verified by the same instrumented-construction-set pattern used in
  T012/T019/T026's leakage tests.
- The report is referenced explicitly from T045/T046/T048's reports (a
  cross-link or citation), so no reader of an ablation delta can miss the
  confound check.

## Tests

- Unit test on synthetic correlated vs. uncorrelated feature pairs,
  confirming the overlap metric correctly distinguishes them.
- Train-only-fitting leakage test, same pattern as prior construction-set
  tickets.

## Dependencies

T030, T040.

## Risks

- **Temporal causality:** same construction-set-scoping risk as every
  other fitted artifact in the project — guarded identically.
- **Interpretive risk (the point of this ticket):** without this check, a
  small H1/H3 delta could be wrongly read as "narrative state doesn't
  help" when the real explanation is feature redundancy — SPEC §18 names
  this explicitly as a required check, not an optional nicety.

## Definition of done

- [ ] `feature_overlap_report` implemented and run against the real train
      split.
- [ ] Report committed and cross-linked from T045/T046/T048.
- [ ] All listed tests pass.

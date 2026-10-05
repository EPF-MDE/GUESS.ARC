# T051 - Error analysis: repeat/explore decomposition

## Objective

Apply the repeat/explore decomposition (Li et al., *A Next Basket
Recommendation Reality Check*, TOIS 2023) to Tier D's event-label
predictions, as a diagnostic over already-produced results.

## Context

SPEC §19: "Repeat/explore decomposition (Li et al., *A Next Basket
Recommendation Reality Check*, TOIS 2023) applied to event-label
predictions... This section is diagnostic, explaining why a tier
over/underperforms using predictions already produced in §16–§18 — it does
not define a new independent run." This ticket consumes T044's (or T050's
rolling-origin) predictions; it must not retrain or re-run anything.

## Scope

- `ncp.evaluation.error_analysis.repeat_explore_split(example: ForecastingExample, prediction, gold) -> dict`:
  for each example, partition predicted/gold labels into "repeat" (present
  in the recent-events history window, T038) vs. "explore" (novel,
  i.e. not in the recent window) categories, and compute per-category
  precision/recall separately — following the cited paper's decomposition
  methodology.
- A report (`experiments/reports/error_repeat_explore.md`) over T044's
  archived Tier D predictions (and, if available, T042's Tier B
  predictions for comparison — repeat/explore performance differences
  between tiers are itself informative about *why* a tier wins or loses).

## Non-goals

- Do not retrain or produce any new model run — this ticket reads only
  already-archived T020 run artifacts.
- Do not implement the full methodology of the cited paper beyond what is
  needed for this decomposition — a focused, correctly-attributed
  reimplementation of the relevant repeat/explore split, not a general
  reproduction of the paper's entire experiment.

## Inputs

- T044 (or T050), T018 (metrics, reused for the per-category precision/
  recall computation).

## Outputs

- `src/ncp/evaluation/error_analysis.py` (this function; T052/T053 add
  more functions to the same module),
  `experiments/reports/error_repeat_explore.md`.

## Acceptance criteria

- The repeat/explore split for a given example is computed only from that
  example's own history window (T038's recent-events feature) — never
  from the gold label itself in a way that would leak the answer into the
  diagnostic category (the category is about label *novelty relative to
  history*, which is a feature-side computation, not a label-side one).
- The report cites the source paper correctly and states its decomposition
  methodology plainly.

## Tests

- Unit test on a synthetic example with known repeat/explore gold labels,
  confirming correct partitioning.
- A test confirming this function only reads already-archived predictions
  and the example's own history — never retrains a model.

## Dependencies

T044, T018.

## Risks

- **Temporal causality:** low — this is a read-only diagnostic over
  already-produced, already-leakage-tested predictions. The main risk is
  conceptual: miscategorizing a label as "repeat" using information not
  actually available at prediction time — guarded by deriving the
  "repeat" category strictly from T038's already-leakage-tested recent-
  events feature, not from any new, unchecked computation.

## Definition of done

- [ ] `repeat_explore_split` implemented and tested.
- [ ] Report generated over real T044 predictions and committed.

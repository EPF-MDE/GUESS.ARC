# T021 - Baseline: predict-nothing & most-frequent-events

## Objective

Implement the two cheapest Tier A baselines — predict-nothing (empty label
set) and most-frequent-events (top-N most frequent event categories in the
construction set) — as `ModelAdapter`-conforming stubs usable by T019's
runner.

## Context

SPEC §13, Tier A: "predict-nothing, most-frequent, persistence,
frequency-weighted recency, union/intersection of last-k | rule-based, no
learning | yes (uses only ≤t) | sanity baseline for all H1–H4." SPEC §16:
predict-nothing is specifically the example used to justify excluding
accuracy as a metric ("a predict-nothing model scores ~98.57% accuracy on
the character task") — implementing it is also what makes T018's
no-accuracy guarantee concretely demonstrable on real data.

## Scope

- `ncp.models.baselines.PredictNothing`: `ModelAdapter` that always
  predicts the empty set (and, for P@K/R@K, an empty score mapping).
- `ncp.models.baselines.MostFrequentEvents`: `fit(construction_set)`
  computes category frequency over the construction set only (reuse T016's
  `category_frequencies`, do not reimplement counting); `predict` always
  returns the fixed top-`model.top_k` categories as both a label set and a
  uniform/rank-ordered score mapping.
- Both registered under `ModelConfig.name` (`"predict_nothing"`,
  `"most_frequent"`) per the existing config convention.

## Non-goals

- Do not implement persistence or frequency-weighted-recency here — T022,
  T023.
- Do not fit `MostFrequentEvents` on anything other than the construction
  set passed in by T019's runner — no internal corpus-wide fallback.

## Inputs

- T007 (examples), T015 (event labels), T019 (runner interface), T016
  (frequency counting, reused).

## Outputs

- `src/ncp/models/baselines.py` (this ticket's two classes; T022/T023 add
  to the same module).

## Acceptance criteria

- `PredictNothing` requires no `fit` call (or `fit` is a no-op) and always
  predicts empty.
- `MostFrequentEvents.fit` never reads labels for chapters outside the
  construction set it is given.
- Running both through T019's holdout protocol produces a `MetricsReport`
  with non-accuracy metrics only.

## Tests

- Unit test confirming `PredictNothing`'s predictions are always empty
  regardless of input.
- Unit test confirming `MostFrequentEvents` picks exactly the top-`top_k`
  construction-set-frequent categories on a synthetic label set.
- Leakage test: `MostFrequentEvents.fit` called with an instrumented
  construction set confirms no chapter outside it is read.

## Dependencies

T007, T015, T019.

## Risks

- **Temporal causality:** `MostFrequentEvents` is the first ticket in the
  project that fits something (a frequency table) directly from data —
  must use only the construction set, exactly like every taxonomy/
  vectorizer ticket after it. Low complexity means low risk, but it is
  also the first real demonstration that the discipline holds end-to-end.

## Definition of done

- [ ] Both baselines implemented and tested.
- [ ] A real run against the actual corpus (holdout protocol) completes and
      is archived via T020.

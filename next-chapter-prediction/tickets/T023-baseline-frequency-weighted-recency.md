# T023 - Baseline: frequency-weighted recency

## Objective

Implement the frequency-weighted recency baseline: score each event
category by a decayed combination of its construction-set frequency (T016)
and its recency within the example's own history window, then predict the
top-`top_k` scored categories.

## Context

SPEC §13, Tier A lists "frequency-weighted recency" alongside persistence
as a standard rule-based baseline, and SPEC §4 names "frequency-weighted
top-25 53.1%" as a feasibility-doc number to be re-measured on this
project's own event target. This baseline is also the first one in the
project to produce genuinely ranked scores (not just a label set), making
it the first real exercise of T018's P@K/R@K metric path.

## Scope

- `ncp.models.baselines.FrequencyWeightedRecency`: `fit(construction_set)`
  stores per-category construction-set frequency (reusing T016); `predict(history)`
  computes, per category seen in the history window, a score combining
  normalized frequency and a recency weight (e.g.
  `weight = decay ** (t - chapter_of_last_occurrence)`, `decay` a config
  parameter under `ModelConfig.params`), and returns both a thresholded
  label set (top-`top_k`) and the full score mapping (for P@K/R@K).

## Non-goals

- Do not reuse `RepresentationConfig.recency_decay` as a hidden default
  without surfacing it explicitly in this model's own config — keep the
  parameter name and default documented at the call site that uses it,
  even if the underlying numeric convention is shared.
- Do not fit frequency on anything but the construction set (same
  discipline as T016/T021).

## Inputs

- T016 (frequencies), T007 (history windows), T019 (runner).

## Outputs

- Additions to `src/ncp/models/baselines.py`.

## Acceptance criteria

- `fit` reads construction-set frequencies only (reusing T016's function,
  not reimplementing counting independently — avoids two divergent
  frequency definitions in the codebase).
- `predict` returns a score for every category observed in the given
  history window, and nothing for categories absent from that specific
  window (even if frequent overall) — recency must matter, not just global
  frequency, matching the baseline's name.
- Changing `decay` changes the relative ranking of an older-but-frequent
  category vs. a newer-but-rare one in a predictable, tested direction.

## Tests

- Unit test with a synthetic history and two categories of different
  frequency/recency, asserting the score ordering changes as expected when
  `decay` is varied.
- Test that `fit` never reads labels outside the construction set
  (instrumented test, same pattern as T021).

## Dependencies

T016, T007, T019.

## Risks

- **Temporal causality:** same class as T021/T022 — the only way to leak
  here is fitting frequencies on more than the construction set, already
  guarded by reusing T016's tested function rather than reimplementing.

## Definition of done

- [ ] `FrequencyWeightedRecency` implemented and tested.
- [ ] A real run (holdout protocol) completes and is archived via T020.

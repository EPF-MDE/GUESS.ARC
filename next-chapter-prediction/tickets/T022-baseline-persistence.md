# T022 - Baseline: recent-event persistence

## Objective

Implement the recent-event persistence baseline: predict, for chapter t+1,
the union (or intersection, as a config option) of event labels observed in
the last-k chapters ending at t.

## Context

SPEC §13, Tier A names "persistence... union/intersection of last-k" as a
standard rule-based baseline, and SPEC §4 explicitly calls out that the
feasibility doc's persistence number (53.0% F1 micro) was measured on the
entity target and "must be re-measured on whichever target(s) each
experiment uses" — this ticket is what makes that re-measurement on the
*event* target possible for the first time in this codebase.

## Scope

- `ncp.models.baselines.RecentEventPersistence`: `ModelAdapter` with a
  config parameter `k` (last-k window, read from `ModelConfig.params`) and
  a `combine` mode (`"union"|"intersection"`); `predict(history)` reads
  only the `history_indices` chapters' already-known Layer 4 labels (via
  T015/T038's accessor — chapters ≤ t, by construction, since this is what
  `ForecastingExample.history_indices` already guarantees) and returns the
  union/intersection of their label sets as the prediction.
- Requires no `fit` step (purely a function of each example's own history)
  — but the `ModelAdapter.fit` method should still exist as a documented
  no-op, for interface consistency with T019's runner.

## Non-goals

- Do not implement frequency-weighted recency — T023.
- Do not read any label for a chapter outside `history_indices` — the
  model must take its input exclusively through the `ForecastingExample`
  interface built by T007, never by independently querying the full
  corpus.

## Inputs

- T007 (`ForecastingExample.history_indices`), T015 (event labels for
  history chapters), T019 (runner interface).

## Outputs

- Additions to `src/ncp/models/baselines.py`.

## Acceptance criteria

- For a fixed `k` and `combine` mode, predictions are a pure function of
  the given history window's labels — no hidden state across examples.
- `union` mode never produces a smaller prediction set than `intersection`
  mode on the same history, verified on a synthetic case.
- The model never queries chapter data outside what the `ForecastingExample`
  object exposes (checked by construction: the `predict` signature takes
  only the example, not the full corpus).

## Tests

- Unit test with a synthetic 5-chapter history and known labels, hand-
  computing the expected union/intersection prediction for `k=2` and `k=3`.
- Test that `predict`'s signature/implementation cannot access chapters
  beyond `history_indices` (e.g. by passing a `ForecastingExample` whose
  `history_indices` deliberately omit a chapter that exists in the full
  corpus, and confirming that chapter's labels never appear in the
  prediction).

## Dependencies

T007, T015, T019.

## Risks

- **Temporal causality:** low — `history_indices` is already
  leakage-checked by T007; this model's only way to violate causality
  would be bypassing the example interface and querying the corpus
  directly, which the test above specifically rules out.

## Definition of done

- [ ] `RecentEventPersistence` implemented for both `combine` modes.
- [ ] All listed tests pass.
- [ ] A real run (holdout protocol) completes and is archived via T020.

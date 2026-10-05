# T018 - Core evaluation metrics module

## Objective

Implement the closed set of metrics SPEC §16 names — Micro-F1, Macro-F1,
Precision, Recall, Precision@K, Recall@K — as pure functions over
multi-label predictions and gold label sets, explicitly excluding accuracy.

## Context

SPEC §16: "Primary metrics: Micro-F1, Macro-F1, Precision, Recall,
Precision@K, Recall@K (K≈20) on event labels (primary) and on the auxiliary
entity target (secondary, reported alongside). Accuracy is explicitly
excluded (a predict-nothing model scores ~98.57% accuracy on the character
task — the trivial-zero-baseline problem...). Additional metrics can be
introduced only when justified." This module is called by every single
later evaluation/report ticket; getting multi-label micro/macro semantics
right once here avoids five divergent reimplementations.

## Scope

- `ncp.evaluation.metrics.precision_recall_f1(y_true: Sequence[frozenset[str]], y_pred: Sequence[frozenset[str]], *, average: Literal["micro","macro"]) -> dict[str, float]`.
- `ncp.evaluation.metrics.precision_at_k(y_true, y_scores: Sequence[Mapping[str, float]], k: int) -> float` and
  `recall_at_k(...)` — operating on **ranked/scored** predictions (a
  mapping label → score per example), since P@K/R@K require a ranking, not
  just a label set; document this clearly, since baselines/models that only
  produce unranked sets (e.g. some Tier A baselines) must be adapted to
  emit scores, not have the metric redefined around them.
- A `MetricsReport` dataclass bundling all computed metrics plus the
  `k` value used, for clean serialization (feeds T020).
- No `accuracy` function anywhere in this module — enforced by a test, not
  just an omission, so a future contributor cannot "helpfully" add it back
  without noticing the SPEC rationale.

## Non-goals

- Do not add any metric beyond SPEC §16's list "just in case" — if a need
  arises later, update `SPEC.md` first (document's own stated rule).
- Do not implement the protocol runner (train/val/test wiring) — that is
  T019; this ticket is pure metric computation over already-produced
  predictions.

## Inputs

- None beyond the label-set/score conventions established by T008 (entity
  target) and T015 (event labels) — this module should be usable with
  synthetic data before either exists, since it has no pipeline dependency.

## Outputs

- `src/ncp/evaluation/metrics.py`

## Acceptance criteria

- Micro-F1/Macro-F1/Precision/Recall match hand-computed values on at least
  three worked examples (including one with class imbalance, since §23
  flags this as a real property of the data).
- P@K/R@K computed correctly against a ranked example with a known expected
  value for a specific `k`.
- No public function or constant named `accuracy` exists in the module.

## Tests

- The three worked-example tests above.
- A test for the predict-nothing edge case (all predictions empty) —
  verifying Micro-F1 behaves sanely (does not raise a division-by-zero
  unhandled exception) and specifically does **not** report a misleadingly
  high score the way raw accuracy would, documented in a comment pointing
  at §16's rationale.
- A grep/AST-based test asserting `accuracy` is absent from the module.

## Dependencies

None.

## Risks

- **Temporal causality:** none — this module computes over already-produced
  predictions/labels and has no access to chapter data or splits.
- **Metric-choice risk (§16):** the main risk is silently drifting from
  SPEC's exact metric list under schedule pressure (e.g. "let's just also
  report accuracy, it's easy") — guarded by the explicit negative test
  above.

## Definition of done

- [ ] All functions implemented and documented with their exact formula.
- [ ] Worked-example tests, edge-case test, and the no-accuracy test all
      pass.

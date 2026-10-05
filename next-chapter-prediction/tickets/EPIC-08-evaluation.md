# EPIC-08 — Evaluation

## Goal

Provide the metrics, the leakage-safe protocol runner, and the provenance
tagging that every other epic reports numbers through (**Part 1**, early);
then, once EPIC-06 produces predictions, aggregate the rolling-origin
comparison and run the diagnostic error analyses §19 requires (**Part 2**,
late).

## Why this epic exists (SPEC anchors)

- §16: Micro-F1, Macro-F1, Precision, Recall, Precision@K, Recall@K (K≈20)
  on the primary event target, entity target reported alongside; "Accuracy
  is explicitly excluded." This is a fixed, closed metric list — Part 1 must
  not add metrics beyond it without SPEC justification (§16: "Additional
  metrics can be introduced only when justified").
- §16 both protocols (chronological holdout, rolling-origin) "must be
  supported," with taxonomy/state construction respecting whichever
  protocol's boundaries are active — this is why T019 is one ticket
  covering both protocols behind one interface, not two separate runners.
- §21: "Every reported number tagged with: split/protocol identifier,
  taxonomy version, extraction version, `State(t)` component scope... No
  fabricated or placeholder results." This is T020's acceptance criterion
  verbatim.
- §19: repeat/explore decomposition, arc-transition breakdown, and
  `State(t)` component-availability breakdown are named as the three
  required diagnostics, explicitly "diagnostic, explaining why a tier
  over/underperforms using predictions already produced in §16–§18 — it does
  not define a new independent run." That sentence is why Part 2's tickets
  only ever consume EPIC-06 run artifacts and never retrain anything.

## Part 1 — Core infrastructure (must exist before EPIC-03)

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T018 | Core evaluation metrics module | Must | — | M |
| T019 | Leakage-safe evaluation protocol runner | Must | T018, T005, T006, T007 | L |
| T020 | Run/result provenance schema & archive | Must | T019 | S |

## Part 2 — Experiment analysis (after EPIC-06)

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T050 | Rolling-origin aggregation for H1/H3 final comparison | Must | T045, T046, T006, T020 | M |
| T051 | Error analysis: repeat/explore decomposition | Should | T044, T018 | M |
| T052 | Error analysis: arc-transition breakdown | Should | T044, T002 | M |
| T053 | Error analysis: `State(t)` component-availability breakdown | Should | T040, T044 | M |
| T054 | Reproducibility/provenance audit | Must | T020, T050 | S |

## Dependency notes

T018 has no dependency because metric functions (multi-label F1, precision,
recall, P@K/R@K) are pure functions over label sets and need no pipeline
data to exist — but it is still placed first because every later ticket in
the entire project calls it. Part 1 as a whole gates EPIC-03 (first reported
baseline number) and every later tier's run ticket. Part 2 cannot start
before EPIC-06 exists, since §19's diagnostics explicitly run over "predictions
already produced" — there is nothing to decompose before T042/T043/T044 have
run.

## Out of scope for this epic

- Defining a new metric not in §16's list, for any reason — if one seems
  needed, update `SPEC.md` first per the document's own rule ("update the
  document... or be treated as a bug").
- H4's rolling-origin aggregation — folded into EPIC-07 once that epic is
  ticketed, since H1/H3 (T050) and H4 depend on different tiers being ready.

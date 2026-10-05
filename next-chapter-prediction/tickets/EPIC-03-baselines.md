# EPIC-03 — Baselines (Tier A)

## Goal

Implement and reproduce, under this project's own code and evaluation
protocol, the Tier A trivial/statistical baselines (SPEC §13) on the primary
event-label target, before any ML tier is built.

## Why this epic exists (SPEC anchors)

- §13 Tier A: "predict-nothing, most-frequent, persistence, frequency-weighted
  recency, union/intersection of last-k... sanity baseline for all H1–H4."
- §4: the feasibility-doc numbers (persistence 53.0% F1 micro, etc.) are
  "baselines to reproduce with this project's own code and evaluation
  protocol, not unquestioned ground truth" — and were measured on the entity
  target, not events, so must be re-measured here on the event target.
- §22: "Tier A baselines are reproduced reliably under the chosen protocol (a
  pipeline sanity check, not a target)" is a named acceptance criterion.
- §16: "Accuracy is explicitly excluded (a predict-nothing model scores
  ~98.57% accuracy... the trivial-zero-baseline problem)" — this epic is the
  reason the metrics module (EPIC-08 T018) must exclude accuracy from the
  start.

## Tickets

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T021 | Baseline: predict-nothing & most-frequent-events | Must | T007, T015, T019 | S |
| T022 | Baseline: recent-event persistence | Must | T007, T015, T019 | S |
| T023 | Baseline: frequency-weighted recency | Must | T007, T015, T019 | S |
| T024 | Tier A baseline run & report | Must | T021, T022, T023, T019 | S |

## Dependency notes

Every ticket here needs EPIC-02's Layer 4 labels (T015) as the prediction
target and EPIC-08 Part 1's protocol runner (T019) to produce a reported
number — this epic cannot start before those exist, but it does not need
EPIC-04/05/06 at all, since none of these baselines learn a representation.
This is also why EPIC-03 is ordered before EPIC-04 in the roadmap: it is the
cheapest possible thing to run through the evaluation harness, and running it
first exercises T018–T020 before any model-training ticket does.

## Out of scope for this epic

- Any baseline that fits parameters via gradient descent or supervised
  training — that starts at EPIC-06 (Tier B/C/D Embedding+MLP runs).
- Reporting on the auxiliary entity target as if it were the primary result
  — §13 requires it be measured, but T024's report must present it as
  secondary, matching §5.

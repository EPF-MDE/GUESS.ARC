# EPIC-06 — Event Forecasting (Embedding+MLP, H1–H3, ablations)

## Goal

Instantiate one shared Embedding+MLP architecture over Tier B, Tier C, and
Tier D inputs (SPEC §14), run it under the chronological protocol, and
produce the concrete H1, H2, H3 experiment reports and the §18 ablations —
the first point in the project where a hypothesis is actually tested.

## Why this epic exists (SPEC anchors)

- §14: "v1 core: Embedding+MLP architecture, instantiated three ways — Tier
  B inputs, Tier C inputs, Tier D inputs — producing the H1/H3 comparison
  pair from one architecture family, removing architecture choice as a
  confound." One architecture, three data tickets (T042–T044), is a direct
  reading of this sentence.
- §16's hypothesis → experiment mapping table is this epic's acceptance
  criteria source: each of H1, H2, H3 names an independent variable, a
  dependent variable, a baseline, a protocol, and metrics that the
  corresponding ticket must reproduce exactly.
- §17: the context-length sweep (H2) has its own confound to control ("report
  whether degradation at large `history_size` is tier-specific") — ticketed
  separately (T047) because it is a sweep over a different axis than
  T042–T044.
- §18: ablations must "change exactly one representational ingredient at a
  time, holding model family, split, and taxonomy version fixed," with a
  "required confound check before interpreting any delta" — T048 and T049
  are two different tickets because the ablation runs and the confound
  check are different activities with different acceptance criteria.

## Tickets

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T041 | Embedding+MLP model architecture | Must | T019, T004 | M |
| T042 | Tier B training/evaluation run | Must | T041, T026 | S |
| T043 | Tier C training/evaluation run | Must | T041, T030 | S |
| T044 | Tier D training/evaluation run | Must | T041, T040 | S |
| T045 | H1 experiment report (Tier D vs. Tier B) | Must | T042, T044, T020 | M |
| T046 | H3 experiment report (Tier C vs. Tier B) | Must | T042, T043, T020 | M |
| T047 | H2 experiment: `history_size` sweep | Must | T042, T020 | L |
| T048 | Ablations: +entities / +events-as-input / +full state | Must | T030, T038, T040, T042 | L |
| T049 | Feature-overlap confound check (§18) | Must | T030, T040 | M |

## Dependency notes

T042/T043/T044 are the same training procedure (T041) over three input
tables and can run in parallel once their respective EPIC-04/05 tickets are
done. T045/T046 only aggregate already-produced runs — they do not retrain
anything. T048's third ablation row ("text-only vs. +full narrative state")
is the same comparison as H1/T045; the ticket should reuse T044's run rather
than retraining, per CLAUDE.md's "no unnecessary rewrites." T048's fourth
`SPEC.md` §18 ablation row ("static state vs. sequential," testing H4) is
**not** in this epic's ticket — it requires Tier E, which is EPIC-07's gated,
not-yet-ticketed scope.

## Out of scope for this epic

- Tier E (GRU/LSTM/Transformer) and the H4 experiment — EPIC-07, gated.
- Rolling-origin aggregation across H1/H3 and all error analysis — EPIC-08
  Part 2 (T050–T054), which consumes this epic's run artifacts but is a
  separate evaluation activity, not a modeling one.
- Summary generation conditioned on predicted events — EPIC-09, out of v1
  scope regardless of how well this epic's models perform.

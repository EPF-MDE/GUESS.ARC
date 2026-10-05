# T047 - H2 experiment: `history_size` sweep

## Objective

Run Tier B (T042's wiring, varying only `forecasting.history_size`) across
a configured sweep of history lengths, and report the Micro-F1/Macro-F1
vs. `history_size` curve, controlling for the long-context-difficulty
confound named in SPEC §17.

## Context

SPEC §16: "H2 — context length | `history_size` (sweep) | event-label F1 |
same tier at minimal `history_size` | holdout (confirm on rolling-origin if
signal found) | Micro-F1, Macro-F1." SPEC §17 adds: "Confound to control:
long-context difficulty (§23) — report whether degradation at large
`history_size` is tier-specific, to separate 'more history helps' from
'this architecture handles long context poorly.'" This is the only
hypothesis in §16 whose independent variable is *not* representation tier,
so it gets its own ticket rather than reusing T045/T046's structure.

## Scope

- A sweep runner iterating `forecasting.history_size` over a configured
  list (e.g. a short, medium, long, and full-history value), rebuilding
  T007's examples and T026's Tier B features fresh for each value
  (`history_size` changes which chapters are "history," so T025's
  assembled text and T026's fit both legitimately change per sweep point —
  not a confound, since `history_size` is the independent variable being
  tested), running T041's `EmbeddingMLP`, archiving each point via T020
  with `history_size` recorded in provenance.
- A report (`experiments/reports/h2_history_size_sweep.md`) with the
  Micro-F1/Macro-F1-vs-`history_size` table/curve and an explicit note on
  whether degradation (if any) at large `history_size` is accompanied by
  training instability (e.g. loss curve behavior) suggestive of
  "architecture handles long context poorly" rather than "more history
  doesn't help."
- Baseline comparison point: the same tier/model at the smallest
  `history_size` in the sweep (per §17's "Baseline" column).

## Non-goals

- Do not run the full sweep under rolling-origin as a default — §17: "holdout
  split for the initial sweep; confirm any non-monotonic finding on
  rolling-origin before reporting it as conclusive." Only re-run on
  rolling-origin if the holdout sweep shows a non-monotonic pattern.
- Do not sweep Tier C/D in this ticket — §16/§17 specify this experiment
  at "same tier," and Tier B is the natural first tier to run it on; a
  same-ticket-shape sweep for other tiers, if wanted later, is a separate,
  explicitly new ticket, not an expansion of this one.

## Inputs

- T042's wiring pattern, T007, T026, T041, T019, T020.

## Outputs

- `experiments/reports/h2_history_size_sweep.md`, one archived run per
  sweep point.

## Acceptance criteria

- Every sweep point's run is independently archived with its own
  `history_size` in provenance.
- The report explicitly addresses the long-context-difficulty confound
  (§17), not just the raw curve.
- If the curve is non-monotonic, the report states that a rolling-origin
  confirmation is required before treating the finding as conclusive, per
  §17 — and either performs it or explicitly marks it as a follow-up.

## Tests

- A fast CI integration test running a 2-3-point sweep on synthetic data,
  confirming the sweep mechanism (distinct `history_size` per point,
  correctly recorded in each archived run's provenance).

## Dependencies

T042, T020.

## Risks

- **Temporal causality:** each sweep point independently inherits T007/
  T026's existing leakage guarantees (every `history_size` value still
  respects `max(history_indices) < target_index`); no new leakage path is
  introduced by varying this one parameter. The real risk named by SPEC is
  the **long-context-difficulty confound** (§17, §23) — not leakage, but a
  validity-of-interpretation risk that this ticket's report must address
  explicitly rather than ignore.

## Definition of done

- [ ] Sweep implemented and run against the real corpus for the configured
      `history_size` values.
- [ ] Report committed, explicitly addressing the long-context-difficulty
      confound.
- [ ] Non-monotonic findings (if any) flagged as pending rolling-origin
      confirmation.

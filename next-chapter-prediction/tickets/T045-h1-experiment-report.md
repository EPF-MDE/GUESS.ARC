# T045 - H1 experiment report (Tier D vs. Tier B)

## Objective

Aggregate T042's (Tier B) and T044's (Tier D) archived holdout runs into
the concrete H1 experiment report: effect size, direction, and full
provenance, per SPEC §16's hypothesis-mapping table.

## Context

SPEC §16: "H1 — state > text-only | representation: Tier D vs. Tier B |
event-label F1/P@K/R@K | Tier B | holdout + rolling-origin | Micro-F1,
Macro-F1, P@K, R@K." SPEC §3: "H1 — Explicit narrative state improves
next-event prediction compared with text-only representations." SPEC §22:
"H1–H4 are each tested with a reported effect size and direction, including
null or negative effects... A negative outcome... is an acceptable,
complete project result." This ticket is where H1 first becomes a
concrete, reportable finding rather than an aspiration — on the holdout
protocol; the rolling-origin confirmation is T050.

## Scope

- `ncp.evaluation.reports.h1_report(tier_b_run: Path, tier_d_run: Path) -> H1Report`
  (or equivalent script): loads both archived runs (T020's `load_run`),
  computes the metric deltas (Micro-F1, Macro-F1, P@K, R@K, on the primary
  event target; entity target reported alongside per §5), and states
  direction (D > B / D < B / no significant difference) plainly, with no
  implied interpretation beyond what the numbers show.
- Written report (`experiments/reports/h1_holdout.md`) including both
  runs' full provenance tags.

## Non-goals

- Do not claim H1 is "confirmed" or "rejected" from holdout alone — SPEC
  §16 requires "holdout + rolling-origin" for this hypothesis; this
  ticket's report must explicitly flag itself as the holdout half, pending
  T050's rolling-origin aggregation before any final claim.
- Do not retrain or re-run anything — pure aggregation over T042/T044's
  already-archived outputs.

## Inputs

- T042, T044, T020.

## Outputs

- `experiments/reports/h1_holdout.md`

## Acceptance criteria

- The report states the exact metric values for both tiers, the delta, and
  the direction, with no rounding that would hide a null result.
- The report explicitly states it is the holdout-only half of H1's full
  protocol and names T050 (rolling-origin) as the pending confirmation
  step.
- If the delta favors Tier B (a negative result for H1), the report states
  this plainly, per §22's explicit acceptance of null/negative outcomes.

## Tests

- A test that the report-generation function raises a clear error if
  either run's provenance is missing/incomplete (reusing T020's guard),
  rather than silently reporting from partial data.

## Dependencies

T042, T044, T020.

## Risks

- **Temporal causality:** none new (pure aggregation of already-leakage-
  tested runs). The risk here is reporting discipline: overstating a
  holdout-only result as conclusive, or fabricating an effect size — both
  explicitly guarded against by the acceptance criteria above and by
  `CLAUDE.md`'s "no fabricated experiment results."

## Definition of done

- [ ] Report generated from real T042/T044 runs and committed.
- [ ] Report explicitly scoped as holdout-only pending T050.
- [ ] Missing-provenance guard test passes.

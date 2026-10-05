# T050 - Rolling-origin aggregation for H1/H3 final comparison

## Objective

Re-run Tier B, Tier C, and Tier D under T006's rolling-origin protocol,
aggregate metrics across origins, and produce the final cross-tier H1/H3
comparison SPEC §16 requires before either hypothesis can be called tested.

## Context

SPEC §16: H1 and H3 both require protocol "holdout + rolling-origin." SPEC
§16: "Rolling-origin... Preferred for the final cross-tier comparison."
T045/T046 only covered the holdout half; this ticket is what makes H1/H3
claims complete per §22 ("H1–H4 are each tested with a reported effect
size and direction... Every result carries its full provenance tag").

## Scope

- Re-run T042 (Tier B), T043 (Tier C), T044 (Tier D)'s exact wiring under
  `protocol="rolling_origin"` via T019's runner, using T006's generated
  origins, with concrete `window`/`step`/`n_origins` values chosen and
  documented here (resolving SPEC §26's "Rolling-origin evaluation design"
  as a configuration choice for this specific reported comparison, not as
  a universal constant).
- `ncp.evaluation.aggregation.aggregate_origins(results: list[ProtocolResult]) -> AggregatedReport`:
  mean and variance of each §16 metric across origins, per tier.
- A final report (`experiments/reports/h1_h3_rolling_origin.md`)
  presenting the holdout results (T045/T046) alongside the rolling-origin
  aggregates, and stating the final H1/H3 conclusions (including null/
  negative outcomes plainly, per §22) now that both required protocol legs
  exist.

## Non-goals

- Do not include H4 in this ticket — Tier E does not exist; H4's
  rolling-origin requirement is EPIC-07's concern once that epic opens.
- Do not re-derive taxonomy/state construction logic — reuse T012/T013's
  incremental-or-frozen taxonomy exactly as T006/T019 already wire it
  together; this ticket only adds the aggregation layer on top.

## Inputs

- T045, T046, T006, T020, T042, T043, T044.

## Outputs

- `src/ncp/evaluation/aggregation.py`,
  `experiments/reports/h1_h3_rolling_origin.md`.

## Acceptance criteria

- Each tier is run across every configured origin, with each origin's
  result independently archived via T020 (full provenance per origin,
  including `construction_set_id`).
- Aggregated metrics report both mean and variance across origins — a
  single mean without variance would understate how much the chosen split
  boundary could be driving any apparent H1/H3 effect.
- The final report explicitly states the H1 and H3 conclusions (direction,
  effect size, and whether holdout and rolling-origin agree or disagree),
  per §22's completeness requirement.

## Tests

- Unit test for `aggregate_origins` on synthetic per-origin results with a
  hand-computed expected mean/variance.
- A test confirming every origin's run used a distinct, correctly-scoped
  `construction_set_id` (reusing T006/T019's existing leakage test
  patterns, applied here as a regression check rather than a new guard).

## Dependencies

T045, T046, T006, T020.

## Risks

- **Temporal causality:** inherits T006/T019's existing per-origin
  guarantees; the specific new risk here is **aggregation-level**, not
  leakage — averaging across too few origins, or origins that are not
  really independent (e.g. heavily overlapping windows), could overstate
  confidence in a direction. The report must state `n_origins` and window
  type plainly so this is auditable.
- **Arc distribution shift (§23):** rolling-origin, by chronology,
  necessarily separates arcs across origins differently than holdout does
  — the report should note any origin whose boundary lands exactly on a
  known arc-transition chapter (feeds T052's later, more detailed
  analysis).

## Definition of done

- [ ] Rolling-origin runs for Tier B/C/D completed and archived, one per
      origin.
- [ ] `aggregate_origins` implemented and tested.
- [ ] Final report committed with explicit H1/H3 conclusions, including
      any null/negative outcome stated plainly.

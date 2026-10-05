# T053 - Error analysis: `State(t)` component-availability breakdown

## Objective

Produce a breakdown of Tier D's prediction errors by which `State(t)`
components were weak/heuristic for the chapters in question, as a
diagnostic over already-produced results.

## Context

SPEC §19: "Breakdown by `State(t)` component availability — whether errors
concentrate on chapters where heuristic/partial v1 components (e.g.
unresolved questions, active conflicts) were weakest." SPEC §8 already
tags which components are heuristic for v1 (components 2, 5, 6, 7) versus
full-fidelity (1, 3, 8, 9) — T040's `StateVector.component_scope` carries
this tag per run; this ticket is the first consumer of that field for its
intended diagnostic purpose.

## Scope

- `ncp.evaluation.error_analysis.component_availability_breakdown(predictions, gold, state_vectors: list[StateVector]) -> dict`:
  for each example, record which components were non-empty/substantive
  (e.g. "had at least one active conflict," "had at least one unresolved
  question") vs. empty/trivial, and correlate error rate with component
  richness, separately per heuristic component (2, 5, 6, 7).
- A report (`experiments/reports/error_state_component_availability.md`)
  presenting, per heuristic component, whether chapters where that
  component was richer/weaker correlate with better/worse prediction —
  informing which §8 components would most benefit from future
  full-fidelity investment (explicitly framed as a forward-looking
  observation, not a v1 scope change).

## Non-goals

- Do not retrain or re-run any model.
- Do not use this breakdown to justify silently upgrading any component's
  fidelity mid-ticket — any such upgrade is a separate, explicitly scoped
  future ticket.

## Inputs

- T044 (predictions), T040 (`StateVector`s with `component_scope`), T018.

## Outputs

- Additions to `src/ncp/evaluation/error_analysis.py`,
  `experiments/reports/error_state_component_availability.md`.

## Acceptance criteria

- The breakdown correctly uses T040's `component_scope` tagging (full-
  fidelity vs. heuristic) rather than re-deriving which components are
  heuristic from scratch — single source of truth for that classification.
- The report presents results separately for each heuristic component (2,
  5, 6, 7), not a single pooled "heuristic vs. full" number, since §19
  specifically names individual components ("unresolved questions, active
  conflicts") as examples.

## Tests

- Unit test on a synthetic set of `StateVector`s with known
  richness/error correlation, confirming the breakdown computes the
  expected per-component result.
- A test confirming this function only reads already-archived predictions
  and `StateVector`s, never retrains.

## Dependencies

T040, T044.

## Risks

- **Temporal causality:** none new — read-only diagnostic over already-
  leakage-tested `StateVector`s and predictions.

## Definition of done

- [ ] `component_availability_breakdown` implemented and tested.
- [ ] Report generated over real T044 predictions and committed, broken
      down per heuristic component.

# T019 - Leakage-safe evaluation protocol runner

## Objective

Implement a single protocol-runner interface that can execute any model
(baseline or ML) under either SPEC §16 protocol — chronological holdout or
rolling-origin — producing a `MetricsReport` (T018) per split/origin, with
every run tagged for provenance (feeding T020).

## Context

SPEC §16: "Both supported... Whichever protocol is active, the event
taxonomy (§10 Layer 3) and any `State(t)` vocabulary must be constructed
respecting that protocol's boundaries — never from the full corpus." This
ticket is the one place that enforces, mechanically, that a model under
test only ever receives train-scoped artifacts for whichever protocol is
active — rather than trusting every individual experiment script to get
this right independently.

## Scope

- `ncp.evaluation.runner.Protocol` (enum/literal: `"holdout"`,
  `"rolling_origin"`).
- `ncp.evaluation.runner.run_protocol(model: ModelAdapter, protocol: Protocol, corpus: Corpus, forecasting_config: ForecastingConfig, *, construction_set_builder: Callable[[SplitBoundaries], ConstructionSet]) -> ProtocolResult`:
  for `holdout`, builds one `SplitBoundaries` (T005), has
  `construction_set_builder` produce whatever train-scoped artifacts
  (taxonomy, vectorizer, state config) the model needs, fits/evaluates once;
  for `rolling_origin`, iterates T006's list of boundaries, repeating the
  same construction-then-evaluate cycle per origin, and collects a
  `MetricsReport` per origin.
- `ModelAdapter` protocol/interface (fit, predict, predict_scores) that
  every baseline (EPIC-03) and ML model (EPIC-06) implements, so the runner
  is written once against an interface, not against each model's concrete
  type.
- Every `ProtocolResult` carries the exact `construction_set_id` used, so
  T020 can tag results without recomputing anything.

## Non-goals

- Do not implement any specific model or baseline here — only the harness.
- Do not implement rolling-origin result *aggregation* across origins
  (mean/variance of metrics) — that is T050; this ticket returns the raw
  per-origin results.

## Inputs

- T018 (metrics), T005 (holdout boundaries), T006 (rolling-origin
  boundaries), T007 (forecasting examples).

## Outputs

- `src/ncp/evaluation/runner.py`

## Acceptance criteria

- Running `run_protocol` with `protocol="holdout"` against any
  `ModelAdapter`-conforming stub produces exactly one `MetricsReport`.
- Running with `protocol="rolling_origin"` produces one `MetricsReport` per
  origin, each tagged with its own `construction_set_id`, and no two
  origins' results use the same taxonomy/vectorizer instance unless the
  taxonomy mode is explicitly frozen-shared-across-origins (a documented,
  deliberate choice, not an accident).
- The runner never calls `construction_set_builder` with a boundary that
  includes any val/test chapter in the "construction" side — verified by a
  test using an instrumented `construction_set_builder`.

## Tests

- Unit test with a trivial stub `ModelAdapter` (e.g. always predicts the
  empty set) run under both protocols, checking result shape and count.
- Leakage test: instrumented `construction_set_builder` records every
  chapter index it was asked to build from; assert none exceed the active
  boundary, for both protocols.
- Test that a `ModelAdapter` raising mid-fit propagates a clear error
  rather than being silently swallowed (no fabricated results, per
  `CLAUDE.md`).

## Dependencies

T018, T005, T006, T007.

## Risks

- **Temporal causality — the core purpose of this ticket.** This is the
  single choke point meant to make every future experiment leakage-safe by
  construction rather than by each script remembering to be careful. A bug
  here affects every single reported number in the project. The
  instrumented-builder leakage test is non-negotiable and must run in CI.

## Definition of done

- [ ] `run_protocol` implemented for both protocols against the
      `ModelAdapter` interface.
- [ ] All listed tests pass, including the instrumented leakage test.
- [ ] Interface documented clearly enough that EPIC-03/06 tickets can
      implement `ModelAdapter` without re-reading this ticket's internals.

# T044 - Tier D training/evaluation run

## Objective

Run T041's `EmbeddingMLP` over Tier D (full `State(t)`, T040) features
through T019's holdout protocol, archive the result via T020.

## Context

SPEC §13 Tier D "tests H1" — the primary research question of the whole
project ("Does an explicit narrative-state representation improve
next-chapter event prediction compared with text-only representations?").
This run, together with T042's Tier B run, is the direct H1 comparison
(T045). Same single-ingredient-change discipline as T043 applies here
relative to T042.

## Scope

- A run script/config (`configs/experiment/tier_d.yaml`) identical to
  T042's `tier_b.yaml` except `representation.name = "text_full"` (or
  equivalent), wired to T040's `build_state` output (flattened into a
  feature vector, concatenated with or replacing Tier B text features per
  whatever Tier D's documented composition is — if Tier D is "full state
  only" vs. "state + text," this must match SPEC §13's table wording:
  "full `State(t)` (§8) as engineered features" — implement Tier D as
  `State(t)` features, with text features included via the same text
  history the other tiers use if that is how `State(t)` is documented to
  compose; resolve ambiguity by matching Tier D to exactly what T040
  outputs, not by inventing a new composition here).
- Same execution shape as T042/T043.

## Non-goals

- Do not change any hyperparameter relative to T042's run, for the same
  confound-avoidance reason as T043.
- Do not attempt to upgrade any §8 heuristic component to full fidelity as
  part of running this tier — use T040's output as-is, heuristic
  components included, and record `component_scope` in provenance so the
  limitation is visible in the eventual H1 report.

## Inputs

- T041, T040, T019, T020.

## Outputs

- `configs/experiment/tier_d.yaml`, an archived run under
  `experiments/<run_id>/`.

## Acceptance criteria

- The run completes and produces a `MetricsReport` with all §16 metrics.
- A config-diff against T042 shows only representation-related fields
  changed.
- Archived provenance records `tier="D"` and the full `component_scope`
  from T040 (which components were full-fidelity vs. heuristic for this
  run).

## Tests

- Config-diff test against T042.
- Fast CI integration test mirroring T042's.

## Dependencies

T041, T040.

## Risks

- **Temporal causality:** this run is the highest-stakes consumer of
  T040's leakage guard — if T040's full-corpus-vs-truncated-corpus
  identity test ever regresses, this run's result (the project's primary
  H1 claim) is the one that would be silently wrong. No new risk is
  introduced here, but this ticket's acceptance criteria should include
  re-confirming T040's leakage test still passes before trusting this
  run's numbers.

## Definition of done

- [ ] Real-corpus run completes and is archived, with `component_scope`
      recorded.
- [ ] Config-diff test against T042 passes.
- [ ] CI integration test passes.
- [ ] T040's leakage guard test re-confirmed green immediately before
      treating this run's output as reportable.

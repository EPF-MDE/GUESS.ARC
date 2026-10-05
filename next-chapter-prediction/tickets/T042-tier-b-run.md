# T042 - Tier B training/evaluation run

## Objective

Run T041's `EmbeddingMLP` over Tier B (TF-IDF, T026) features through
T019's holdout protocol, archive the result via T020.

## Context

SPEC §13 Tier B is the text-only baseline every later comparison (H1, H3)
measures against. SPEC §14 names this as the first of the three required
instantiations. This ticket is deliberately thin — wiring, not new logic —
per `CLAUDE.md`'s "no giant scripts" and "no unnecessary rewrites."

## Scope

- A run script/config (`configs/experiment/tier_b.yaml` or equivalent)
  setting `representation.name = "text"`, `representation.encoder =
  "tfidf"`, `model.name = "embedding_mlp"`.
- Execute: build Tier B features for every example (T025→T026) → fit
  `EmbeddingMLP` on train → evaluate on val/test via T019 → archive via
  T020 with `tier="B"` provenance.

## Non-goals

- Do not tune hyperparameters extensively — use documented, reasonable
  defaults; hyperparameter search is not named as a SPEC requirement.
- Do not run under rolling-origin yet — holdout only here; T050 handles
  rolling-origin aggregation once all tiers have holdout runs.

## Inputs

- T041, T026, T019, T020.

## Outputs

- `configs/experiment/tier_b.yaml`, an archived run under
  `experiments/<run_id>/`.

## Acceptance criteria

- The run completes end-to-end against the real corpus and produces a
  `MetricsReport` with all §16 metrics (primary event target; auxiliary
  entity target reported alongside, never substituted).
- The archived run's provenance correctly records `tier="B"`,
  `taxonomy_version`, `extraction_version`, `split_protocol="holdout"`.

## Tests

- A fast integration test running this exact wiring on a small synthetic
  corpus in CI (mirroring T024's pattern), separate from the slow real-
  corpus run.

## Dependencies

T041, T026.

## Risks

- **Temporal causality:** none new — this ticket only orchestrates
  already-leakage-tested components (T026, T041, T019). Its own risk is
  purely configuration mistakes (e.g. wrong `representation.name`),
  caught by the integration test asserting the expected feature shape is
  used.

## Definition of done

- [ ] Real-corpus run completes and is archived.
- [ ] CI integration test passes on synthetic data.

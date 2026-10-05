# T024 - Tier A baseline run & report

## Objective

Run all three Tier A baselines (T021–T023) through T019's protocol runner
under the chronological holdout split, archive the results via T020, and
produce a short comparison report on both the primary event target and the
auxiliary entity target.

## Context

SPEC §22: "Tier A baselines are reproduced reliably under the chosen
protocol (a pipeline sanity check, not a target)." SPEC §4: the
feasibility-doc numbers are explicitly something "to reproduce with this
project's own code and evaluation protocol," re-measured per target. This
ticket is the first point in the project where a complete, provenance-tagged
number exists for anything — it is the end-to-end pipeline sanity check
the whole project depends on before any representation/model work is
trusted.

## Scope

- A run script/notebook (per `CLAUDE.md`'s "no giant scripts" — keep this
  thin, calling into T019/T021-23/T020, not reimplementing logic) that
  runs `PredictNothing`, `MostFrequentEvents`, `RecentEventPersistence`,
  `FrequencyWeightedRecency` under `protocol="holdout"` on the real corpus,
  for both the primary event target (T015) and, alongside, the auxiliary
  entity target (T008) — two separate metric computations per baseline,
  clearly labeled primary/secondary, never merged into one number (§5).
- A short report (`experiments/reports/tier_a_baselines.md`) tabulating
  Micro-F1/Macro-F1/Precision/Recall/P@K/R@K for all four baselines on both
  targets.

## Non-goals

- Do not run under rolling-origin yet — holdout is sufficient for this
  pipeline-sanity-check purpose per §22's wording ("reproduced reliably
  under the chosen protocol," singular, for this step); rolling-origin
  aggregation across tiers is EPIC-08 Part 2's job once more tiers exist.
- Do not interpret these numbers as a target to beat — §22 explicitly: "The
  project's success is not defined as 'beat the 53% F1 persistence
  baseline.'" The report must say so.

## Inputs

- T021, T022, T023, T019, T020, T008, T015.

## Outputs

- Run script, `experiments/reports/tier_a_baselines.md`, archived run
  records under `experiments/<run_id>/`.

## Acceptance criteria

- All four baselines run to completion against the real corpus without
  error.
- Each archived run carries complete T020 provenance (taxonomy version,
  extraction version, split identifier).
- The report explicitly separates primary (event) and secondary (entity)
  metrics per baseline and includes the explicit "not a target to beat"
  framing from §22.

## Tests

- An integration/smoke test that the run script executes end-to-end on a
  small synthetic corpus (fast) in CI, separate from the slow full-corpus
  run (which may be a manual or scheduled step, documented as such).

## Dependencies

T021, T022, T023, T019.

## Risks

- **Temporal causality:** none new — this ticket only orchestrates already
  leakage-tested components (T005/T007/T019/T021-23). Its own risk is
  reporting discipline: conflating primary/secondary targets, or presenting
  a baseline number as a target, both explicitly guarded against above.

## Definition of done

- [ ] All four baselines run and archived against the real corpus.
- [ ] Report committed with both targets clearly separated and the §22
      framing included.
- [ ] CI smoke test passes on a fast synthetic corpus.

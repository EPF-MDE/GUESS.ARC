# T046 - H3 experiment report (Tier C vs. Tier B)

## Objective

Aggregate T042's (Tier B) and T043's (Tier C) archived holdout runs into
the concrete H3 experiment report: effect size, direction, and full
provenance, mirroring T045's structure exactly for the entity-aware
comparison.

## Context

SPEC §16: "H3 — entities > text-only | representation: Tier C vs. Tier B |
event-label F1/P@K/R@K | Tier B | holdout + rolling-origin | Micro-F1,
Macro-F1, P@K, R@K." SPEC §3: "H3 — Entity-aware representations improve
prediction compared with text-only representations." This ticket is
intentionally structured identically to T045 (same report shape, same
scoping caveats) since both are instances of the same §16 table pattern,
differing only in which tier pair is compared.

## Scope

- Reuse T045's report-generation function/module, parameterized by the two
  run paths, rather than writing a second, divergent implementation — one
  `h1_h3_report` shape serving both tickets is acceptable and preferred
  over code duplication (per `CLAUDE.md`'s "no unnecessary rewrites").
- Written report (`experiments/reports/h3_holdout.md`).

## Non-goals

- Do not claim H3 is confirmed/rejected from holdout alone — same
  holdout-plus-rolling-origin requirement as H1; T050 provides the
  rolling-origin half.
- Do not retrain or re-run anything.

## Inputs

- T042, T043, T020.

## Outputs

- `experiments/reports/h3_holdout.md`

## Acceptance criteria

- Same acceptance criteria shape as T045, applied to the Tier C vs. Tier B
  pair: exact metric values, delta, direction, explicit holdout-only
  scoping, plain statement of a null/negative result if that is what the
  data shows.

## Tests

- Same missing-provenance guard test as T045 (if implemented as a shared
  function, this test may already be covered by T045's test; otherwise
  duplicate the check for this call site).

## Dependencies

T042, T043, T020.

## Risks

- **Temporal causality:** none new. Same reporting-discipline risk as T045,
  same mitigation.

## Definition of done

- [ ] Report generated from real T042/T043 runs and committed.
- [ ] Report explicitly scoped as holdout-only pending T050.

# T048 - Ablations: +entities / +events-as-input / +full state

## Objective

Report the three in-scope §18 ablation rows (text-only vs. +entities,
text-only vs. +past-events-as-input, text-only vs. +full-narrative-state),
each changing exactly one representational ingredient relative to the
Tier B baseline, reusing already-archived runs wherever possible.

## Context

SPEC §18's ablation table has four rows; the fourth ("static state vs.
sequential," testing H4) requires Tier E and is explicitly out of this
ticket's scope (EPIC-07, gated, not yet ticketed). The first three rows map
directly onto comparisons this project already has the pieces for:
"text-only vs. +entities" = T042 vs. T043 (already T046's H3 report, so
this ticket's row 1 can cite T046 rather than re-running); "text-only vs.
+full narrative state" = T042 vs. T044 (already T045's H1 report, cited
similarly); "text-only vs. +past events as input" is the one genuinely new
run this ticket must produce — a Tier B-plus-recent-events variant that
isolates T038's component 8 specifically, without the rest of `State(t)`.

## Scope

- A new intermediate representation,
  `ncp.representations.tier_b_plus_events`, concatenating Tier B text
  features (T026) with T038's recent-events window features only (not the
  full T040 `StateVector`) — a minimal new assembly function, structurally
  identical in spirit to T030's Tier C assembly but for events instead of
  entities.
- A run (`configs/experiment/tier_b_plus_events.yaml`) under the same
  single-change discipline as T043/T044 relative to T042.
- A combined ablation report (`experiments/reports/ablations.md`) covering
  all three in-scope rows, citing T045/T046 for rows 1 and 3 (by SPEC's
  table ordering: entities and full-state) and this ticket's new run for
  row 2 (past-events-as-input), each stating hypothesis tested, delta, and
  direction.
- Explicitly note the fourth row (static vs. sequential, H4) as
  **deferred**, with a one-line pointer to EPIC-07's gate condition.

## Non-goals

- Do not re-run the entities or full-state comparisons — cite T046/T045's
  already-archived results; this ticket must not duplicate work `CLAUDE.md`
  already asks be avoided ("no unnecessary rewrites").
- Do not attempt the fourth ablation row — Tier E does not exist yet.

## Inputs

- T038, T026, T041, T019, T020, T045, T046.

## Outputs

- `src/ncp/representations/tier_b_plus_events.py`,
  `configs/experiment/tier_b_plus_events.yaml`,
  `experiments/reports/ablations.md`.

## Acceptance criteria

- The new past-events-as-input run differs from T042's config only in the
  representation (verified by config-diff, same pattern as T043/T044).
- The combined report covers exactly three rows, cites existing reports
  for two of them rather than re-deriving numbers, and explicitly defers
  the fourth with a stated reason.

## Tests

- Config-diff test for the new run against T042.
- CI integration test for the new representation's assembly function
  (mirrors T030's shape test: feature count equals Tier B width plus
  recent-events feature width).

## Dependencies

T038, T026, T041, T045, T046.

## Risks

- **Temporal causality:** the new run inherits T026/T038's existing
  guarantees; no new leakage path. The main risk specific to this ticket
  is the confound §18 names generally — "change exactly one... ingredient
  at a time" — enforced by the config-diff test, same as T043/T044.

## Definition of done

- [ ] New representation and run implemented and executed against the
      real corpus.
- [ ] Combined ablation report committed, covering all three in-scope
      rows and explicitly deferring the fourth.
- [ ] Config-diff and shape tests pass.

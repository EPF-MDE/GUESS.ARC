# T037 - Ongoing plot threads aggregation (`State(t)` component 7)

## Objective

Implement ongoing-plot-threads aggregation: higher-level arcs/goals in
progress, built by aggregating active conflicts, unresolved questions, and
arc metadata known as of t.

## Context

SPEC §8, component 7: "Contains: higher-level arcs/goals in progress.
Constructed from: aggregation of active conflicts + unresolved questions +
arc metadata known as of t. Allowed inputs: chapters 1..t. Available at
prediction time: yes, in whatever simplified form v1 implements (full
fidelity is Later scope, §25)." This is explicitly the simplest, most
aggregation-only of the nine components — a thin join over three already-
built sources, not new extraction.

## Scope

- `ncp.state.plot_threads.PlotThread`: `label` (derived from arc metadata,
  e.g. chapter t's `arc` front-matter field, per T002), `open_conflicts`,
  `open_questions`.
- `ncp.state.plot_threads.ongoing_threads_as_of(conflicts: list[Conflict], questions: list[UnresolvedQuestion], corpus: Corpus, t: int) -> list[PlotThread]`:
  groups T034's active conflicts and T036's unresolved questions by the
  `arc` metadata of their originating chapter (chapters `<= t` only, read
  via T002's parsed front-matter).

## Non-goals

- Do not implement full-fidelity thread tracking (cross-arc thread
  continuity, thread importance scoring) — explicitly **Later** (§25).
- Do not introduce any extraction step not already covered by T034/T036 —
  this ticket is aggregation only.

## Inputs

- T034 (active conflicts), T036 (unresolved questions), T002 (arc
  metadata).

## Outputs

- `src/ncp/state/plot_threads.py`

## Acceptance criteria

- `ongoing_threads_as_of` never includes a conflict/question with
  `opened_at`/`raised_at > t` (inherited correctness from T034/T036 — this
  ticket must not introduce a new path that bypasses their filtering).
- Grouping by `arc` metadata correctly reflects each chapter's own
  front-matter `arc` field, read only for chapters `<= t`.

## Tests

- Unit test with synthetic conflicts/questions across two arcs, asserting
  correct grouping.
- A test confirming this function calls T034/T036's `_as_of` functions
  (not independent, un-filtered data) — i.e. it cannot "accidentally"
  re-derive active/unresolved status with different (buggier) logic.

## Dependencies

T034, T036, T002.

## Risks

- **Temporal causality:** low direct risk since this ticket performs no
  new extraction — but it must not reimplement filtering independently
  (e.g. recomputing "active" status inline instead of calling T034), which
  would create a second, potentially inconsistent leakage-guard surface to
  maintain. The reuse test above guards this.

## Definition of done

- [ ] `PlotThread`, `ongoing_threads_as_of` implemented.
- [ ] All listed tests pass.

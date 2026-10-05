# T034 - Active conflicts tracking (`State(t)` component 4)

## Objective

Implement active-conflict tracking: antagonistic situations introduced in
chapters 1..t and not yet matched with a resolution event within 1..t.

## Context

SPEC §8, component 4: "Contains: antagonistic situations introduced, not
yet resolved as of t. Constructed from: event candidates (§10 Layer 2)
tagged conflict-initiating, with no matching resolution event in 1..t.
Allowed inputs: chapters 1..t. Classification: feature." This is the first
`State(t)` component that consumes Layer 4 event labels (T015) as its raw
material, rather than extracting independently from chapter text.

## Scope

- Extend T015/T012's taxonomy with a `conflict_role` tag per category
  (`initiating` / `resolving` / `neutral`) — a small, versioned mapping
  (e.g. `combat_strike` → initiating, `combat_resolution` → resolving),
  stored alongside the taxonomy, not hard-coded inline, so it is reviewable
  and versioned the same way the taxonomy itself is.
- `ncp.state.conflicts.Conflict`: `participants`, `opened_at`, `resolved_at: int | None`.
- `ncp.state.conflicts.active_conflicts_as_of(labels: list[EventLabels], taxonomy_roles: dict[str, str], t: int) -> list[Conflict]`:
  matches each `initiating` event (chapter `<= t`) to the earliest
  `resolving` event involving overlapping participants at a later chapter
  `<= t`; conflicts with no such match by `t` are "active."

## Non-goals

- Do not implement full-fidelity conflict/plot modeling (narrative nuance
  beyond initiating/resolving tags) — a simplified heuristic is explicitly
  acceptable; full fidelity for unresolved plotlines generally is **Later**
  (§12, §25).
- Do not build the `conflict_role` tagging as a separate ML classifier —
  a small reviewed mapping table is sufficient for v1.

## Inputs

- T015 (event labels), T012 (taxonomy categories to tag).

## Outputs

- `src/ncp/state/conflicts.py`, a `conflict_roles.yaml`-style mapping
  artifact versioned alongside the taxonomy.

## Acceptance criteria

- `active_conflicts_as_of(labels, roles, t)` never includes a conflict
  whose `opened_at > t`, and never marks a conflict resolved using a
  resolution event at a chapter `> t`.
- A conflict opened at chapter 10 and resolved at chapter 20 is active for
  `t` in `[10, 19]` and inactive (resolved) for `t >= 20`.
- Re-evaluating at an earlier `t` after appending later chapters' labels
  returns an unchanged result (monotonicity-of-the-past).

## Tests

- Unit test with a synthetic opened/resolved pair, asserting the active
  window above.
- Monotonicity-of-the-past test.
- A test that a conflict with no matching resolution anywhere in the
  corpus remains active at every `t >= opened_at`.

## Dependencies

T015.

## Risks

- **Temporal causality:** the resolution-matching step must only consider
  resolving events at chapters `<= t` — the most likely bug is scanning
  the full label table for "the" resolution regardless of `t`, which would
  make a conflict's active/resolved status depend on the full corpus
  rather than on what is knowable at `t`. The monotonicity test is the
  direct guard.

## Definition of done

- [ ] `conflict_roles` mapping committed and versioned.
- [ ] `Conflict`, `active_conflicts_as_of` implemented.
- [ ] All listed tests pass.

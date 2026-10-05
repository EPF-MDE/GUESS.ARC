# T036 - Unresolved questions tracking (`State(t)` component 6)

## Objective

Implement unresolved-questions tracking: mysteries raised in 1..t and not
textually answered by t, as a partial/heuristic v1 component, reusing
T034's resolution-matching pattern.

## Context

SPEC §8, component 6: "Contains: mysteries raised and not textually
answered by t. Constructed from: question-raising events/statements in
1..t minus those with a matching resolution event in 1..t (ties to §12).
Allowed inputs: chapters 1..t — resolution must never be detected by
reading chapters beyond t. Classification: feature; also raw material for
the resolved-vs-open diagnostic in §19 (evaluation-only in that use)."
Listed among the partial/heuristic-acceptable components (§8).

## Scope

- Reuse T034's `conflict_roles`-style pattern but for a `question_role` tag
  (`raising` / `answering`) on taxonomy categories, versioned the same way.
- `ncp.state.questions.UnresolvedQuestion`: `topic`, `raised_at`,
  `answered_at: int | None`.
- `ncp.state.questions.unresolved_questions_as_of(labels, roles, t) -> list[UnresolvedQuestion]`:
  same matching logic shape as T034's `active_conflicts_as_of` (raising
  event with no matching answering event at or before t).

## Non-goals

- Do not implement full-fidelity plotline/mystery tracking — explicitly
  simplified for v1 (§12: "v1 may implement only the simplified version
  already covered by `State(t)` components 6–7").
- Do not use this component's output for the §19 resolved-vs-open
  diagnostic in this ticket — §8 explicitly marks that use
  "evaluation-only," which belongs to EPIC-08 Part 2 (T053), not here;
  this ticket only produces the feature.

## Inputs

- T034 (shared matching-logic pattern, taxonomy role-tagging convention),
  T015 (event labels).

## Outputs

- `src/ncp/state/questions.py`, a `question_roles.yaml`-style mapping.

## Acceptance criteria

- `unresolved_questions_as_of(labels, roles, t)` never includes a question
  whose `raised_at > t`, and never marks a question answered using an
  answering event at a chapter `> t`.
- Monotonicity-of-the-past holds (same test pattern as T034).

## Tests

- Unit test mirroring T034's raised/answered pair test.
- Monotonicity-of-the-past test.

## Dependencies

T034, T015.

## Risks

- **Temporal causality:** identical risk class to T034 — "resolution must
  never be detected by reading chapters beyond t" is stated explicitly in
  SPEC §8 for this component. Reusing T034's already-tested matching logic
  (rather than writing new logic from scratch) directly reduces this risk.

## Definition of done

- [ ] `question_roles` mapping committed.
- [ ] `UnresolvedQuestion`, `unresolved_questions_as_of` implemented.
- [ ] All listed tests pass.

# T039 - Important objects/goals tracking (`State(t)` component 9)

## Objective

Implement important-objects/goals tracking: artifacts, Devil Fruits, and
stated goals introduced and still relevant as of t, with the same status
logic used for characters — as a full-fidelity v1 component.

## Context

SPEC §8, component 9: "Contains: artifacts, Devil Fruits, stated goals
introduced and still relevant as of t. Constructed from: entity/event
extraction restricted to chapters 1..t, tracked with the same status logic
as characters. Allowed inputs: chapters 1..t. Classification: feature."
Listed among the four full-fidelity v1 components (§8).

## Scope

- `ncp.state.objects.ObjectStatus`: reuse T031's `CharacterStatus`-shaped
  ontology (`introduced`/`active`/`inactive`/`deceased`-analog e.g.
  "destroyed"/"lost"/`unknown`) — share the enum/logic where semantically
  identical, per "no unnecessary rewrites."
- `ncp.state.objects.extract_object_mentions(chapter: ChapterRecord, *, extraction_version: str) -> list[ObjectCandidate]`:
  per-chapter extraction (T010 pattern) of named objects/goals (Devil
  Fruits, named weapons/ships already partially covered by the chapter's
  own front-matter where available, plus free-text mentions of stated
  goals, e.g. "find the One Piece," "become Pirate King").
- `ncp.state.objects.object_status_as_of(name, corpus, t, **params) -> ObjectStatus`
  mirroring T031's interface shape exactly.

## Non-goals

- Do not build a separate status ontology from scratch if T031's is
  directly reusable with renamed terminal states — reuse its tested
  monotonicity-of-the-past logic.
- Do not attempt canonical Devil-Fruit/weapon disambiguation beyond
  name-string matching — out of scope for v1.

## Inputs

- T031 (status-ontology logic to reuse/share), T010 (extraction pattern),
  T002 (chapter text/front-matter).

## Outputs

- `src/ncp/state/objects.py`

## Acceptance criteria

- `object_status_as_of` satisfies the same guarantees as T031's
  `character_status_as_of`: never reads beyond `t`, and is safe even when
  given a corpus containing chapters beyond `t`.
- `extract_object_mentions` reads only its one input chapter.

## Tests

- Unit tests mirroring T031's five-status and monotonicity-of-the-past
  tests, adapted to object/goal terminal states.
- Single-chapter-input test for the extractor.

## Dependencies

T031, T010, T002.

## Risks

- **Temporal causality:** identical risk class and identical mitigation to
  T031 — reusing T031's already-tested logic directly reduces the chance
  of a subtly different, unguarded status computation for objects.

## Definition of done

- [ ] `ObjectStatus`, `extract_object_mentions`, `object_status_as_of`
      implemented, sharing logic with T031 where applicable.
- [ ] All listed tests pass.

# T032 - Relationship extraction with `evidenced_at` (§11, `State(t)` component 2)

## Objective

Implement typed relationship extraction (e.g. `ally_of`, `enemy_of`,
`sibling_of`) between entity pairs, each tagged with `evidenced_at` — the
first chapter where the relation became textually explicit — and a filter
making a relation available in `State(t)` iff `evidenced_at <= t`.

## Context

SPEC §11: "Contains: typed edges between two entities... each with
`evidenced_at`... `evidenced_at` must be the first chapter where the
relation became explicit, never inferred later and back-dated... a
relation is available for predicting t+1 only if `evidenced_at <= t`." SPEC
§8, component 2, worked example: "if a relationship becomes explicit in
chapter 500, it must be absent from `State(100)` and `State(499)`, and
present from `State(500)` onward." SPEC §8 explicitly allows this component
to be "partial/heuristic in v1."

## Scope

- `ncp.state.relations.Relation`: `entity_a`, `entity_b`, `relation_type`,
  `evidenced_at: int`.
- `ncp.state.relations.extract_relations(chapter: ChapterRecord, *, extraction_version: str) -> list[Relation]`:
  per-chapter co-occurrence/text-pattern extraction (reuse T010's
  discipline: one chapter in, versioned, deterministic), restricted to
  character pairs present in that chapter's own front-matter list.
- `ncp.state.relations.relations_as_of(all_relations: list[Relation], t: int) -> list[Relation]`:
  filters to `evidenced_at <= t`, with **first-occurrence** semantics
  enforced by construction: when the same `(entity_a, entity_b,
  relation_type)` is extracted from multiple chapters, keep only the
  earliest `evidenced_at` (a relation cannot become "more explicit" twice
  for `evidenced_at` purposes — first mention wins).

## Non-goals

- Do not build a standalone relation-prediction model — §11: "exploratory
  in v1, deferred past core scope... as a standalone prediction target."
  Relations here are only ever a `State(t)` feature ingredient.
- Do not achieve full-fidelity relation-type coverage — partial/heuristic
  is explicitly acceptable (§8).

## Inputs

- T010 (extraction-procedure pattern), T002 (per-chapter character lists).

## Outputs

- `src/ncp/state/relations.py`

## Acceptance criteria

- `relations_as_of(relations, t)` never returns a relation whose earliest
  `evidenced_at` exceeds `t`.
- `extract_relations` run on chapter `c` reads only chapter `c`'s own text/
  front-matter — never any other chapter (checked by signature and test,
  same pattern as T010).
- Re-running extraction deterministically on the same chapter yields the
  same relations with the same `evidenced_at`.

## Tests

- Unit test with a synthetic relation first appearing in chapter 10 and
  again (same type) in chapter 50 — `relations_as_of` at `t=10..49` must
  include it with `evidenced_at=10`; at `t=9` it must be absent.
- Determinism test.
- Single-chapter-input test (signature/behavior check, mirroring T010).

## Dependencies

T010, T002.

## Risks

- **Temporal causality — this ticket's `evidenced_at` discipline is the
  exact mechanism SPEC §8/§26 calls out by name** ("Relationship
  `evidenced_at` extraction mechanism | how first-explicit-chapter is
  detected/verified | building §8 component 2 / §11"). The main failure
  mode is "back-dating" — e.g. inferring from chapter 500 that two
  characters "must have been allies since chapter 200" and setting
  `evidenced_at=200`. This ticket's extraction must only ever set
  `evidenced_at` to the chapter where the relation was *itself* being
  processed, never an inferred earlier chapter — enforced by the
  single-chapter-input constraint.

## Definition of done

- [ ] `Relation`, `extract_relations`, `relations_as_of` implemented.
- [ ] All listed tests pass, including the back-dating guard (first-mention
      test above).

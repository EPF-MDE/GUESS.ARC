# T015 - Layer 4 final event label generation

## Objective

Apply a frozen/incremental taxonomy (T012/T013) to every chapter's Layer 2
candidates (T010), producing the versioned, per-chapter multi-label event
target that is the project's **primary prediction target** (SPEC §5).

## Context

SPEC §10, Layer 4: "Contains: per-chapter supervised event labels, from
applying the frozen/incremental taxonomy to that chapter's candidates.
Constructed from: Layers 1–3, versioned (extraction version + taxonomy
version)... Classification: primary prediction target (chapter t+1) /
feature (chapters ≤t, via `State(t)`)." This is the first artifact in the
project that is simultaneously a training *target* (for t+1) and a
*feature* (for history chapters, via EPIC-05's component 8) — both roles
must be served by the same underlying table to avoid two divergent
definitions of "event label" existing in the codebase.

## Scope

- `ncp.annotations.layer4.EventLabels`: `chapter: int`, `labels: frozenset[str]`
  (canonical category names from the active `EventTaxonomy`),
  `taxonomy_version: str`, `extraction_version: str`.
- `generate_labels(chapter_candidates: Mapping[int, list[EventCandidate]], taxonomy: EventTaxonomy) -> list[EventLabels]`:
  for each chapter, classify its own candidates via
  `taxonomy.classify(candidate)` and collect the resulting label set
  (deduplicated; a chapter can carry multiple distinct event-category
  labels, matching "multi-label next-event prediction," §1, `CLAUDE.md`).
- A chapter with zero candidates yields an empty label set, not an error —
  explicitly reportable, matching Layer 1/2's "zero is a fact" convention
  (T009).

## Non-goals

- Do not re-run taxonomy construction here — this ticket only *applies* an
  already-built `EventTaxonomy` (T012/T013's output); it must accept the
  taxonomy as a parameter, never build one internally.
- Do not decide the frequency threshold for "model individually vs. other"
  — that is T016, applied as a post-processing step over this ticket's
  output, not inside `generate_labels`.

## Inputs

- T010 (candidates for every chapter), T012/T013 (a built `EventTaxonomy`).

## Outputs

- `src/ncp/annotations/layer4.py`

## Acceptance criteria

- Every chapter in the corpus has exactly one `EventLabels` row.
- Labels are drawn only from the supplied taxonomy's category set (plus
  `other`) — no label string can appear that is not one of the taxonomy's
  known categories.
- `EventLabels` for chapter t+1, when used as a training target, and for
  chapters ≤t, when used as a `State(t)` feature (EPIC-05 T038), both read
  from literally the same generated table — verified by a test that
  constructs one `EventLabels` list and passes it to both consumers'
  interfaces.

## Tests

- Unit test on a small synthetic candidate+taxonomy pair with hand-computed
  expected labels.
- Test that a chapter with zero candidates produces an empty label set, not
  a crash or a missing row.
- A test asserting `taxonomy_version`/`extraction_version` are correctly
  propagated and non-empty on every row (§21 provenance requirement).

## Dependencies

T012, T010.

## Risks

- **Temporal causality:** low *within* this ticket (it only ever reads a
  chapter's own candidates, classified by an already-frozen/already-scoped
  taxonomy) — but it is the ticket that makes every upstream leakage risk
  (T010's extraction, T012/T013's construction-set discipline) materialize
  as a concrete label. Any upstream leakage becomes a Layer 4 leak here.
  This ticket's own guard is simply never calling taxonomy construction
  itself — enforced by the function signature requiring a pre-built
  `EventTaxonomy`.

## Definition of done

- [ ] `generate_labels` implemented and tested.
- [ ] Full-corpus run completes, producing one row per chapter with
      non-empty version tags.
- [ ] A smoke check confirms the same table serves both the T021+ target
      role and the T038 feature role without duplication.

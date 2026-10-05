# T033 - Location tracking (`State(t)` component 3)

## Objective

Implement location tracking: the current/recent narrative setting(s) of the
active cast as of chapter t, built with full fidelity per SPEC §8's v1
scope.

## Context

SPEC §8, component 3: "Contains: current/recent narrative setting(s) of the
active cast. Constructed from: location mentions in chapters 1..t.
Allowed inputs: chapters 1..t. Available at prediction time: yes.
Classification: feature." Listed among the four components v1 implements
"with full fidelity" (components 1, 3, 8, 9).

## Scope

- `ncp.state.locations.Location`: a named setting with `first_mentioned_at`,
  `last_mentioned_at` (both as-of-t-dependent, recomputed per query, not
  stored mutable state).
- `ncp.state.locations.extract_location_mentions(chapter: ChapterRecord, *, extraction_version: str) -> list[str]`:
  per-chapter location-mention extraction (reuse T010's discipline;
  location names can come from `AnnotationConfig.entity_labels` matching
  `GPE`/`LOC` if spaCy is available, falling back to a regex/gazetteer
  approach per `AnnotationConfig.entity_backend == "auto"`'s existing
  fallback convention).
- `ncp.state.locations.current_locations_as_of(corpus, t, *, recency_window: int) -> list[str]`:
  locations mentioned within the recency window ending at t, ordered by
  recency.

## Non-goals

- Do not attempt to resolve location hierarchy/geography (e.g. "this
  island is part of this sea") — out of scope; a flat recency-ranked list
  satisfies §8's "current/recent... setting(s)" wording for v1.

## Inputs

- T010 (extraction pattern), T002 (chapter text).

## Outputs

- `src/ncp/state/locations.py`

## Acceptance criteria

- `extract_location_mentions` reads only its one input chapter.
- `current_locations_as_of(corpus, t, ...)` never reflects a location
  first mentioned after chapter `t`.
- Re-evaluating at an earlier `t` after the corpus gains later chapters
  returns an unchanged result (same monotonicity-of-the-past guarantee as
  T031).

## Tests

- Unit test with synthetic location mentions across chapters, asserting
  `current_locations_as_of` excludes a location introduced after `t`.
- Monotonicity-of-the-past test (same pattern as T031).
- Single-chapter-input test for the extractor.

## Dependencies

T010, T002.

## Risks

- **Temporal causality:** same class as T031/T032 — the recency window
  must be computed strictly from `<= t`; the monotonicity test is the
  concrete guard.

## Definition of done

- [ ] `Location`, `extract_location_mentions`,
      `current_locations_as_of` implemented.
- [ ] All listed tests pass.

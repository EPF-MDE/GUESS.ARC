# T012 - Layer 3 taxonomy construction — frozen mode

## Objective

Implement "frozen" taxonomy construction: cluster/normalize Layer 2
candidates drawn **only** from a designated construction set (e.g. the
train split) into a versioned set of canonical event categories, with an
`other` fallback for unmapped future candidates.

## Context

SPEC §10, Layer 3: "(a) Frozen — built once from a designated construction
set (e.g. the train split or an initial chapter prefix), then frozen, with
a defined fallback (`other`) for unmapped future candidates... never the
full corpus including test chapters, in either mode, for any number
reported as a final result." SPEC §26 lists the frozen-vs-incremental
choice as open; this ticket implements frozen mode as v1's primary path
(cheaper, matches the "initial recommendation" framing elsewhere in SPEC),
with T013 as an optional incremental extension behind the same interface.

## Scope

- `ncp.annotations.layer3.EventTaxonomy`: versioned artifact
  (`taxonomy_version: str`, `categories: dict[str, CategorySpec]`, an
  `other` category always present, `construction_set_id: str` recording
  exactly which chapters built it).
- `build_frozen_taxonomy(candidates: Iterable[EventCandidate], *, construction_set_id: str, taxonomy_version: str) -> EventTaxonomy`:
  normalizes candidate `event_type`/`evidence` text (embedding or
  lexical clustering — simplest viable approach: TF-IDF/embedding + a
  clustering algorithm already available via `scikit-learn`, matching the
  core dependency list in `pyproject.toml`; no new heavy dependency
  required for v1), assigns a canonical label per cluster, and freezes the
  result.
- `EventTaxonomy.classify(candidate: EventCandidate) -> str`: maps a new
  candidate (from any chapter, including beyond the construction set) to
  its nearest frozen category or `other` if below a similarity threshold.
- Use T004's cache utility, keyed on `construction_set_id`, since this is
  exactly the "expensive intermediate artifact" §21 names.
- Explicit required argument `construction_set_id` — no default, per §15.

## Non-goals

- Do not implement incremental (rebuild-per-origin) mode — T013.
- Do not decide the final construction set (train split vs. "initial
  chapter prefix") as a permanent research choice — implement both as
  valid inputs (any `Iterable[EventCandidate]` the caller has already
  filtered), with the caller (T019/T045+) deciding which to pass.
- Do not pick final category count/granularity as a fixed research
  deliverable — expose it as a tunable parameter with a documented default.

## Inputs

- T010 (candidates), T005 (train split boundary, to filter candidates
  before calling this function), T004 (cache).

## Outputs

- `src/ncp/annotations/layer3.py`

## Acceptance criteria

- `build_frozen_taxonomy` never reads any candidate whose `chapter` is
  outside the caller-supplied iterable — the function itself has no
  corpus-wide access, so leakage can only enter via the caller passing a
  bad iterable (checked by T014).
- `EventTaxonomy.classify` runs on candidates from any chapter, including
  ones chronologically after the construction set, without raising (falls
  back to `other`).
- Two calls with the same candidates and `taxonomy_version` produce
  identical categories (determinism, modulo a fixed random seed where
  clustering is stochastic).

## Tests

- Unit test building a taxonomy from a small synthetic candidate set with
  known clusters, asserting the expected category count and that an
  obviously-unrelated held-out candidate maps to `other`.
- Determinism test with a fixed seed.
- Cache round-trip test via T004.

## Dependencies

T010, T005, T004.

## Risks

- **Temporal causality — the central risk SPEC §10 names explicitly:**
  "Building the taxonomy from the full corpus and evaluating on the same
  chapters is a leakage path even though no single label reads chapter
  t+1's text directly — the vocabulary itself would have seen the future."
  This ticket's function signature forces an explicit candidate iterable
  and `construction_set_id`, but cannot itself stop a caller from passing
  the full corpus's candidates — T014 is the dedicated guard ticket that
  tests the *caller contract*, and every future caller of this function
  (T015, T019, T045+) must be reviewed against it.

## Definition of done

- [ ] `build_frozen_taxonomy` and `EventTaxonomy.classify` implemented.
- [ ] Determinism and cache tests pass.
- [ ] `construction_set_id` is a required, non-defaulted parameter in the
      function signature (enforced by the type checker / no default value).

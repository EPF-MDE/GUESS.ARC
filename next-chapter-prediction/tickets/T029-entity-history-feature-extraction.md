# T029 - Entity-history feature extraction (§9, Tier C)

## Objective

Implement the entity-history feature extractor that turns a
`ForecastingExample`'s history window's per-chapter character lists (SPEC
§9) into a fixed-shape feature vector — the entity-aware ingredient that
distinguishes Tier C from Tier B.

## Context

SPEC §13, Tier C: "Tier B features + entity representation (§9, history
only) | same classifier family | yes | tests H3." SPEC §9: "Contains:
per-chapter character list with faction and appearance annotation...
Constructed from: direct parsing of chapter t's own front-matter...
Allowed inputs: only chapter t's own front-matter when representing chapter
t... as history (chapters ≤t): feature." This ticket uses the *raw*
per-chapter character list (§9), not the richer status ontology EPIC-05
builds for Tier D — see EPIC-04's epic file for why these are intentionally
different granularities.

## Scope

- `ncp.representations.entities.entity_history_features(example: ForecastingExample, corpus: Corpus) -> dict[str, float]`:
  for each character appearing in any history chapter, a feature such as
  "appeared in history window" (binary) and "appearance count within
  window" (integer/normalized), keyed by a stable vocabulary (characters
  seen across the construction set — **fit** this vocabulary the same way
  T026 fits its TF-IDF vocabulary: only from construction-set examples,
  with an explicit `construction_set_id` argument and an `other`/unknown
  bucket for characters never seen in the construction set).
- `EntityVocabulary.fit(examples: Sequence[ForecastingExample], corpus, *, construction_set_id: str)` /
  `.transform(example) -> dict[str, float]`, mirroring T026's `fit`/
  `transform` shape so T030 can treat both encoders uniformly.
- Cache the fitted vocabulary via T004.

## Non-goals

- Do not implement the character status ontology
  (`introduced`/`active`/`inactive`/`deceased`/`unknown`) — that is
  EPIC-05's T031, a different, richer construction for Tier D.
- Do not read the target chapter's character list here — that is T008's
  target-builder role, a completely separate call site.

## Inputs

- T008 (per-chapter character-list access pattern, reused for history
  rather than target), T007 (`ForecastingExample`).

## Outputs

- `src/ncp/representations/entities.py`

## Acceptance criteria

- `fit` only ever reads character lists from history chapters of
  construction-set examples — never the target chapter of any example,
  never any chapter outside the construction set.
- `transform` on a val/test example works correctly even for a character
  never seen during `fit` (falls into the unknown bucket, does not crash).
- Feature vectors have a fixed, vocabulary-determined length across all
  examples once fit.

## Tests

- Unit test on a synthetic 3-chapter history with known characters,
  asserting correct binary/count features.
- Unknown-character test (val/test example introduces a character absent
  from the fit vocabulary).
- Leakage test: `fit` instrumented to confirm it never reads a target
  chapter's character list or any chapter outside the construction set.

## Dependencies

T008, T007.

## Risks

- **Temporal causality:** the key risk is accidentally fitting the entity
  vocabulary on the full corpus (including test-split characters who first
  appear only in later chapters) rather than the construction set — this
  would let the model "know" a character exists before they are
  chronologically introduced in the train data. The leakage test directly
  guards this.

## Definition of done

- [ ] `EntityVocabulary` and `entity_history_features` implemented.
- [ ] All listed tests pass.

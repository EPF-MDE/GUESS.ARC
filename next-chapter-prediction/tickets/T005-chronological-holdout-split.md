# T005 - Chronological holdout split + leakage guard tests

## Objective

Implement the chronological holdout split (train/val/test by chapter order)
driven by `ForecastingConfig.split_ratios` / explicit chapter cut points, and
a dedicated suite of tests proving it can never produce a random split.

## Context

SPEC §16: "Strictly chronological; boundaries configurable via
`ForecastingConfig.split_ratios` / explicit chapter cut points — never
hard-coded in analysis code... Chronological holdout — one fixed train/val/
test boundary." SPEC §6(a): "Random train/test splits are forbidden." This
is the single mechanism every later construction-set argument (T012's
taxonomy, T026's vectorizer fit) ultimately points at.

## Scope

- `ncp.data.splits.chronological_holdout(corpus: Corpus, config: ForecastingConfig) -> SplitBoundaries`
  where `SplitBoundaries` holds, per book, the train/val/test chapter index
  ranges, computed from `split_ratios` by chapter **count** (not random
  sampling) in index order, or from an explicit cut-point list if one is
  supplied in config (extend `ForecastingConfig` only if a field is missing
  — check `split_ratios`/`split_strategy` first, since they may already
  suffice).
- A `SplitBoundaries.as_of(chapter: int) -> Literal["train","val","test"]`
  lookup and a `.construction_set_id() -> str` stable identifier for use as
  a `ConstructionSetKey` (T004).
- Validate `split_strategy == "chronological"` is honored; raise
  `ConfigError` (reusing the existing class) if ratios don't sum to 1 — this
  check may already exist in `Config.validate()`; reuse it, don't duplicate.

## Non-goals

- Do not implement rolling-origin here — that is T006, built on top of this
  ticket's boundary primitives.
- Do not resolve SPEC §26's "exact chronological split boundaries" research
  question — implement the ~80/10/10 default from §16 and leave it fully
  configurable; do not hard-code a specific chapter number anywhere in code.

## Inputs

- T002 (loaded corpus), T003 (validated corpus — split only a validated
  corpus).
- `src/ncp/config/schema.py` (`ForecastingConfig`).

## Outputs

- `src/ncp/data/splits.py` (`SplitBoundaries`, `chronological_holdout`).

## Acceptance criteria

- For a corpus of N contiguous chapters and ratios `(0.8, 0.1, 0.1)`, train
  is chapters `[1, floor(0.8N)]`, val and test are the next contiguous
  blocks in order — never interleaved, never shuffled.
- `as_of(t)` for every `t` in train returns `"train"`; no chapter appears in
  two splits.
- Changing `split_ratios` changes the boundary without any code edit.

## Tests

- Property test: for 50 random valid `split_ratios` tuples, every chapter
  index is assigned to exactly one split, and all train indices are less
  than all val indices, which are less than all test indices.
- Explicit **leakage guard test**: assert that `chronological_holdout` has
  no code path that calls any shuffling/sampling function (can be checked
  via a dedicated test that monkey-patches `random`/`numpy.random` calls to
  raise if invoked during the split).
- Test that an explicit chapter cut point (if supported) is honored exactly.

## Dependencies

T002, T003.

## Risks

- **Temporal causality — primary risk of this ticket.** This is the
  function every leakage guarantee in the project traces back to. Any bug
  here (off-by-one at the boundary, accidental shuffle, ratio applied to a
  shuffled index list instead of the sorted one) invalidates every
  downstream result. Mitigation: the property test above, run on every CI
  pass, not just once.

## Definition of done

- [ ] `chronological_holdout` implemented and used by nothing yet except its
      own tests (consumers come in T007+).
- [ ] Property test and leakage guard test both pass.
- [ ] `construction_set_id()` is deterministic across repeated calls with
      the same config.

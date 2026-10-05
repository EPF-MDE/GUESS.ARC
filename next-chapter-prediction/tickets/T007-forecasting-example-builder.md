# T007 - Forecasting example builder (history window → t+1)

## Objective

Build the function that turns a validated, split corpus into concrete
forecasting examples: `(history = chapters [t-k+1..t], target_chapter = t+1)`
pairs, respecting `history_size`, `min_history`, `stride`, and `horizon`.

## Context

SPEC §1/§5: the pipeline is "chapters 1...t → representation → prediction of
events in chapter t+1." SPEC §6(a): "For target chapter t+1, every feature
must be constructed exclusively from chapters 1..t." The existing
`ForecastingConfig` already declares `history_size`, `min_history`,
`stride`, `horizon`, `require_contiguous` — this ticket is where those
fields are first consumed by real logic.

## Scope

- `ncp.forecasting.examples.ForecastingExample`: a dataclass with
  `book_id`, `target_index` (= t+1), `history_indices` (tuple of chapter
  indices ≤ t, ascending), `split` (`"train"|"val"|"test"`, from T005/T006's
  boundaries).
- `build_examples(corpus: Corpus, boundaries: SplitBoundaries, config: ForecastingConfig) -> list[ForecastingExample]`:
  for each candidate `t+1` (offset by `config.horizon`), compute history as
  the `history_size` most recent chapters ≤ t (or all available if
  `history_size == 0`), skip if fewer than `min_history` are available,
  apply `stride` to the set of `t` values considered, and if
  `require_contiguous` is set, skip windows with gaps.
- Each example's `split` is assigned from the **target** chapter's split
  membership (an example belongs to whichever split its *prediction target*
  falls in) — history chapters may span an earlier split only by
  chronology, never by construction choice.

## Non-goals

- Do not attach any features/representations to the example yet — this
  ticket only produces chapter-index tuples; EPIC-04/05 attach features.
- Do not attach labels yet — EPIC-02's T015 (event labels) and T008
  (entity labels) are separate tickets; this one only defines which
  chapters are inputs vs. target.

## Inputs

- T003 (validated corpus), T005 (`SplitBoundaries`).
- `src/ncp/config/schema.py` (`ForecastingConfig`).

## Outputs

- `src/ncp/forecasting/examples.py`

## Acceptance criteria

- No example's `history_indices` contains any index `>= target_index`.
- No example's `history_indices` contains an index from a later split than
  its own `target_index`'s split (train examples never borrow val/test
  chapters as history, even though val/test examples may borrow train
  chapters as history — that is expected and correct per rolling forecast
  semantics, not a leak, since val/test targets are strictly after train
  chapters chronologically).
- `min_history`, `stride`, `horizon`, `require_contiguous` all visibly
  affect the produced example count/shape in the expected direction.

## Tests

- Unit test on a synthetic 20-chapter corpus verifying example count and
  exact `history_indices` for a few concrete `(history_size, min_history,
  stride, horizon)` combinations, hand-computed.
- **Leakage guard test**: assert, for every example in a real build over the
  full corpus, `max(history_indices) < target_index`.
- Test that `require_contiguous=True` drops a window that would otherwise
  span a gap (constructed synthetically, since the real corpus has no
  gaps per T003).

## Dependencies

T003, T005.

## Risks

- **Temporal causality — direct.** This function is the literal boundary
  between "chapters 1..t" and "chapter t+1" referenced throughout SPEC §6/
  §8/§10/§11/§12. An off-by-one here (e.g. including `t+1` itself in
  history, or computing `horizon` in the wrong direction) silently leaks
  the prediction target into every single downstream feature and label.
  The leakage guard test above must run against the full real corpus, not
  only the synthetic fixture.

## Definition of done

- [ ] `build_examples` implemented and passing all listed tests.
- [ ] Leakage guard test passes against the full real 1193-chapter corpus.
- [ ] Example count for the default config is logged/printed by a smoke
      script for sanity review.

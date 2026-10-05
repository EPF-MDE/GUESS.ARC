# T006 - Rolling-origin split generator

## Objective

Implement the rolling-origin (expanding or sliding window) evaluation
protocol described in SPEC §16, generating multiple forecast origins over
the chronological chapter sequence.

## Context

SPEC §16: "Rolling-origin (expanding or sliding window) — multiple forecast
origins aggregated. Preferred for the final cross-tier comparison; window
type, step size, and number of origins are **[OPEN]** (§26)." SPEC §16's H4
row requires rolling-origin specifically (not holdout alone); several H1/H3
cells require "holdout + rolling-origin." This ticket is what makes those
cells runnable.

## Scope

- `ncp.data.splits.rolling_origin(corpus: Corpus, config: ForecastingConfig, *, window: Literal["expanding","sliding"], step: int, n_origins: int) -> list[SplitBoundaries]`
  reusing T005's `SplitBoundaries` type so every downstream consumer (T019's
  protocol runner) handles both protocols through one interface.
- `expanding`: origin `k`'s train set is chapters `[1, boundary_k]`, growing
  by `step` chapters each origin; `sliding`: train set is a fixed-width
  window sliding forward by `step`. Both produce a val/test block
  immediately following train, sized consistently with `split_ratios`'
  val/test proportions (or an explicit fixed width if configured).
- Expose `window`, `step`, `n_origins` as new fields on `ForecastingConfig`
  if not already present (check the schema first — current `ForecastingConfig`
  has no rolling-origin fields; add them with documented defaults, not
  silently defaulting inside the function).

## Non-goals

- Do not decide the final window type/step/count for the project's reported
  results (SPEC §26 — [OPEN]) — implement the mechanism generically;
  EPIC-08 Part 2 (T050) chooses concrete values when aggregating results.
- Do not implement the aggregation of metrics across origins — that is
  T050; this ticket only produces the list of boundaries.

## Inputs

- T005 (`SplitBoundaries`, chronological primitives).
- `src/ncp/config/schema.py` (`ForecastingConfig`) — to extend.

## Outputs

- `rolling_origin` function in `src/ncp/data/splits.py`.
- New `ForecastingConfig` fields: `rolling_window` (`"expanding"|"sliding"`),
  `rolling_step`, `rolling_n_origins`, with `Config.validate()` extended to
  check them.

## Acceptance criteria

- For `window="expanding"`, origin `k+1`'s train set is a strict superset of
  origin `k`'s train set.
- For `window="sliding"`, every origin's train set has the same chapter
  count.
- No origin's val/test block overlaps its own train block; no origin's test
  block extends past the final chapter.
- `n_origins` origins are produced, or fewer with a clear error/warning if
  the corpus is too short for the requested `step`/`n_origins` combination
  — never a silent wraparound.

## Tests

- Unit tests for both window types verifying the superset/fixed-width
  properties above on a synthetic 100-chapter corpus.
- A test that an origin's test block is always strictly after its own train
  block (no origin can see its own future).
- A test that insufficient chapters for the requested configuration raises
  a clear, typed error rather than producing a malformed origin.

## Dependencies

T005.

## Risks

- **Temporal causality.** Same class of risk as T005: each origin must be
  self-contained (its own train/val/test never overlap, and later origins
  may know more only because they are chronologically later, not because
  of any peeking). A subtle bug here (e.g. `sliding` window computed from
  the wrong end of the corpus) would make an origin's "train" set include
  chapters after its own test set. The overlap/ordering tests above exist
  specifically to catch this.

## Definition of done

- [ ] `rolling_origin` implemented for both window types.
- [ ] New config fields added with validation.
- [ ] All listed tests pass, including the insufficient-corpus error case.

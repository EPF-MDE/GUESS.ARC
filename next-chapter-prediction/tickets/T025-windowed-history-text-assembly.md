# T025 - Windowed-history text assembly

## Objective

Implement the function that turns a `ForecastingExample`'s history window
into a single assembled text blob (with an optional recency-decay weighting
hook), ready for encoding by T026/T027.

## Context

SPEC §13, Tier B: "TF-IDF/embedding of chapter-window summary text." The
existing `RepresentationConfig.recency_decay` field already anticipates
"poids decroissant des chapitres anciens de l'historique" (decaying weight
for older history chapters) — this ticket is the first consumer of that
field. SPEC §17/H2 (context-length) depends on this function correctly
respecting whatever `history_size` the example was built with (T007),
since the sweep varies that parameter.

## Scope

- `ncp.representations.text.assemble_history_text(example: ForecastingExample, corpus: Corpus, config: RepresentationConfig) -> str | list[tuple[str, float]]`:
  concatenates each history chapter's cleaned summary (via the existing
  `PreprocessConfig`-driven cleaning, if already implemented elsewhere in
  the scaffold — otherwise apply `PreprocessConfig` fields directly here:
  lowercase, whitespace collapse, markup/citation stripping) in
  chronological order; when `recency_decay != 1.0`, return a weighted
  per-chapter list instead of a flat string, so T026/T027 can decide how to
  use per-chapter weights (e.g. repeat/weight before TF-IDF, or weighted
  pooling for embeddings).
- Only ever reads `example.history_indices` chapters — never the target.

## Non-goals

- Do not implement the encoder (TF-IDF/embedding) itself — T026/T027.
- Do not implement entity-feature assembly — T029.

## Inputs

- T007 (`ForecastingExample`), T002 (chapter summaries).
- `src/ncp/config/schema.py` (`RepresentationConfig`, `PreprocessConfig`).

## Outputs

- `src/ncp/representations/text.py`

## Acceptance criteria

- Output text/weighted-list is built exclusively from
  `example.history_indices` chapters, in ascending chapter order.
- Varying `history_size` (via different `ForecastingExample`s from T007)
  changes the assembled text length/content accordingly, with no hidden
  cap beyond what `history_size` specifies.
- `recency_decay == 1.0` (no decay) produces a plain concatenated string;
  any other value produces the weighted form — both paths tested.

## Tests

- Unit test on a synthetic 5-chapter history asserting exact concatenation
  order and content.
- Test that the target chapter's own text never appears in the assembled
  output, even when adjacent to the last history chapter.
- Test for both the flat-string and weighted-list output paths.

## Dependencies

T007, T002.

## Risks

- **Temporal causality:** direct — this function is the first point where
  "history text" becomes a literal string a model will see. A bug that
  includes the target chapter's text (e.g. an off-by-one against
  `history_indices`) would leak the entire future chapter's prose into
  every representation downstream. The target-never-appears test is the
  key guard.

## Definition of done

- [ ] `assemble_history_text` implemented for both decay paths.
- [ ] All listed tests pass.

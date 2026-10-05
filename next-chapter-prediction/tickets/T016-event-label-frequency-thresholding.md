# T016 - Event label frequency thresholding

## Objective

Compute per-category event-label frequency over the designated construction
set and apply a configurable, documented threshold deciding which
categories are modeled individually versus folded into `other`.

## Context

SPEC §26: "Event label frequency threshold — which event types are
frequent enough to model individually vs. `other` — needed before:
finalizing Layer 4 labels." SPEC §23 names "class imbalance" as a research
risk: "long-tailed event/entity distributions affect metric choice and may
require frequency thresholds." This ticket resolves the [OPEN] decision as
a configurable mechanism with a documented default, not as a final,
unchangeable research conclusion.

## Scope

- `ncp.annotations.thresholding.category_frequencies(labels: list[EventLabels], *, construction_set_id: str) -> dict[str, int]`:
  counts label occurrences **only** over chapters in the supplied
  construction set.
- `apply_frequency_threshold(labels: list[EventLabels], frequencies: dict[str, int], *, min_count: int) -> list[EventLabels]`:
  remaps any label below `min_count` occurrences in the construction set to
  `other`, for every chapter (not only construction-set chapters — the
  threshold decision, once made from train data, applies uniformly going
  forward, same discipline as T012's frozen taxonomy).
- Add `min_category_count` (or equivalent) to `AnnotationConfig` or a new
  `TaxonomyConfig` section, with a documented default and no silent
  fallback to "no threshold."
- Produce a frequency report (category → count, sorted) for manual review,
  since choosing `min_count` is a judgment call this ticket must make
  visible, not hide inside a magic number.

## Non-goals

- Do not pick the one "correct" threshold as an immutable constant —
  implement it as a config value with a documented, justified default;
  record the chosen default's rationale in the report, not just in a code
  comment.
- Do not re-run taxonomy construction (T012) — this ticket only
  post-processes already-generated Layer 4 labels (T015).

## Inputs

- T015 (generated labels), T005 (construction-set boundary for frequency
  counting).

## Outputs

- `src/ncp/annotations/thresholding.py`
- A frequency report artifact (e.g. `experiments/reports/event_label_frequencies.json`).

## Acceptance criteria

- `category_frequencies` counts only construction-set chapters — a label
  occurring 1000 times in the test split but 0 times in train is reported
  as frequency 0 (test-split frequency must never influence the threshold
  decision).
- Applying the threshold is idempotent (applying it twice yields the same
  result as once).
- The report clearly lists which categories were folded into `other` and
  why (count below `min_count`).

## Tests

- Unit test with a synthetic label set and known frequencies, asserting
  correct remapping at a given `min_count`.
- Test that frequencies computed over a construction set exclude any label
  occurrence outside it, using a synthetic corpus with a deliberately
  frequent test-split-only category that must not count.
- Idempotency test.

## Dependencies

T015.

## Risks

- **Temporal causality:** the central risk is computing "frequency" over
  the full corpus instead of the construction set, which would let the
  test split's distribution influence which categories get modeled
  individually — a textbook taxonomy-adjacent leak per §8's general rule.
  The construction-set-only counting test directly guards this.
- **Class imbalance (§23):** explicitly an accepted, expected characteristic
  of this data, not a defect to "fix" beyond this configurable threshold.

## Definition of done

- [ ] `category_frequencies` and `apply_frequency_threshold` implemented.
- [ ] Config field added with a documented default.
- [ ] Frequency report generated against the real train split and reviewed.
- [ ] All listed tests pass.

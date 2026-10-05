# T028 - Tier B leakage guard tests

## Objective

Write a dedicated test suite proving that every Tier B encoder (TF-IDF,
sentence-embedding) is fit exclusively on construction-set text in every
real call site, and that cached artifacts are never reused across
incompatible construction sets.

## Context

SPEC §15's general rule applies directly to this epic's two encoders:
"Any function that builds a vocabulary... must take an explicit... argument.
No such function may silently default to 'the whole dataset.'" This ticket
mirrors T014's role for Layer 3, but for Tier B representations — kept as
its own ticket per the "no giant tickets / no several unrelated components"
rule, even though it is conceptually similar to T014.

## Scope

- An instrumented-fit test: wrap `TfidfEncoder.fit` (and
  `SentenceEmbeddingEncoder.fit`, if its no-op still records call
  arguments) to record every example's chapter indices passed through
  `assemble_history_text`, and assert, for a real `fit` call using T005's
  train boundary, that no index exceeds the boundary.
- A cache-key sensitivity test: fitting on two different construction sets
  (e.g. two different holdout boundaries) must produce two distinct cache
  entries, never a collision (reuses T004's existing collision test
  pattern, applied specifically to these two encoders' key construction).
- A call-site check (same style as T014) confirming every call to
  `TfidfEncoder.fit` / `SentenceEmbeddingEncoder.fit` in `src/ncp/` passes a
  `construction_set_id` derived from a `SplitBoundaries`/rolling-origin
  object, never an unfiltered corpus.

## Non-goals

- Do not re-test TF-IDF/embedding correctness itself — T026/T027 already
  cover that; this ticket only tests the leakage boundary.

## Inputs

- T026, T027 (if implemented).

## Outputs

- `tests/representations/test_tier_b_leakage.py`

## Acceptance criteria

- The instrumented-fit test passes against the real corpus and T005's
  boundary.
- The cache-key sensitivity test passes.
- The call-site check passes and is wired into CI.

## Tests

(This ticket *is* a test suite — see Scope above; no additional tests
beyond those.)

## Dependencies

T026, T027.

## Risks

- **Temporal causality — this ticket's entire purpose.** Same framing as
  T014: a leakage guard is only as good as its CI wiring; a one-time manual
  check would not catch a future regression.

## Definition of done

- [ ] All three guard tests implemented and passing.
- [ ] Wired into CI so any future call site violating the contract fails
      the build.

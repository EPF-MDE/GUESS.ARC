# T014 - Layer 3 taxonomy leakage guard tests

## Objective

Write a dedicated test suite — independent of T012/T013's own unit tests —
whose sole purpose is proving that taxonomy construction (frozen or
incremental) can never be invoked, anywhere in the codebase, with a
candidate set that spans beyond its declared construction set.

## Context

SPEC §10, Layer 3, states this leakage path explicitly and at length because
it is the one most likely to be introduced accidentally later ("even though
no single label reads chapter t+1's text directly — the vocabulary itself
would have seen the future"). SPEC §8's general rule — "This rule binds
every intermediate artifact used to build `State(t)`... If any intermediate
artifact is fit on data beyond chapter t, `State(t)` is contaminated" —
makes this a project-wide concern, not just a Layer 3 detail, which is why
it gets its own ticket rather than living inside T012.

## Scope

- An integration test that builds a frozen taxonomy (T012) from the real
  corpus's train split (T005) and asserts, via instrumentation (e.g. a
  thin wrapper recording every chapter index touched during construction),
  that no touched index exceeds the train boundary.
- A regression test asserting that calling `build_frozen_taxonomy` with a
  candidate iterable that includes even one test-split candidate changes
  the resulting taxonomy relative to a train-only call (proving the
  function is not accidentally ignoring the extra data, which would mask a
  bug rather than reveal it — the test should show the taxonomy *would*
  differ, confirming the function is leakage-*sensitive* and therefore
  that keeping it train-only in production call sites actually matters).
- A static/codebase check (can be a simple `grep`-style test or an AST
  check) that every call site of `build_frozen_taxonomy` /
  `build_incremental_taxonomy` in `src/ncp/` passes an explicit
  `construction_set_id` and a filtered candidate iterable derived from a
  `SplitBoundaries` or rolling-origin object — never the raw, unfiltered
  corpus.

## Non-goals

- Do not re-test T012/T013's clustering correctness (already covered
  there) — this ticket only tests the leakage boundary.
- Do not test Layer 4 (T015) here — Layer 4's own correctness is T015's
  concern; this ticket stops at "the taxonomy itself is leakage-free."

## Inputs

- T012 (and T013 if present), T005.

## Outputs

- `tests/annotations/test_layer3_leakage.py`

## Acceptance criteria

- The instrumented-touched-chapters test passes against the real corpus.
- The train-only-vs-train-plus-test-sensitivity test passes (demonstrating
  the function is not accidentally invariant to the leak, which would hide
  a different bug).
- The call-site check passes against the current codebase and is wired into
  CI so a future call site that violates the contract fails the build.

## Dependencies

T012 (T013 if implemented).

## Risks

- **Temporal causality — this entire ticket is the risk mitigation.** Its
  own risk is false confidence: a leakage guard that only checks today's
  call sites will not catch a future call site added without re-running
  this suite. Mitigation: wire the call-site check into CI (not a one-time
  manual script), so it runs on every change to any file calling the
  taxonomy builders.

## Definition of done

- [ ] All three tests implemented and passing.
- [ ] Call-site check wired into the project's test suite (`pytest`
      discovery, not a separate manual step).

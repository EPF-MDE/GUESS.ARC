# T040 - `State(t)` assembly (Tier D) + leakage guard tests

## Objective

Assemble components 1–9 (T031–T039) into the single `State(t)` feature
vector that Tier D's model (T044) consumes, and add a cross-component
leakage guard verifying the assembled whole is leakage-safe even though
every component already individually is.

## Context

SPEC §8's formal definition applies to the assembled object as much as to
each piece: "This rule binds every intermediate artifact used to build
`State(t)`... not only the final feature vector." SPEC §8 also scopes v1's
component fidelity explicitly ("v1 implements components 1, 3, 8, 9 with
full fidelity. Components 2, 5, 6, 7 may be partial/heuristic in v1") —
this ticket's assembly must preserve and document that scope, not silently
present all nine components as equally reliable.

## Scope

- `ncp.state.assembly.StateVector`: a dataclass bundling T031–T039's
  per-component outputs for a given `t`, plus a `component_scope` record
  (which components are full-fidelity vs. heuristic in this run — feeds
  T020's provenance).
- `ncp.state.assembly.build_state(t: int, corpus: Corpus, labels: list[EventLabels], relations: list[Relation], **component_params) -> StateVector`:
  calls each of T031–T039's `*_as_of` functions with the same `t`, and
  flattens the result into a numeric feature vector (e.g. one-hot character
  statuses, relation-count summaries, conflict/question counts, recent-
  event multi-hot, object statuses) via a documented, versioned encoding
  scheme.
- `as_of_chapter` is a required parameter on every public function in this
  module — no silent default, per §15.

## Non-goals

- Do not re-derive any component's logic inline — `build_state` must call
  T031–T039's tested functions, never reimplement their filtering.
- Do not attempt to upgrade any §8-designated heuristic component to full
  fidelity as part of this ticket — that would be scope creep into a
  different ticket (and, for full-fidelity plotlines, into **Later** scope,
  §25).

## Inputs

- T031, T032, T033, T034, T035, T036, T037, T038, T039 (all nine
  components).

## Outputs

- `src/ncp/state/assembly.py`

## Acceptance criteria

- `build_state(t, ...)` internally calls each component function with the
  same `t` — verified by an instrumentation test (mocking each component
  function and asserting it receives the same `t` `build_state` was
  called with).
- No field of the resulting `StateVector` can be traced back to any chapter
  `> t` — this is the headline cross-component leakage guard: construct a
  `StateVector` at `t` from two corpora (one truncated to `<= t`, one with
  the full 1193 chapters) and assert they are identical.
- `StateVector.component_scope` correctly reports which of the nine
  components were computed in full-fidelity vs. heuristic mode for this
  run, matching SPEC §8's documented v1 scope.

## Tests

- The full-corpus-vs-truncated-corpus identity test described above — this
  is the single most important test in the entire project for defending
  H1's validity, since every Tier D result depends on it.
- The per-component-receives-same-`t` instrumentation test.
- A test asserting `as_of_chapter`/`t` has no default value in the public
  function signatures of this module.

## Dependencies

T031, T032, T033, T034, T035, T036, T037, T038, T039.

## Risks

- **Temporal causality — the single highest-stakes leakage guard in the
  project.** SPEC §8 states the contamination risk applies to "every
  intermediate artifact," and this is the ticket where nine independently
  correct components are combined for the first time — a correct component
  fed through a buggy join (e.g. passing `t+1` instead of `t` to one
  component by a copy-paste slip) can still leak even though each
  component in isolation was already tested. The full-corpus-vs-truncated-
  corpus identity test is specifically designed to catch exactly this class
  of assembly-level bug, which per-component tests cannot catch on their
  own.

## Definition of done

- [ ] `StateVector`, `build_state` implemented.
- [ ] The full-corpus-vs-truncated-corpus identity test passes against the
      real corpus for a representative sample of `t` values spanning early,
      middle, and late chapters.
- [ ] `component_scope` correctly reflects §8's documented v1 fidelity
      split.
- [ ] All listed tests pass.

# T031 - Character state ontology (`State(t)` component 1)

## Objective

Implement the character status ontology (`introduced`, `active`,
`inactive`, `deceased`, `unknown`) exactly as defined in SPEC §8, computed
as-of any chapter t from cumulative appearance history only.

## Context

SPEC §8, component 1: "Contains: character → status... as of t. Constructed
from: cumulative union of appearances/mentions in chapters 1..t, status
rule applied per character... v1 implements components 1, 3, 8, 9 with full
fidelity." SPEC §8's status table gives exact per-status semantics:
`introduced` (first appearance ≤t, no further status established),
`active` (appeared within a recency window ending at t), `inactive`
(introduced but absent from the recency window, no death/unknown evidence),
`deceased` (death explicitly depicted/stated ≤t), `unknown` (explicitly
ambiguous in-story status, e.g. "presumed dead" — distinct from `inactive`).
SPEC §26 lists the recency-window width and `unknown`-trigger conditions as
open — this ticket implements both as configurable, documented defaults.

## Scope

- `ncp.state.characters.CharacterStatus` enum matching the five values
  exactly.
- `ncp.state.characters.character_status_as_of(character: str, corpus: Corpus, t: int, *, recency_window: int, death_markers: ..., ambiguity_markers: ...) -> CharacterStatus`:
  computed purely from chapters `1..t`'s front-matter character
  appearances (§9) plus death/ambiguity signals detected from chapter text
  (reuse T010's extraction-procedure discipline: a fixed, versioned,
  chapter-local detector, not a global statistic).
- `active_characters_as_of(corpus, t, **params) -> dict[str, CharacterStatus]`
  for the full roster.
- `recency_window` and death/ambiguity marker lexicons exposed via config
  (extend `AnnotationConfig` or a new state-specific config section), with
  documented defaults — not resolving SPEC §26's open research question,
  only making it adjustable.

## Non-goals

- Do not use §9's raw per-chapter list directly as the final feature (that
  is Tier C's simpler job, T029) — this ticket's richer status ontology is
  specifically for Tier D.
- Do not resolve the exact recency-window width or `unknown`-trigger
  wording as a permanent research conclusion — implement as configurable
  with a reasoned default, documented in the module.

## Inputs

- T003 (validated corpus with per-chapter character lists, T002's output),
  T010 (extraction-procedure pattern, for death/ambiguity detection).

## Outputs

- `src/ncp/state/characters.py`

## Acceptance criteria

- `character_status_as_of(name, corpus, t, ...)` only ever reads chapters
  `<= t` for that character — never chapter `t+1` or beyond.
- A character whose only appearance is chapter 5, evaluated at `t=5`, is
  `introduced`; evaluated at `t=5+recency_window`, `inactive` unless
  additional appearances occur within the window.
- A character with an explicit death signal detected at chapter `d <= t` is
  `deceased` at every `t >= d`, and whatever status applied for `t < d`
  remains unchanged (status is never retroactively altered by future
  information — re-evaluating `character_status_as_of` at an earlier `t`
  after new death evidence appears later must still return the pre-death
  status for that earlier `t`).
- `unknown` is returned only when an explicit ambiguity marker is detected,
  never as a default fallback for "insufficient data."

## Tests

- Unit tests for each of the five status outcomes on synthetic character
  timelines.
- **Leakage guard test**: `character_status_as_of(name, corpus, t, ...)`
  called with `t` fixed, must return the identical result regardless of
  whether `corpus` is truncated to chapters `<= t` or contains the full
  1193-chapter corpus — i.e. the function itself must never read beyond
  `t` even when given access to more data (test by comparing both calls).
- Monotonicity-of-the-past test: re-running at an earlier `t` after
  appending later chapters never changes the earlier result (see
  acceptance criteria above).

## Dependencies

T003, T010.

## Risks

- **Temporal causality — SPEC §8's example is written for exactly this
  ticket:** "if a relationship becomes explicit in chapter 500, it must be
  absent from `State(100)` and `State(499)`, and present from `State(500)`
  onward — even though it was 'always true' in the fictional timeline...
  `State(t)` models what is knowable from the text at t, not fictional
  ground truth." The same discipline applies to death/ambiguity detection
  here: a character's death revealed in flashback at chapter 600 referring
  to an event "that happened" earlier must still only count as `deceased`
  from chapter 600 onward, not retroactively.
- **Character state ontology thresholds (§26):** recency window and
  `unknown` triggers are open decisions; this ticket's defaults must be
  documented and easy to change via config, not buried in code.

## Definition of done

- [ ] `CharacterStatus`, `character_status_as_of`,
      `active_characters_as_of` implemented.
- [ ] All listed tests pass, including the two leakage/monotonicity tests.
- [ ] Config defaults for recency window and markers documented with
      rationale.

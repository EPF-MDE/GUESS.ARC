# T035 - Known facts tracking (`State(t)` component 5)

## Objective

Implement known-facts tracking: canonical facts revealed by chapter t
(in-story epistemic state, not eventual retconned "truth"), each with an
`evidenced_at`, as a partial/heuristic v1 component.

## Context

SPEC §8, component 5: "Contains: canonical facts revealed by t (in-story
epistemic state, not necessarily the eventual retconned 'truth').
Constructed from: explicit statements/reveals in 1..t, each with an
`evidenced_at`. Allowed inputs: chapters 1..t. Classification: feature."
Explicitly listed among the components "may be partial/heuristic in v1"
(§8).

## Scope

- `ncp.state.facts.Fact`: free-text or lightly structured
  (`subject`, `predicate_text`, `evidenced_at`).
- `ncp.state.facts.extract_facts(chapter: ChapterRecord, *, extraction_version: str) -> list[Fact]`:
  a simple heuristic extractor over chapter t's own Long Summary/Chapter
  Notes — e.g. sentences matching a small set of reveal-indicating patterns
  ("revealed that", "is actually", "turns out") — explicitly heuristic and
  documented as such, not claiming completeness.
- `ncp.state.facts.known_facts_as_of(all_facts: list[Fact], t: int) -> list[Fact]`:
  filters to `evidenced_at <= t`.

## Non-goals

- Do not attempt comprehensive fact extraction or fact verification against
  "true" canon — explicitly out of scope; SPEC emphasizes in-story
  epistemic state at t, which this heuristic approximates, not resolves
  perfectly.
- Do not deduplicate/merge facts across chapters beyond simple exact-text
  matching — a heuristic v1 component does not need canonical fact
  resolution.

## Inputs

- T010 (extraction-procedure pattern), T002 (chapter text).

## Outputs

- `src/ncp/state/facts.py`

## Acceptance criteria

- `extract_facts` reads only its one input chapter.
- `known_facts_as_of(facts, t)` never includes a fact with
  `evidenced_at > t`.
- The heuristic nature and known limitations are documented in the module
  docstring (per `CLAUDE.md`'s "no fabricated experiment results" spirit —
  do not imply this is a complete fact base).

## Tests

- Unit test with synthetic reveal-pattern sentences, asserting extraction
  fires on expected patterns and not on unrelated sentences.
- Filter test (`evidenced_at <= t`).
- Single-chapter-input test.

## Dependencies

T010.

## Risks

- **Temporal causality:** same class as prior components — `evidenced_at`
  must be the chapter where the fact was *itself* extracted, never
  back-dated. Low complexity reduces risk, but the heuristic nature raises
  a **retrospective-wiki-annotation** risk (§23): if a chapter's Long
  Summary was edited with hindsight, a "fact" extracted from chapter t's
  summary might actually encode knowledge from later chapters. This ticket
  cannot fix that (§26: a retrospective-edit check is a separate, unresolved
  decision) but must document it as an inherited risk.

## Definition of done

- [ ] `Fact`, `extract_facts`, `known_facts_as_of` implemented.
- [ ] All listed tests pass.
- [ ] Heuristic limitations and inherited retrospective-edit risk
      documented in the module docstring.

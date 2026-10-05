# T008 - Auxiliary entity-presence target builder

## Objective

Build the chapter-(t+1) character-presence label set for each forecasting
example — the auxiliary target defined in SPEC §9 — kept strictly separate
from, and never substituted for, the primary event-label target.

## Context

SPEC §5: "Auxiliary target: character/entity presence in chapter t+1 (§9).
Retained because the wiki's character table makes it cheap to measure...
but it is explicitly not a substitute for the primary event target." SPEC
§9: "The chapter-(t+1) entity list is not available at prediction time — it
is a label... as the chapter-(t+1) target: auxiliary target."

## Scope

- `ncp.forecasting.targets.entity_presence_target(example: ForecastingExample, corpus: Corpus) -> set[str]`:
  reads the **target** chapter's own front-matter character list (parsed by
  T002) and returns the set of character names present (per whatever
  on-panel/cover/flashback granularity T002 preserved — this ticket does
  not re-decide that; see Non-goals).
- A small `EntityTargetTable` aggregation helper producing one row per
  example (`target_index` → label set), for use by T019's protocol runner
  and T021-T024/T042-T044's secondary-metric reporting.
- Explicit module-level docstring/constant naming this as
  `AUXILIARY_TARGET = "entity_presence"`, distinct from
  `PRIMARY_TARGET = "event_labels"` (T015), so no caller can accidentally
  conflate the two without an explicit, visible choice.

## Non-goals

- Do not decide the cover/flashback granularity question (SPEC §26) — pass
  through whatever T002 produced; if both a collapsed boolean and the
  granular signal exist, expose both and let the caller choose, defaulting
  to the collapsed `on_panel` boolean to match the existing
  `ChapterRecord.metadata` convention described in §4.
- Do not use this target as a stand-in for event labels in any report —
  enforced by naming, not by this ticket controlling callers (callers'
  discipline is checked in each consuming ticket's acceptance criteria).

## Inputs

- T002 (parsed per-chapter character list), T007 (`ForecastingExample`
  with its `target_index`).

## Outputs

- `src/ncp/forecasting/targets.py` (`entity_presence_target`,
  `EntityTargetTable`, the two named constants).

## Acceptance criteria

- For every example, the returned label set is built exclusively from the
  target chapter's own front-matter — never from history chapters, never
  from any other chapter.
- Calling this on chapter t's own history window (as a feature, via
  `State(t)` component 1 in EPIC-05) and on chapter t+1 (as this ticket's
  target) must be two distinct call sites in the codebase — this ticket
  only implements the target call site.

## Tests

- Unit test asserting the returned set matches a hand-checked fixture
  chapter's character list.
- Test asserting that changing the *target* chapter's metadata changes the
  label, while changing a *history* chapter's metadata does not.

## Dependencies

T002, T007.

## Risks

- **Temporal causality:** low direct risk (this is a label, read correctly
  from its own chapter), but SPEC §9 flags a **labeling-integrity** risk
  specific to this target: "retrospective/hindsight curation by wiki
  editors — chapter-t annotations may encode knowledge the editor had of
  chapters beyond t at edit time... a labeling-integrity risk, not a
  feature-leakage risk." Document this risk in the module docstring; no
  code fix is prescribed by SPEC for v1.

## Definition of done

- [ ] `entity_presence_target` implemented and tested.
- [ ] Primary/auxiliary target naming constants present and referenced in
      module docstring.
- [ ] Labeling-integrity risk documented inline per SPEC §9/§23.

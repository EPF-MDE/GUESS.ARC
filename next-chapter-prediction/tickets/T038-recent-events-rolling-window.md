# T038 - Recent-events rolling window (`State(t)` component 8)

## Objective

Implement the recent-events rolling window: the most recent k Layer 4
event labels for chapters ≤ t, as a full-fidelity v1 component.

## Context

SPEC §8, component 8: "Contains: rolling window of the most recent k items
from §10 Layer 4, for chapters ≤t. Constructed from: §10's pipeline applied
only to chapters ≤t, using whichever taxonomy mode is active for the run.
Allowed inputs: chapters 1..t; the taxonomy itself must not have been built
using chapters beyond t. Available at prediction time: yes. Classification:
feature (distinct from the chapter t+1 event labels used as the prediction
target)." This is the simplest of the four full-fidelity components — a
direct windowed read of T015's already-produced labels — and is also what
T022's persistence baseline already exercises informally; this ticket
formalizes it as a reusable `State(t)` component for Tier D.

## Scope

- `ncp.state.recent_events.recent_events_as_of(labels: list[EventLabels], t: int, *, k: int) -> list[EventLabels]`:
  the `EventLabels` rows for the `k` most recent chapters with index `<= t`
  (fewer than `k` if `t` is near the corpus start).
- Explicitly documents, in its docstring, the distinction from the
  training *target* (chapter t+1's own `EventLabels`, never passed to this
  function) — the same labels table serves both roles (per T015's
  acceptance criteria) but through two different call sites.

## Non-goals

- Do not re-derive or re-classify labels — purely a windowed read of
  already-generated T015 output.
- Do not conflate this with T022's baseline logic — that baseline predicts
  from this window; this ticket only exposes the window as a `State(t)`
  feature for Tier D's model (T040/T044), a different consumer.

## Inputs

- T015 (event labels), T007 (chapter ordering/history size conventions,
  for consistency of "recent" semantics with the rest of the project).

## Outputs

- `src/ncp/state/recent_events.py`

## Acceptance criteria

- `recent_events_as_of(labels, t, k=k)` never returns a row with
  `chapter > t`.
- Calling this function is the *only* way Tier D accesses recent event
  history — verified by a test confirming Tier D's assembly (T040) imports
  and calls this function rather than re-reading `labels` directly.

## Tests

- Unit test on a synthetic label table, asserting the correct k-window for
  several `t` values, including near the corpus start (fewer than k rows
  available).
- A test confirming the function never reads `labels` entries with
  `chapter > t`, even when the full label table (including future
  chapters) is passed in — mirrors T031/T033's "safe even if given more
  data than it should use" guarantee.

## Dependencies

T015, T007.

## Risks

- **Temporal causality:** low complexity, but this component is the
  closest state ingredient to the prediction target itself (both are
  "event labels," differing only in which chapter) — the clearest possible
  place for a careless off-by-one to turn a feature into the target. The
  "never reads chapter > t even if given more data" test is the key guard.

## Definition of done

- [ ] `recent_events_as_of` implemented and tested.
- [ ] Docstring explicitly distinguishes this feature role from the T015
      target role.

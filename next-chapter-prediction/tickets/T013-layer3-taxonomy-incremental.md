# T013 - Layer 3 taxonomy construction — incremental mode

## Objective

Implement "incremental" taxonomy construction as an alternate mode behind
T012's `EventTaxonomy` interface: rebuilt only from chapters ≤ t at each
rolling-origin evaluation point, rather than frozen once.

## Context

SPEC §10, Layer 3: "(b) Incremental — rebuilt only from chapters ≤t at each
evaluation point." This mode matters specifically for the rolling-origin
protocol (§16, T006), where later origins have strictly more history
available and a frozen train-only taxonomy might miss categories that only
emerge later in the corpus. Marked **Could** in the roadmap because §16's
hypothesis table does not require incremental mode specifically — frozen
mode (T012) is sufficient to run every H1–H3 cell; this ticket exists for
completeness and for a stronger rolling-origin H4 comparison later (EPIC-07).

## Scope

- `build_incremental_taxonomy(candidates_as_of: Callable[[int], Iterable[EventCandidate]], origin_chapter: int, *, taxonomy_version: str) -> EventTaxonomy`:
  same output type as T012, but constructed by calling
  `candidates_as_of(origin_chapter)` internally (a caller-supplied function
  that itself must only ever return candidates with `chapter <= origin_chapter`
  — validated, not just trusted).
- Reuses T012's clustering/normalization internals (do not duplicate logic
  — refactor the shared normalization step into a private helper T012
  already needs, and call it from both modes).
- Per-origin taxonomies are cached (T004) keyed by `origin_chapter`, since
  rolling-origin with many origins would otherwise rebuild redundantly.

## Non-goals

- Do not change T012's frozen-mode behavior or public interface.
- Do not decide how many origins / which step size to use — that is T006's
  and T050's concern; this ticket only makes incremental construction
  possible for whatever origins are supplied.

## Inputs

- T012 (shared taxonomy internals, `EventTaxonomy` type).
- T006 (rolling-origin boundaries, as the source of `origin_chapter` values
  in practice).

## Outputs

- Additions to `src/ncp/annotations/layer3.py`
  (`build_incremental_taxonomy`).

## Acceptance criteria

- For two origins `o1 < o2`, the taxonomy built at `o2` is built from a
  candidate set that is a superset of (or equal to) the one used at `o1`
  (strictly more or equal history, never less, never different-but-
  unrelated chapters).
- A `candidates_as_of` implementation that violates its contract (returns a
  candidate with `chapter > origin_chapter`) causes this function to raise,
  not silently include it.

## Tests

- Unit test with a synthetic `candidates_as_of` and two origins, asserting
  the superset property.
- Contract-violation test: a deliberately broken `candidates_as_of` (leaking
  one future candidate) must cause `build_incremental_taxonomy` to raise.

## Dependencies

T012.

## Risks

- **Temporal causality:** this ticket exists specifically to serve
  rolling-origin evaluation without leakage, but is also the easiest mode
  to get wrong, since "rebuild per origin" invites an implementer to reach
  for "just pass the whole corpus and let something else filter it later."
  The explicit raise-on-violation acceptance criterion is the main
  mitigation; it must never be weakened to a warning.

## Definition of done

- [ ] `build_incremental_taxonomy` implemented, sharing internals with
      T012, with both tests passing.
- [ ] Contract-violation test passes (raises as specified).

# T004 - Construction-set-scoped artifact cache utility

## Objective

Implement a small, generic caching utility that keys every cached artifact
(embeddings, extracted candidates, fitted vectorizers, taxonomies) by an
explicit construction-set identifier, so a cache entry built under one split
boundary is never silently reused under another.

## Context

SPEC §21: "Expensive intermediate artifacts (embeddings, extracted
candidates) cached, keyed by their construction-set identifier, so a cached
artifact built under one split boundary is never silently reused under
another." SPEC §15 generalizes this: "Any function that builds a vocabulary,
taxonomy, or threshold must take an explicit 'as-of chapter' or
'construction set' argument. No such function may silently default to 'the
whole dataset.'" This ticket builds the one shared mechanism that every
later caching ticket (T012, T026, T027) uses, rather than each reinventing
cache-key logic.

## Scope

- `ncp.utils.cache.ConstructionSetKey`: a frozen, hashable value built from
  the pieces that make an artifact valid-or-not for a given context — e.g.
  `{"split_id": ..., "boundary_chapter": ..., "config_hash": ...}`.
- `ncp.utils.cache.cached_artifact(key: ConstructionSetKey, builder: Callable[[], T], cache_dir: Path) -> T`:
  looks up a serialized artifact under a filename derived from `key`'s hash;
  calls `builder()` and writes the result if missing; raises on a
  deserialization mismatch rather than silently returning a wrong-shaped
  object.
- A `clear_cache(cache_dir, *, key: ConstructionSetKey | None = None)` helper
  for tests and for deliberate invalidation.

## Non-goals

- Do not implement caching for model checkpoints (training already has
  `paths.checkpoints_dir` in `PathsConfig`) — this utility is for
  deterministic, input-derived intermediate artifacts only.
- Do not pick a specific serialization format beyond what the first
  consumer (T012/T026) needs — keep the interface format-agnostic
  (`builder`/`loader`/`dumper` callables), not hard-coded to pickle/JSON.

## Inputs

- `src/ncp/config/schema.py` for the kind of values (`split_ratios`,
  `history_size`, etc.) that typically belong in a `ConstructionSetKey`.
- `src/ncp/utils/io.py` (existing JSON helpers) as a model for I/O style.

## Outputs

- `src/ncp/utils/cache.py`

## Acceptance criteria

- Calling `cached_artifact` twice with the same key and a `builder` that
  raises on the second call still succeeds (second call is a cache hit).
- Calling it with two different keys never returns the first key's artifact
  for the second key.
- The cache file name/path is a pure function of the key's contents (same
  key → same path, regardless of process/run).

## Tests

- Unit tests for cache hit, cache miss, key-collision-avoidance (two
  distinct keys never collide to the same path for a reasonable sample),
  and `clear_cache`.

## Dependencies

None.

## Risks

- **Temporal causality (indirect but important):** this utility does not
  itself enforce leakage-freedom — it only prevents *cross-contamination
  between runs*. A caller that constructs a `ConstructionSetKey` without
  including the split boundary can still produce a leaking cache. This must
  be documented prominently in the module docstring so every consumer
  ticket (T012, T026, T027) is reminded to include the boundary in the key.

## Definition of done

- [ ] `ncp.utils.cache` implemented with hit/miss/collision tests passing.
- [ ] Docstring explicitly states the key must include the construction-set
      boundary to be leakage-safe, and that this utility does not verify
      that on its own.

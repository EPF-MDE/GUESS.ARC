# T027 - Sentence-embedding encoder (Tier B, optional)

## Objective

Implement an optional alternate Tier B encoder using pretrained sentence
embeddings (the `sentence-transformers` optional `dl` extra), as a drop-in
alternative to T026's TF-IDF encoder behind the same interface.

## Context

SPEC §13, Tier B explicitly allows "TF-IDF/**embedding**" — the existing
`RepresentationConfig.encoder` field already supports `"sentence_transformer"`
and names a default model
(`sentence-transformers/all-MiniLM-L6-v2`), and `pyproject.toml`'s `dl`
extra already lists `sentence-transformers`. This ticket is marked
**Could** (roadmap) because T026 alone is sufficient to run every Tier B/C
experiment in EPIC-06 — this ticket only adds a second option for
comparison/robustness, not a required path.

## Scope

- `ncp.representations.embedding.SentenceEmbeddingEncoder`: same interface
  shape as `TfidfEncoder` (`fit`/`transform`, though for pretrained
  embeddings "fit" may be a no-op beyond caching — document this
  explicitly, since no corpus-derived vocabulary is learned, which is
  itself a mild leakage-reducing property worth noting).
- Embeddings computed per history-chapter text (or per assembled window,
  per `RepresentationConfig.options`), cached via T004 keyed by
  construction-set id **and** model name/version (pretrained model identity
  matters for cache correctness even though no corpus fitting occurs).
- Graceful, clear failure (not a bare `ImportError` traceback) if the `dl`
  extra is not installed, pointing the user at
  `pip install -e ".[dl]"`.

## Non-goals

- Do not fine-tune the embedding model on this corpus — v1 uses it purely
  as a frozen pretrained encoder, consistent with "no unnecessary
  training" and with keeping this optional/lightweight.
- Do not make this encoder the default — TF-IDF (T026) remains the default
  per the existing config's documented intent (core dependency, no
  download required).

## Inputs

- T025 (assembled history text), T004 (cache).

## Outputs

- `src/ncp/representations/embedding.py`

## Acceptance criteria

- With the `dl` extra installed, encoding the same text twice (same model)
  produces identical vectors (determinism) and hits the cache on the
  second call.
- Without the `dl` extra installed, instantiating this encoder raises a
  clear, actionable error rather than an opaque import traceback.
- Output interface matches `TfidfEncoder`'s closely enough that T030/T042
  can use either encoder without branching on type.

## Tests

- Unit test (skipped/xfail if `dl` extra absent in the test environment)
  for determinism and caching.
- Test for the clear-error-without-extra path (can be simulated by
  monkey-patching the import).

## Dependencies

T025, T004.

## Risks

- **Temporal causality:** minimal — a frozen pretrained model has no
  corpus-fit vocabulary to leak from the construction set at all (it was
  trained externally, long before and independent of this project's
  split). The main residual risk is caching an embedding under a key that
  omits the model name/version, causing a stale/wrong-model vector to be
  reused silently after a model upgrade — guarded by including model
  identity in the cache key.

## Definition of done

- [ ] `SentenceEmbeddingEncoder` implemented behind the same interface
      shape as `TfidfEncoder`.
- [ ] All listed tests pass (or are cleanly skipped without the `dl`
      extra).

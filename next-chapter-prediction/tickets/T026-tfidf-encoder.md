# T026 - TF-IDF encoder (Tier B)

## Objective

Implement the TF-IDF encoder for Tier B text representations, fit
exclusively on the construction set's assembled history text, cached via
T004, and usable by T019's runner/T041's model.

## Context

SPEC §13, Tier B: "TF-IDF/embedding of chapter-window summary text | simple
classifier (logistic/GBM/MLP) | yes | baseline for H1, H3." The existing
`RepresentationConfig` already declares `encoder: "tfidf"`,
`max_features`, `ngram_range` — this ticket is the first implementation
behind those fields. SPEC §15: "Any function that builds a vocabulary...
must take an explicit... construction set argument" applies directly to
`TfidfVectorizer.fit`.

## Scope

- `ncp.representations.tfidf.TfidfEncoder`: wraps
  `sklearn.feature_extraction.text.TfidfVectorizer` (already a core
  dependency per `pyproject.toml`), with `fit(texts: Sequence[str], *, construction_set_id: str)`
  (required, non-defaulted) and `transform(texts) -> scipy.sparse matrix`.
- Vectorizer parameters (`max_features`, `ngram_range`) sourced from
  `RepresentationConfig`.
- Fitted vectorizer cached via T004, keyed on `construction_set_id` +
  config hash, so re-fitting the same construction set is a cache hit.

## Non-goals

- Do not implement the sentence-embedding alternative — T027.
- Do not implement Tier C's entity concatenation — T030.

## Inputs

- T025 (assembled history text for every example), T005 (construction-set
  boundary — only train-split examples' text is used to `fit`), T004
  (cache).

## Outputs

- `src/ncp/representations/tfidf.py`

## Acceptance criteria

- `fit` is only ever called (in every call site in the codebase) with text
  assembled from train-split examples — enforced by T028's leakage test,
  not duplicated here, but this ticket's own unit test must demonstrate the
  mechanism works correctly when used properly.
- `transform` can be called on val/test example text after `fit` on train
  text alone, without error, including text containing out-of-vocabulary
  terms (handled gracefully by TF-IDF's existing OOV behavior).
- Re-fitting with the same `construction_set_id` and config is a cache hit
  (no vectorizer re-training).

## Tests

- Unit test: fit on a small train corpus, transform a val-only document
  containing a word absent from train, confirm no crash and a sane sparse
  vector.
- Cache-hit test via T004.
- Determinism test: same input text, same config → identical output
  vector.

## Dependencies

T025, T005, T004.

## Risks

- **Temporal causality:** the central risk is fitting on anything beyond
  the train split. `construction_set_id` being a required argument (no
  default) is the primary code-level guard; T028 adds the dedicated
  cross-cutting test.

## Definition of done

- [ ] `TfidfEncoder` implemented with caching.
- [ ] All listed tests pass.
- [ ] A real fit on the actual train split completes and produces a
      reasonably sized vocabulary (logged for review, not asserted to an
      exact number).

# T030 - Tier C feature assembly + leakage guard tests

## Objective

Concatenate Tier B's text features (T026) with Tier C's entity-history
features (T029) into one combined feature vector per example, and add a
dedicated leakage guard proving the combination introduces no new leakage
beyond what T026/T029 already individually guard.

## Context

SPEC §13 defines Tier C purely as "Tier B features + entity representation" —
i.e. a concatenation, not a new learned representation. SPEC §18's first
ablation row ("text-only vs. +entities... holding model family, split, and
taxonomy version fixed") requires that Tier B and Tier C differ by
*exactly* the entity features and nothing else — this ticket is what makes
that controlled comparison mechanically guaranteed rather than merely
intended.

## Scope

- `ncp.representations.tier_c.assemble_tier_c(example, corpus, tfidf: TfidfEncoder, entity_vocab: EntityVocabulary) -> np.ndarray`:
  horizontally concatenates the TF-IDF (or embedding) vector and the entity
  feature vector for the same example, in a fixed, documented order.
- A regression test asserting that the first `N` columns of a Tier C vector
  exactly equal the corresponding Tier B vector's values (same encoder,
  same example) — i.e. concatenation adds columns, never mutates existing
  ones.

## Non-goals

- Do not introduce any new fitted component in this ticket — both
  `tfidf`/encoder and `entity_vocab` are passed in already-fitted from
  T026/T029; this ticket is pure assembly.

## Inputs

- T026 (fitted encoder), T029 (fitted entity vocabulary), T007 (examples).

## Outputs

- `src/ncp/representations/tier_c.py`

## Acceptance criteria

- Tier C vectors' first block of columns exactly matches Tier B vectors
  for the same example/encoder (verified by the regression test above).
- Tier C introduces no additional construction-set-fitting step of its own
  — it only consumes already-fitted T026/T029 objects.

## Tests

- The Tier-B-equivalence regression test described above.
- A shape test: Tier C vector length equals Tier B length plus entity
  vocabulary size, for every example.

## Dependencies

T026, T029.

## Risks

- **Temporal causality:** low, by construction (this ticket fits nothing
  itself) — the main residual risk would be a caller fitting `tfidf` and
  `entity_vocab` on *different* construction sets by mistake, silently
  producing an internally inconsistent Tier C representation. Document
  this explicitly in the function's docstring as a caller responsibility,
  and add a test that passing mismatched `construction_set_id`s raises.

## Definition of done

- [ ] `assemble_tier_c` implemented.
- [ ] Tier-B-equivalence and shape tests pass.
- [ ] Mismatched-construction-set-id test raises as specified.

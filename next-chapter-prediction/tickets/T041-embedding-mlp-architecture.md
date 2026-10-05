# T041 - Embedding+MLP model architecture

## Objective

Implement one shared Embedding+MLP model architecture, parameterized only
by input feature dimension, that T042/T043/T044 instantiate over Tier B,
Tier C, and Tier D inputs respectively.

## Context

SPEC §14: "v1 core: Embedding+MLP architecture, instantiated three ways —
Tier B inputs, Tier C inputs, Tier D inputs — producing the H1/H3 comparison
pair from one architecture family, removing architecture choice as a
confound." This is the architectural backbone of every H1/H2/H3 result;
sharing one implementation across tiers is itself a SPEC requirement, not
just good practice — it is what makes the later H1/H3 comparisons valid
(the only varying ingredient between runs must be the input representation).

## Scope

- `ncp.models.mlp.EmbeddingMLP`: a `ModelAdapter`-conforming
  (T019 interface) multi-label classifier — a simple feed-forward network
  (input → hidden layer(s) → sigmoid output per event category), trainable
  with the core dependencies alone where possible (e.g.
  `sklearn.neural_network.MLPClassifier` wrapped for multi-label output,
  or a minimal `numpy`-based implementation) so Tier B/C/D runs do not
  require the `dl` extra; if a `torch`-based implementation is preferred
  for the sigmoid multi-label output head, gate it behind the `dl` extra
  with the same clear-error-without-extra pattern as T027.
- Hyperparameters (hidden size, learning rate, epochs, regularization)
  sourced from `ModelConfig.params`, with fixed seeds via
  `ExperimentConfig.seed` (per `CLAUDE.md`'s "fixed random seeds").
- `fit(X_train, y_train, *, seed)` / `predict(X) -> label sets` /
  `predict_scores(X) -> per-category scores` (for P@K/R@K).

## Non-goals

- Do not implement GRU/LSTM/Transformer here — Tier E is EPIC-07, gated and
  not yet ticketed.
- Do not tune hyperparameters per tier as part of this ticket — T042/T043/
  T044 may each have their own reasonable defaults, but the *architecture*
  (this ticket) must be identical code across tiers, only the input
  dimension and surrounding config differ.

## Inputs

- T019 (`ModelAdapter` interface).

## Outputs

- `src/ncp/models/mlp.py`

## Acceptance criteria

- The same `EmbeddingMLP` class, with no tier-specific code branches,
  trains successfully on Tier B, Tier C, and Tier D feature matrices of
  different widths (verified by a parameterized test running all three
  shapes through the same class).
- Training with a fixed seed is reproducible (same seed, same data → same
  learned weights or, at minimum, same predictions).
- `predict_scores` output is suitable for T018's P@K/R@K computation
  (per-category float scores, not just hard labels).

## Tests

- Parameterized test across three synthetic input widths (standing in for
  Tier B/C/D), confirming the architecture is tier-agnostic.
- Reproducibility test (fixed seed → deterministic output).
- A multi-label correctness smoke test on a small synthetic dataset with a
  known learnable pattern, confirming the model can fit it above a trivial
  baseline.

## Dependencies

T019.

## Risks

- **Temporal causality:** none directly (this ticket only defines model
  *architecture*, with no access to chapter data) — training-time leakage
  is governed entirely by what `X_train`/`y_train` the caller (T042-44)
  passes in, which is where the real risk lives, already guarded by
  T026/T029/T040's construction-set discipline.
- **Sample size (§24):** 1193 chapters is small; this architecture must
  stay simple enough to avoid gross overfitting at this scale — keep
  hidden-layer size modest and regularized by default.

## Definition of done

- [ ] `EmbeddingMLP` implemented, tier-agnostic, seeded.
- [ ] All listed tests pass.

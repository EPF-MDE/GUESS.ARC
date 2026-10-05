# T043 - Tier C training/evaluation run

## Objective

Run T041's `EmbeddingMLP` over Tier C (TF-IDF + entity history, T030)
features through T019's holdout protocol, archive the result via T020.

## Context

SPEC §13 Tier C "tests H3" against Tier B. SPEC §18's first ablation row
("text-only vs. +entities") is exactly the T042-vs-T043 comparison. This
ticket must differ from T042 *only* in the representation fed to the
identical `EmbeddingMLP` architecture (T041) — no other configuration
changes, so the comparison in T046 is a clean single-ingredient ablation.

## Scope

- A run script/config (`configs/experiment/tier_c.yaml`) identical to
  T042's `tier_b.yaml` except `representation.name = "text_entities"` (or
  equivalent), wired to T030's `assemble_tier_c`.
- Same execution shape as T042: build features → fit → evaluate → archive
  with `tier="C"`.

## Non-goals

- Do not change any model hyperparameter relative to T042's run — any
  difference beyond the representation itself would confound the H3
  comparison (§18's explicit warning: "change exactly one representational
  ingredient at a time, holding model family, split, and taxonomy version
  fixed").

## Inputs

- T041, T030, T019, T020.

## Outputs

- `configs/experiment/tier_c.yaml`, an archived run under
  `experiments/<run_id>/`.

## Acceptance criteria

- The run completes and produces a `MetricsReport` with all §16 metrics.
- A diff between `tier_b.yaml` and `tier_c.yaml` shows only the
  representation-related fields changed — verified by an explicit config-
  diff test.
- Archived provenance records `tier="C"` with the same `taxonomy_version`/
  `split_protocol`/seed as T042's run (confirmed by comparing the two
  archived provenance records).

## Tests

- Config-diff test (only representation fields differ from T042's config).
- Fast CI integration test mirroring T042's.

## Dependencies

T041, T030.

## Risks

- **Temporal causality:** none new (inherits T030's guarantees). The
  specific risk for *this* ticket is a confound risk, not a leakage risk:
  accidentally changing a hyperparameter alongside the representation,
  which would invalidate the H3 comparison even without any leakage. The
  config-diff test is the direct guard.

## Definition of done

- [ ] Real-corpus run completes and is archived.
- [ ] Config-diff test against T042 passes.
- [ ] CI integration test passes.

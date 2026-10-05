# EPIC-04 — Representations (Tier B / Tier C)

## Goal

Build the text-only representation (Tier B) and the entity-aware
representation (Tier C = Tier B + §9 entity history) that the H3 experiment
(entities vs. text-only) compares, using one shared encoder family so the
only varying ingredient is presence/absence of entity features.

## Why this epic exists (SPEC anchors)

- §13 Tier B: "TF-IDF/embedding of chapter-window summary text... baseline for
  H1, H3." Tier C: "Tier B features + entity representation (§9, history
  only)... tests H3."
- §9: entity representation is "per-chapter character list with faction and
  appearance annotation... sourced from wiki front-matter," available as a
  feature only via history (chapters ≤t); the chapter-(t+1) list is a label,
  never a feature.
- §18 ablation table, row 1: "text-only vs. +entities" tests H3, "holding
  model family, split, and taxonomy version fixed" — this epic is what makes
  that controlled comparison possible, by keeping Tier B and Tier C on the
  same encoder.
- §15: "Any function that builds a vocabulary... must take an explicit
  'as-of chapter' or construction-set argument" applies directly to the
  TF-IDF/embedding fitting step in this epic.

## Tickets

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T025 | Windowed-history text assembly | Must | T007, T002 | M |
| T026 | TF-IDF encoder (Tier B) | Must | T025, T005, T004 | M |
| T027 | Sentence-embedding encoder (Tier B, optional) | Could | T025, T004 | M |
| T028 | Tier B leakage guard tests | Must | T026, T027 | S |
| T029 | Entity-history feature extraction (§9, Tier C) | Must | T008, T007 | M |
| T030 | Tier C feature assembly + leakage guard tests | Must | T026, T029 | S |

## Dependency notes

T027 is **Could**: §13/§14 only require "simple classifier" over Tier B
features, and `requirements.txt` already comments out the `dl` extra
(`sentence-transformers`) as optional. TF-IDF (T026) alone is sufficient to
run every Tier B/C ticket in EPIC-06; T027 is an enhancement, not a blocker.
T029 deliberately reuses §9's raw per-chapter character list (faction +
on-panel/cover/flashback annotation), not EPIC-05's richer character-status
ontology (`State(t)` component 1, §8) — §13 defines Tier C via §9 specifically,
keeping Tier C "simple classifier family" distinct from Tier D's full state.

## Out of scope for this epic

- The character state ontology (`introduced`/`active`/`inactive`/`deceased`/
  `unknown`, §8 component 1) — that is EPIC-05's richer construction for
  Tier D, not this epic's Tier C entity feature.
- Relations, locations, conflicts, facts, unresolved questions, plot
  threads, objects/goals — all EPIC-05.
- Any model training — this epic only produces feature matrices consumed by
  EPIC-06.

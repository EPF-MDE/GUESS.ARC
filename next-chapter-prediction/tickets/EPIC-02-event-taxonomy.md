# EPIC-02 — Event Taxonomy

## Goal

Build and validate the four-layer event pipeline (SPEC §10) — raw notes →
event candidates → normalized taxonomy → final per-chapter event labels —
entirely independent of any model, and with every taxonomy-construction step
provably scoped to a declared construction set.

## Why this epic exists (SPEC anchors)

- §10: "No layer below Layer 1 is assumed to already be ground truth" — each
  layer needs its own ticket and its own validation, not one monolithic
  "extract events" script.
- §10 Layer 3: taxonomy construction is explicitly a leakage channel
  ("Building the taxonomy from the full corpus and evaluating on the same
  chapters is a leakage path even though no single label reads chapter
  t+1's text directly").
- §26 lists "Event taxonomy construction method" and "Event label frequency
  threshold" as open decisions that must be resolved, as configurable
  mechanisms, before any Layer 4 label exists.
- §4/§10 explicitly forbid silently adopting the existing exploratory
  `onepiece-faisabilite/output/taxonomy.json` — it must be reviewed first.

## Tickets

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T009 | Layer 1 raw-notes accessor & integrity report | Should | T002 | S |
| T010 | Layer 2 event candidate extraction | Must | T009, T003 | L |
| T011 | Layer 2 extraction quality spot-check tooling | Should | T010 | M |
| T012 | Layer 3 taxonomy construction — frozen mode | Must | T010, T005, T004 | L |
| T013 | Layer 3 taxonomy construction — incremental mode | Could | T012 | M |
| T014 | Layer 3 taxonomy leakage guard tests | Must | T012 | S |
| T015 | Layer 4 final event label generation | Must | T012, T010 | M |
| T016 | Event label frequency thresholding | Must | T015 | M |
| T017 | Exploratory `taxonomy.json` review & comparison report | Should | T012 | M |

## Dependency notes

T012 (frozen-mode taxonomy) is the critical-path ticket of this epic: every
later ticket in the project that consumes event labels (EPIC-03 baselines,
EPIC-05 component 8, EPIC-06 models) depends on T015, which depends on T012.
T013 (incremental mode) is marked **Could** — §10 frames frozen vs.
incremental as a choice, not a requirement to implement both; v1 ships with
frozen mode and the incremental interface is added only if a rolling-origin
result later needs it. T017 is investigative and only needs T012 to exist as
a comparison point; it does not block T015 or anything downstream.

## Out of scope for this epic

- Using Layer 4 labels as model input features — that is EPIC-05 component 8
  (`State(t)` "recent events"), a consumer of this epic's output, not part of
  it.
- Relation extraction (§11) — tracked under EPIC-05 (`State(t)` component 2),
  since it feeds narrative state rather than the event-label target, even
  though it reuses this epic's extraction-procedure discipline.
- Resolving the §26 "taxonomy.json role" decision beyond producing the
  comparison report (T017) — reuse/adapt/discard is a project decision to be
  made from that report's findings, not a coding task.

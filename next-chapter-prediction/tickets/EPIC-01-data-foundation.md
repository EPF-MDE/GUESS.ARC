# EPIC-01 — Data Foundation

## Goal

Turn the `onepiece-faisabilite` silver corpus into a validated, chronologically
splittable, leakage-safe set of forecasting examples, before any taxonomy,
representation, or model work begins (SPEC §4, §6, §7, §16).

## Why this epic exists (SPEC anchors)

- §4 defines the only dataset source (`onepiece-faisabilite/data/silver/chapter_NNNN.md`)
  and its known coverage/quality issues.
- §6(a) makes chapter-chronology leakage prevention the project's first
  concern: "Random train/test splits are forbidden."
- §7 names the dataset-agnostic scaffold (`ChapterRecord`/`Book`/`Corpus`,
  `RecordMapper`, `DatasetConfig`) this epic must plug the silver corpus into,
  and flags that `configs/dataset/local.yaml` does not exist yet.
- §16 requires chronological holdout and rolling-origin protocols, with
  split boundaries "configurable... never hard-coded in analysis code."

## Tickets

| ID | Title | Priority | Dependencies | Complexity |
|---|---|---|---|---|
| T001 | Dataset config for the silver corpus | Must | — | S |
| T002 | `markdown_dir` loader for silver chapter files | Must | T001 | M |
| T003 | Dataset integrity validation command | Must | T002 | S |
| T004 | Construction-set-scoped artifact cache utility | Must | — | S |
| T005 | Chronological holdout split + leakage guard tests | Must | T002, T003 | M |
| T006 | Rolling-origin split generator | Must | T005 | M |
| T007 | Forecasting example builder (history window → t+1) | Must | T003, T005 | M |
| T008 | Auxiliary entity-presence target builder | Must | T002, T007 | S |

## Dependency notes

T001 and T004 have no internal dependencies and can start immediately and in
parallel. Everything else in this epic, and every later epic, ultimately
depends on T002 (the only way chapter text enters the pipeline) and T003 (the
only gate that confirms the loaded corpus is safe to split and extract from).
T005/T006 produce the split boundaries that every later taxonomy-construction
and representation-fitting ticket (EPIC-02 T012/T013, EPIC-04 T026/T027) must
receive as an explicit construction-set argument — this epic is where that
contract is first established, not re-derived per epic.

## Out of scope for this epic

- Anything that reads chapter *content* for narrative purposes (entities
  beyond raw front-matter, events, relations, state) — EPIC-02/04/05.
- Resolving the §26 "exact chronological split boundaries" research
  question — T005/T006 implement the mechanism with a documented default
  (~80/10/10 per §16), not the final research answer.
- Real-world publication dates (§4, §26) — explicitly not required for v1
  (§6b); no ticket in this epic touches `revised_at` as a timing signal.

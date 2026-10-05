# EPIC-05 — Narrative State (Tier D)

## Goal

Implement each of `State(t)`'s nine components (SPEC §8) as an independently
testable module, then assemble them into the Tier D feature vector that the
H1 experiment (state vs. text-only) and the H1/H3 component ablations (§18)
depend on.

## Why this epic exists (SPEC anchors)

- §8's formal definition: "`State(t)` must never be built, directly or
  indirectly, using any information first revealed in chapters > t... This
  rule binds every intermediate artifact... not only the final feature
  vector." This is the single most leakage-sensitive epic in the project.
- §8 lists all nine components with their own construction rule, allowed
  inputs, and availability — the rule "No ticket should implement several
  unrelated components" (project instructions) maps directly onto one
  ticket per component.
- §8 explicitly scopes v1: "v1 implements components 1, 3, 8, 9 with full
  fidelity. Components 2, 5, 6, 7 may be partial/heuristic in v1." Ticket
  priorities below reflect that split.
- §11 (relations) is "exploratory in v1" but is this epic's component 2
  source data, so its extraction ticket lives here rather than in EPIC-02.
- §12 (unresolved plotlines): "v1 may implement only the simplified version
  already covered by `State(t)` components 6–7" — this epic is where that
  simplification is implemented; full-fidelity thread tracking is **Later**
  (§25), not ticketed here.

## Tickets

| ID | Title | Priority | Dependencies | Complexity | §8 component |
|---|---|---|---|---|---|---|
| T031 | Character state ontology | Must | T003, T007 | L | 1 (full fidelity) |
| T032 | Relationship extraction with `evidenced_at` (§11) | Must | T010, T002 | L | 2 (partial) |
| T033 | Location tracking | Must | T010, T002 | M | 3 (full fidelity) |
| T034 | Active conflicts tracking | Must | T015 | M | 4 (feature) |
| T035 | Known facts tracking | Should | T010 | M | 5 (partial) |
| T036 | Unresolved questions tracking | Should | T034, T015 | M | 6 (partial) |
| T037 | Ongoing plot threads aggregation | Should | T034, T036, T002 | M | 7 (partial) |
| T038 | Recent-events rolling window | Must | T015, T007 | S | 8 (full fidelity) |
| T039 | Important objects/goals tracking | Must | T010 | M | 9 (full fidelity) |
| T040 | `State(t)` assembly (Tier D) + leakage guard tests | Must | T031–T039 | L | all |

## Dependency notes

T031, T033, T038, T039 (the full-fidelity components) are **Must** and have
no internal epic dependency on each other, so they can proceed in parallel
once their EPIC-01/02 inputs exist. T034→T036→T037 is a real chain: conflict
resolution-matching (T036) needs conflict tracking (T034) first, and plot
thread aggregation (T037) needs both. T040 is deliberately last and
deliberately **L**: per §8's own text, the per-component rules are necessary
but not sufficient — T040's acceptance criteria must re-verify the "as-of
chapter t" contract across all nine components assembled together, because a
correct component fed through an incorrect join can still leak.

## Out of scope for this epic

- Full-fidelity unresolved-plotline modeling beyond §8 components 6–7 —
  explicitly **Later** (§12, §25).
- The graph representation mentioned in `CLAUDE.md`'s "Planned
  representations" and `RepresentationConfig.name == "graph"` in the existing
  config scaffold — explicitly **Later** (§25), not part of Tier D.
- Treating this epic's relationship/fact/question components as a standalone
  prediction target — §11 is explicit that relations are "exploratory in v1,
  deferred... as a standalone prediction target."

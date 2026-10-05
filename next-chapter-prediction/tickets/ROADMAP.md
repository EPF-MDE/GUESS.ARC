# Implementation Roadmap — One Piece Next-Chapter Event Forecasting

Source of truth: `SPEC.md` (sections cited as `§N`). This roadmap does not
introduce any research requirement, metric, model, or target not already in
`SPEC.md`. Where `SPEC.md` marks a decision **[OPEN]**, the corresponding
ticket implements a *configurable mechanism* with a documented default — it
does not resolve the open research question itself.

Two epics in the requested structure — **EPIC-07 (sequential models)** and
**EPIC-09 (summary generation)** — correspond to work `SPEC.md` explicitly
places in **Later** scope, gated behind v1 core completing (§14, §20, §22,
§25). Per the instruction *"do not create tickets for speculative features
that are explicitly out of scope for v1,"* those two epic files exist (for
structural completeness and to carry the gate condition) but contain **zero**
implementation tickets. Nothing in v1 depends on them.

---

## 1. Epics

| Epic | File | Theme | SPEC anchor |
|---|---|---|---|
| EPIC-01 | `EPIC-01-data-foundation.md` | Ingestion, validation, chronological splits, forecasting windows | §4, §6, §7, §16 |
| EPIC-02 | `EPIC-02-event-taxonomy.md` | Event pipeline Layers 1–4 (candidates → taxonomy → labels) | §10, §26 |
| EPIC-03 | `EPIC-03-baselines.md` | Tier A trivial/statistical baselines | §13, §22 |
| EPIC-04 | `EPIC-04-representations.md` | Tier B (text-only) and Tier C (entity-aware) features | §9, §13 |
| EPIC-05 | `EPIC-05-narrative-state.md` | `State(t)` components 1–9 → Tier D features | §8, §11, §12 |
| EPIC-06 | `EPIC-06-event-forecasting.md` | Embedding+MLP model, H1–H3 experiments, ablations | §14, §15, §16, §17, §18 |
| EPIC-07 | `EPIC-07-sequential-models.md` | Tier E (GRU/LSTM/Transformer) — **Later, gated, no v1 tickets** | §14, §22, §25 |
| EPIC-08 | `EPIC-08-evaluation.md` | Metrics, protocol runner, provenance (early); rolling-origin aggregation and error analysis (late) | §16, §19, §21, §22 |
| EPIC-09 | `EPIC-09-summary-generation.md` | Summary generation — **Later, out of v1 scope, no v1 tickets** | §20, §25 |

EPIC-08 is split internally into **Part 1 — core infrastructure** (must exist
before any tier reports a metric, so it is consumed by EPIC-03 onward) and
**Part 2 — experiment analysis** (consumes model predictions produced by
EPIC-06, so it runs last). The file groups tickets by part; ticket IDs are
assigned once, in global dependency order, and are not re-used across epics.

## 2. Dependency graph (epic level)

```
EPIC-01 (data foundation)
   │
   ▼
EPIC-02 (event taxonomy) ──────────────┐
   │                                   │
   ▼                                   │
EPIC-08 Part 1 (metrics, protocol      │
   runner, provenance schema)          │
   │                                   │
   ▼                                   │
EPIC-03 (Tier A baselines) ◄───────────┘   (needs event labels from EPIC-02)
   │
   ▼
EPIC-04 (Tier B / Tier C representations)
   │
   ▼
EPIC-05 (Tier D narrative state)  ──needs event labels (EPIC-02) too
   │
   ▼
EPIC-06 (Embedding+MLP, H1/H2/H3, ablations)
   │
   ▼
EPIC-08 Part 2 (rolling-origin aggregation, error analysis, repro audit)
   │
   ▼
EPIC-07 (Tier E) ── GATED, no tickets yet — see §22 gate condition below
EPIC-09 (summary generation) ── OUT OF V1 SCOPE — see note below
```

Both EPIC-02 and EPIC-05 read `State(t)` component 8 ("recent events"),
which is itself sourced from EPIC-02's Layer 4 labels — this is a feature
dependency, not a cycle: component 8 at chapter `t` only ever reads labels
for chapters `≤ t`, which are produced once per chapter by EPIC-02 and never
recomputed per-tier.

## 3. Gate conditions for the two deferred epics

- **EPIC-07 (Tier E — sequential models).** Per §14 ("Later: GRU/LSTM/
  Temporal Transformer (Tier E), gated on Tiers B–D clearing Tier A under
  §22's criteria first") and §25. Do not open implementation tickets for
  this epic until EPIC-06's Tier B/C/D runs have been evaluated against
  Tier A under §22's acceptance criteria. When that gate clears, the H4
  experiment (Tier E vs. Tier D, §16 table, §18 last ablation row) becomes
  the first ticket of this epic — write it then, against the thenresults,
  not speculatively now.
- **EPIC-09 (summary generation).** Per §20 ("out of v1 core scope; deferred
  to Later... not part of v1's acceptance criteria") and §25 ("Summary
  generation until event prediction is validated"), and per `CLAUDE.md`
  ("Do not begin by directly generating the next chapter summary"). No
  ticket should exist for this epic until event prediction (EPIC-06) is
  validated and the project explicitly moves to Later scope.

## 4. Full ticket list (dependency order, global)

Legend — Priority: **Must** (blocks §22 acceptance criteria) / **Should**
(strengthens the result but v1 is coherent without it, e.g. heuristic
components explicitly allowed partial in §8) / **Could** (nice-to-have,
explicitly optional in SPEC, e.g. incremental taxonomy mode, sentence
embeddings). Complexity: **S**/**M**/**L**, no time units.

| ID | Title | Epic | Priority | Dependencies | Complexity |
|---|---|---|---|---|---|
| T001 | Dataset config for the silver corpus | 01 | Must | — | S |
| T002 | `markdown_dir` loader for silver chapter files | 01 | Must | T001 | M |
| T003 | Dataset integrity validation command | 01 | Must | T002 | S |
| T004 | Construction-set-scoped artifact cache utility | 01 | Must | — | S |
| T005 | Chronological holdout split + leakage guard tests | 01 | Must | T002, T003 | M |
| T006 | Rolling-origin split generator | 01 | Must | T005 | M |
| T007 | Forecasting example builder (history window → t+1) | 01 | Must | T003, T005 | M |
| T008 | Auxiliary entity-presence target builder | 01 | Must | T002, T007 | S |
| T009 | Layer 1 raw-notes accessor & integrity report | 02 | Should | T002 | S |
| T010 | Layer 2 event candidate extraction | 02 | Must | T009, T003 | L |
| T011 | Layer 2 extraction quality spot-check tooling | 02 | Should | T010 | M |
| T012 | Layer 3 taxonomy construction — frozen mode | 02 | Must | T010, T005, T004 | L |
| T013 | Layer 3 taxonomy construction — incremental mode | 02 | Could | T012 | M |
| T014 | Layer 3 taxonomy leakage guard tests | 02 | Must | T012 | S |
| T015 | Layer 4 final event label generation | 02 | Must | T012, T010 | M |
| T016 | Event label frequency thresholding | 02 | Must | T015 | M |
| T017 | Exploratory `taxonomy.json` review & comparison report | 02 | Should | T012 | M |
| T018 | Core evaluation metrics module | 08 | Must | — | M |
| T019 | Leakage-safe evaluation protocol runner | 08 | Must | T018, T005, T006, T007 | L |
| T020 | Run/result provenance schema & archive | 08 | Must | T019 | S |
| T021 | Baseline: predict-nothing & most-frequent-events | 03 | Must | T007, T015, T019 | S |
| T022 | Baseline: recent-event persistence | 03 | Must | T007, T015, T019 | S |
| T023 | Baseline: frequency-weighted recency | 03 | Must | T007, T015, T019 | S |
| T024 | Tier A baseline run & report | 03 | Must | T021, T022, T023, T019 | S |
| T025 | Windowed-history text assembly | 04 | Must | T007, T002 | M |
| T026 | TF-IDF encoder (Tier B) | 04 | Must | T025, T005, T004 | M |
| T027 | Sentence-embedding encoder (Tier B, optional) | 04 | Could | T025, T004 | M |
| T028 | Tier B leakage guard tests | 04 | Must | T026, T027 | S |
| T029 | Entity-history feature extraction (§9, Tier C) | 04 | Must | T008, T007 | M |
| T030 | Tier C feature assembly + leakage guard tests | 04 | Must | T026, T029 | S |
| T031 | Character state ontology (`State(t)` #1) | 05 | Must | T003, T007 | L |
| T032 | Relationship extraction with `evidenced_at` (§11, `State(t)` #2) | 05 | Must | T010, T002 | L |
| T033 | Location tracking (`State(t)` #3) | 05 | Must | T010, T002 | M |
| T034 | Active conflicts tracking (`State(t)` #4) | 05 | Must | T015 | M |
| T035 | Known facts tracking (`State(t)` #5) | 05 | Should | T010 | M |
| T036 | Unresolved questions tracking (`State(t)` #6) | 05 | Should | T034, T015 | M |
| T037 | Ongoing plot threads aggregation (`State(t)` #7) | 05 | Should | T034, T036, T002 | M |
| T038 | Recent-events rolling window (`State(t)` #8) | 05 | Must | T015, T007 | S |
| T039 | Important objects/goals tracking (`State(t)` #9) | 05 | Must | T010 | M |
| T040 | `State(t)` assembly (Tier D) + leakage guard tests | 05 | Must | T031–T039 | L |
| T041 | Embedding+MLP model architecture | 06 | Must | T019, T004 | M |
| T042 | Tier B training/evaluation run | 06 | Must | T041, T026 | S |
| T043 | Tier C training/evaluation run | 06 | Must | T041, T030 | S |
| T044 | Tier D training/evaluation run | 06 | Must | T041, T040 | S |
| T045 | H1 experiment report (Tier D vs. Tier B) | 06 | Must | T042, T044, T020 | M |
| T046 | H3 experiment report (Tier C vs. Tier B) | 06 | Must | T042, T043, T020 | M |
| T047 | H2 experiment: `history_size` sweep | 06 | Must | T042, T020 | L |
| T048 | Ablations: +entities / +events-as-input / +full state | 06 | Must | T030, T038, T040, T042 | L |
| T049 | Feature-overlap confound check (§18) | 06 | Must | T030, T040 | M |
| T050 | Rolling-origin aggregation for H1/H3 final comparison | 08 | Must | T045, T046, T006, T020 | M |
| T051 | Error analysis: repeat/explore decomposition | 08 | Should | T044, T018 | M |
| T052 | Error analysis: arc-transition breakdown | 08 | Should | T044, T002 | M |
| T053 | Error analysis: `State(t)` component-availability breakdown | 08 | Should | T040, T044 | M |
| T054 | Reproducibility/provenance audit | 08 | Must | T020, T050 | S |

54 tickets. None implement EPIC-07 or EPIC-09.

## 5. Why this order (rules applied)

1. **Dataset validation before modeling** — T003 (integrity validation) is a
   hard dependency of every split/example ticket (T005–T008) and of the
   extraction pipeline (T009+). Nothing downstream reads unvalidated data.
2. **Temporal split and forecasting windows before supervised forecasting** —
   T005–T007 exist before T015 (first supervised label table) and long
   before any model ticket (T041+).
3. **Event taxonomy defined and validated before event prediction** — T012
   (taxonomy construction) and T014 (its leakage guard) precede T015 (label
   generation), which precedes every model ticket.
4. **Baselines before complex models** — EPIC-03 (T021–T024) precedes
   EPIC-04–06. Tier A is rule-based and needs only EPIC-02's labels plus
   EPIC-08 Part 1's metrics, not any representation work.
5. **Narrative State independently testable** — T031–T039 each ship with
   their own acceptance criteria and tests before T040 assembles them into
   the Tier D feature vector; T040 adds its own leakage guard on top of the
   per-component ones.
6. **Evaluation infrastructure before experiments** — T018–T020 (EPIC-08
   Part 1) precede the first baseline run (T021) and every later experiment
   ticket. EPIC-08 Part 2 (T050–T054) runs only after EPIC-06 produces
   predictions to analyze.
7. **Temporal-causality statement per historical-data ticket** — every
   ticket touching chapters 1..t carries an explicit **Risks** entry on
   leakage, and tickets that construct a vocabulary/taxonomy/threshold
   (T012, T013, T016, T026, T027, T031–T040) additionally carry a
   **Non-goals** entry forbidding full-corpus fitting, per §15's rule that
   such functions must take an explicit construction-set argument.

## 6. Cross-check against SPEC.md

**Every core v1 requirement has at least one ticket** (§25 "Core v1" list):

| Core v1 requirement (§25) | Covered by |
|---|---|
| Chronological dataset | T001–T003 |
| Forecasting windows | T005–T007 |
| Event taxonomy | T009–T017 |
| Event labels | T015, T016 |
| Simple baselines | T021–T024 |
| Text representation | T025–T028 |
| Narrative-state representation | T031–T040 |
| Next-event prediction | T041–T044 |
| Rigorous evaluation | T018–T020, T050–T054 |
| Ablation study | T048, T049 |

**Every research hypothesis has the necessary tickets** (§3, §16 mapping
table):

| Hypothesis | Independent variable | Covered by |
|---|---|---|
| H1 — state > text-only | Tier D vs. B | T044, T042, T045, T050 |
| H2 — context length | `history_size` sweep | T047 |
| H3 — entities > text-only | Tier C vs. B | T043, T042, T046, T050 |
| H4 — sequential > static | Tier E vs. D | **Not ticketed in v1** — correctly gated to EPIC-07 per §14/§22; T044 (Tier D) is the baseline this future experiment will use. |

The auxiliary entity target (§5, §9) is covered by T008 and carried through
T021–T024's and T042–T044's reporting as a secondary metric, never
substituted for the primary event target, per §5/§13.

**No ticket contradicts SPEC.md.**
- No ticket performs a random train/test split (§6a) — T005/T006 are the
  only split-producing tickets and both are chronological/rolling-origin.
- No ticket adopts `onepiece-faisabilite/output/taxonomy.json` directly —
  T017 only reviews/compares it; T012 builds this project's own taxonomy.
- No ticket treats auxiliary entity presence as the primary target (§5) —
  T021–T049 all name the event label (§10 Layer 4) as primary, entities as
  secondary.
- No ticket schedules Tier E or summary generation inside v1 (§14, §20, §25)
  — see EPIC-07/EPIC-09 files.
- No ticket hard-codes a split boundary or taxonomy construction set (§15,
  §16) — T005, T006, T012, T013 all require an explicit construction-set /
  as-of-chapter argument as an acceptance criterion.

**No future information can accidentally enter the forecasting pipeline.**
Every ticket from T009 onward that builds a vocabulary, taxonomy,
classifier-input feature, or threshold has a **Risks** section naming the
specific leakage channel from §6/§23 and an acceptance criterion requiring a
test that asserts the construction set excludes chapters beyond the active
boundary. T014, T028, T030, and T040 are dedicated leakage-guard tickets
layered on top of the per-component checks, so the guarantee is checked at
three levels: per-component, per-tier, and per-taxonomy.

**The dependency order is coherent.** See §2 and §5 above; the table in §4
lists dependencies as concrete ticket IDs, all pointing strictly backward
(no ticket depends on a higher-numbered ticket, except where EPIC-08 Part 2
tickets depend on EPIC-06 tickets, which is the intended cross-epic edge
described in §1/§2).

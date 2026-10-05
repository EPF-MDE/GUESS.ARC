# One Piece Next-Chapter Event Forecasting — Project Specification

This document is the single source of truth for the project's scope, data,
representations, models, evaluation protocol, and open decisions. Any
implementation choice that contradicts this document should either update
the document (with rationale) or be treated as a bug.

Status markers used throughout:

- **[OPEN]** — a design decision that has not been made yet. Do not infer
  an answer from surrounding text; see §26 for the full list.
- **[UNKNOWN]** — a factual question about the data or environment that
  has not been verified yet.

---

## 1. Problem statement

This project studies whether machine learning can predict the important
narrative **events** of the next chapter of *One Piece* from all
information available up to the current chapter. One Piece is used as a
single, long, continuous narrative (1193 chapters at time of writing).

The project is structured as a forecasting pipeline, not a text
classification task:

```
chapters 1...t
  → representation of narrative history/state
  → prediction of events in chapter t+1
```

Character/entity presence in chapter t+1 is a related, simpler signal and
is retained as an **auxiliary** prediction task (§5, §9) — it must never
be substituted for event prediction as the project's primary deliverable.

## 2. Research question

**Primary:** Does an explicit narrative-state representation improve
next-event prediction compared with text-only representations?

**Secondary:**
- How does context length affect prediction?
- Do explicit entities improve prediction?
- Do extracted events (as input history) improve prediction?
- Does modeling unresolved plotlines improve prediction?
- Do temporal (sequential) models outperform static models?
- Does better event prediction improve generated summaries?

## 3. Research hypotheses

- **H1** — Explicit narrative state improves next-event prediction
  compared with text-only representations.
- **H2** — Increasing historical context improves prediction up to a
  point, after which additional context provides diminishing returns or
  noise.
- **H3** — Entity-aware representations improve prediction compared with
  text-only representations.
- **H4** — Modeling narrative events/state sequentially improves
  prediction compared with static chapter representations. **[Later — see
  §14/§25]**

Every hypothesis has a corresponding experiment with an explicit
independent variable, dependent variable, baseline, protocol, and metrics
— see the mapping table in §16, and the full experiment specs in §17–§18.

## 4. Dataset

**Source and location.** English-language One Piece Fandom wiki, ingested
via the MediaWiki API by the separate `onepiece-faisabilite/` pipeline
(not part of this project's codebase, but its only data source):

- `onepiece-faisabilite/data/bronze/chapters.jsonl` — raw wikitext archive,
  one line per chapter (`number`, `revid`, `timestamp`, `wikitext`).
  Archival only; not modeled directly.
- `onepiece-faisabilite/data/silver/chapter_NNNN.md` — one file per
  chapter: YAML front-matter (`chapter`, `title`, `jname`, `arc`,
  `revision_id`, `revised_at`, `complete`, `character_count`,
  `characters: [{name, faction, on_panel}]`, `source`, `license`) plus a
  Markdown body (`Short Summary`, `Long Summary`, `Chapter Notes` bullets,
  a trailing plain-text character list with `(cover)`/`(flashback)`
  annotations).

License: CC BY-SA (academic use with attribution).

**Coverage, verified by direct inspection:**
- 1193 chapters, numbered 1–1193, contiguous, no missing chapters, no
  duplicate chapters.
- Every inspected chapter has `arc`, `complete: true`, and a non-empty
  `Long Summary`.

**Known data-quality issues:**
- `jname` is corrupted (literal unparsed wikitext, `"{{Ruby"`) in
  195 / 1193 chapters. Does not affect `Long Summary`/`Chapter Notes`.
- The front-matter `on_panel` boolean collapses two distinct appearance
  types — `cover` and `flashback` — that remain distinguishable only in
  the trailing plain-text character list. Whether to preserve this
  distinction is **[OPEN]** (§26).
- `revised_at` is a **wiki-edit timestamp**, not the chapter's real-world
  publication date. No field in the dataset encodes the actual release
  date. **[UNKNOWN]** whether/how to obtain real publication dates (§6,
  §26) — not required for v1, which uses chapter order only.

**Related but separate artifact — not part of this dataset's ground
truth:** `onepiece-faisabilite/output/` contains an exploratory tag
taxonomy (`taxonomy.json`, categories `perso, lieu, objet, event, rel,
groupe, pouvoir, fruit, navire, arme, poneglyphe`) built by a NER +
embedding + HDBSCAN pipeline over free text. This is **raw exploratory
material only**. It is explicitly **not** adopted as this project's
event/entity vocabulary until its categories are inspected and evaluated
(§10, §26).

## 5. Input and prediction target

- **Primary target (v1):** the set of normalized **events** occurring in
  chapter t+1 (§10, Layer 4 — "final event labels"), predicted from a
  narrative-history/state representation built only from chapters 1..t.
- **Auxiliary target:** character/entity presence in chapter t+1 (§9).
  Retained because the wiki's character table makes it cheap to measure
  and because it may be a useful secondary signal, but it is explicitly
  **not** a substitute for the primary event target, and no section of
  this spec may silently redefine "the prediction target" to mean
  entities.
- **Input:** chapters 1..t, accessed only through the representations
  defined in §7–§12.

## 6. Temporal formulation

Two distinct leakage channels are tracked separately; only the first is
in scope for v1.

**(a) Chapter chronology leakage — in scope, must be prevented.**
For target chapter t+1, every feature must be constructed exclusively
from chapters 1..t. Never use:
- future chapters
- future summaries
- future entity states
- future relations
- future events
- future arc information
- annotations derived from future chapters
- any vocabulary, taxonomy, cluster, or threshold fit using chapters
  beyond the active split/evaluation boundary (see §10 Layer 3, §16)

Random train/test splits are forbidden; only chronological splits and
rolling-origin evaluation are used (§16).

**(b) External real-world spoiler leakage — explicitly out of scope for
v1.** The model consumes only the internal chapter sequence as stored in
the dataset; it never uses leak/spoiler timing, real-world publication
dates, or any signal external to the chapters themselves. This is why the
`revised_at` **[UNKNOWN]** publication-date gap (§4) does not block v1:
chapter order, not real-world timing, is what the model uses.

## 7. Data representation

Chapters are mapped onto the existing dataset-agnostic scaffold already
present in this repository (`ncp.data.schema.ChapterRecord` / `Book` /
`Corpus`, `ncp.data.mapping.RecordMapper`, `ncp.config.schema.DatasetConfig`,
loaders for `jsonl`/`csv`/`markdown_dir`). The silver `.md` directory is
the intended source for the `markdown_dir` loader, with YAML front-matter
fields mapped into `ChapterRecord.metadata`.

**[OPEN]** No dataset config has been written yet
(`configs/dataset/local.yaml` does not exist). This is a required
pre-implementation step, not a research decision — tracked for
completeness but not a scientific open question.

## 8. Narrative state representation

**Formal definition:**

```
State(t) := everything that can be inferred or reconstructed
            using chapters 1...t only.

Hard rule: State(t) must never be built, directly or indirectly,
using any information first revealed in chapters > t.
```

This rule binds every intermediate artifact used to build `State(t)` —
vocabularies, clusters, thresholds, relationship extractions, taxonomy
categories — not only the final feature vector. If any intermediate
artifact is fit on data beyond chapter t, `State(t)` is contaminated even
if no sentence from chapter t+1 is read directly.

**Character state ontology.** Each character has an explicit status at t,
drawn from a closed set (thresholds **[OPEN]**, §26):

| Status | Meaning (evaluated using chapters 1..t only) |
|---|---|
| `introduced` | First appearance is in chapters ≤t; no further status established. |
| `active` | Has appeared within a defined recency window ending at t. |
| `inactive` | Introduced, but has not appeared within the recency window; no deceased/unknown evidence. |
| `deceased` | Death explicitly depicted or stated in chapters ≤t. |
| `unknown` | In-story status is explicitly ambiguous as of t (e.g. "presumed dead") — distinct from `inactive`, which is narrative absence, not textual ambiguity. |

**Relationship temporal validity.** Every relationship instance carries
`evidenced_at` — the chapter where it first became explicit. A
relationship is included in `State(t)` **if and only if**
`evidenced_at ≤ t`.

> Example: if a relationship becomes explicit in chapter 500, it must be
> absent from `State(100)` and `State(499)`, and present from `State(500)`
> onward — even though it was "always true" in the fictional timeline.
> `State(t)` models what is knowable from the text at t, not fictional
> ground truth. The same evidenced-at discipline applies to `known facts`
> and `unresolved questions` below.

**Components of `State(t)`.** For each: what it contains · how
constructed · what information it may use · availability at prediction
time · classification.

1. **Active characters**
   - Contains: character → status (ontology above), as of t.
   - Constructed from: cumulative union of appearances/mentions in
     chapters 1..t, status rule applied per character.
   - Allowed inputs: chapters 1..t only; no global corpus statistics that
     depend on chapters beyond t.
   - Available at prediction time: yes, by construction.
   - Classification: **feature** (for predicting t+1); also the basis of
     the auxiliary entity target (§9) at t+1.

2. **Relationships**
   - Contains: typed edges between entities with `evidenced_at`.
   - Constructed from: relation extraction (§11), filtered by
     `evidenced_at ≤ t`.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes, subject to the evidenced-at
     filter.
   - Classification: **feature**.

3. **Locations**
   - Contains: current/recent narrative setting(s) of the active cast.
   - Constructed from: location mentions in chapters 1..t.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes.
   - Classification: **feature**.

4. **Active conflicts**
   - Contains: antagonistic situations introduced, not yet resolved as of
     t.
   - Constructed from: event candidates (§10 Layer 2) tagged
     conflict-initiating, with no matching resolution event in 1..t.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes.
   - Classification: **feature**.

5. **Known facts**
   - Contains: canonical facts revealed by t (in-story epistemic state,
     not necessarily the eventual retconned "truth").
   - Constructed from: explicit statements/reveals in 1..t, each with an
     `evidenced_at`.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes.
   - Classification: **feature**.

6. **Unresolved questions**
   - Contains: mysteries raised and not textually answered by t.
   - Constructed from: question-raising events/statements in 1..t minus
     those with a matching resolution event in 1..t (ties to §12).
   - Allowed inputs: chapters 1..t — resolution must never be detected by
     reading chapters beyond t.
   - Available at prediction time: yes.
   - Classification: **feature**; also raw material for the
     resolved-vs-open diagnostic in §19 (**evaluation-only** in that use).

7. **Ongoing plot threads**
   - Contains: higher-level arcs/goals in progress.
   - Constructed from: aggregation of active conflicts + unresolved
     questions + arc metadata known as of t.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes, in whatever simplified form v1
     implements (full fidelity is Later scope, §25).
   - Classification: **feature**.

8. **Recent events**
   - Contains: rolling window of the most recent k items from §10 Layer 4,
     for chapters ≤t.
   - Constructed from: §10's pipeline applied only to chapters ≤t, using
     whichever taxonomy mode is active for the run.
   - Allowed inputs: chapters 1..t; the taxonomy itself must not have been
     built using chapters beyond t (§10).
   - Available at prediction time: yes.
   - Classification: **feature** (distinct from the chapter t+1 event
     labels used as the prediction **target**).

9. **Important objects/goals**
   - Contains: artifacts, Devil Fruits, stated goals introduced and still
     relevant as of t.
   - Constructed from: entity/event extraction restricted to chapters
     1..t, tracked with the same status logic as characters.
   - Allowed inputs: chapters 1..t.
   - Available at prediction time: yes.
   - Classification: **feature**.

v1 implements components 1, 3, 8, 9 with full fidelity. Components 2, 5,
6, 7 may be partial/heuristic in v1. Exact scope is **[OPEN]** (§26).

## 9. Entity representation

- **Contains:** per-chapter character list with faction and appearance
  annotation (on-panel / cover / flashback; exact granularity **[OPEN]**,
  §26), sourced from wiki front-matter.
- **Constructed from:** direct parsing of chapter t's own front-matter.
- **Allowed inputs:** only chapter t's own front-matter when representing
  chapter t.
- **Availability at prediction time:** the chapter-t entity list is
  available as a feature for predicting t+1 (via `State(t)` component 1).
  The chapter-(t+1) entity list is **not** available at prediction time —
  it is a label.
- **Classification:** dual role —
  - as history (chapters ≤t): **feature**.
  - as the chapter-(t+1) target: **auxiliary target** (never a
    replacement for the primary event target, §5).
- **Documented risk:** retrospective/hindsight curation by wiki editors —
  chapter-t annotations may encode knowledge the editor had of chapters
  beyond t at edit time. This is a labeling-integrity risk (§23), not a
  feature-leakage risk, since the chapter-t annotation is only ever used
  as a label for chapter t itself.

## 10. Event representation

The event pipeline has four layers. **No layer below Layer 1 is assumed
to already be ground truth** — in particular, Chapter Notes are raw
editorial text, not validated event annotations, until they pass through
Layers 2–4 and that process is itself validated.

**Layer 1 — Raw Chapter Notes**
- Contains: editorial bullet points as stored in silver `.md`.
- Constructed from: wiki editing of chapter t's page.
- Allowed inputs: not applicable — this is the raw source. Its integrity
  question is whether it was edited with hindsight (§23, §26).
- Available at prediction time: for chapters ≤t only, by definition
  (chapter t+1's notes are exactly what must never be used).
- Classification: **raw material** — not a feature or target directly.

**Layer 2 — Event candidates**
- Contains: short structured/semi-structured event mentions extracted
  from chapter t's own notes/summary.
- Constructed from: an extraction procedure (method **[OPEN]**:
  rule-based / NER / LLM-assisted) applied chapter-by-chapter.
- Allowed inputs: chapter t's own text, plus a fixed shared extraction
  procedure whose parameters must never be fit on statistics computed
  over chapters beyond t.
- Available at prediction time: for chapters ≤t only.
- Classification: **intermediate artifact** — feeds Layer 3 and, for
  chapters ≤t, `State(t)` component 8.

**Layer 3 — Normalized event taxonomy**
- Contains: canonical event categories (e.g. `combat_strike`) that event
  candidates map onto.
- Constructed from: clustering/normalization of candidates, in one of two
  modes (choice **[OPEN]**, §26):
  - **(a) Frozen** — built once from a designated construction set (e.g.
    the train split or an initial chapter prefix), then frozen, with a
    defined fallback (`other`) for unmapped future candidates.
  - **(b) Incremental** — rebuilt only from chapters ≤t at each
    evaluation point.
- Allowed inputs: whichever construction set is designated for the active
  mode — **never** the full corpus including test chapters, in either
  mode, for any number reported as a final result. Building the taxonomy
  from the full corpus and evaluating on the same chapters is a leakage
  path even though no single label reads chapter t+1's text directly —
  the vocabulary itself would have seen the future.
- Available at prediction time: the taxonomy active at t must reflect only
  information available at or before t (mode b), or a pre-frozen
  construction set that itself respects the split (mode a).
- Classification: **vocabulary/artifact** — not itself a feature or
  target; it is the lens Layer 4 is read through.
- Explicit note: the existing exploratory `onepiece-faisabilite/output/taxonomy.json`
  is **not** adopted as this layer's taxonomy. Its categories must be
  inspected and evaluated first (§4, §26) before any decision to reuse,
  adapt, or discard it.

**Layer 4 — Final event labels**
- Contains: per-chapter supervised event labels, from applying the
  frozen/incremental taxonomy to that chapter's candidates.
- Constructed from: Layers 1–3, versioned (extraction version + taxonomy
  version).
- Allowed inputs: chapter t's own candidates, read through a taxonomy that
  itself only used information available at/before the relevant split
  boundary.
- Available at prediction time: chapter-(t+1) labels are **not** available
  at prediction time — they are the target. Chapter-≤t labels **are**
  available, feeding `State(t)` component 8.
- Classification: **primary prediction target** (chapter t+1) /
  **feature** (chapters ≤t, via `State(t)`).

**Minimal candidate event schema** (strawman, **not yet validated** —
§26):

```
event:
  chapter: int
  event_type: str
  participants: list[str]
  location: str | None
  object: str | None
  evidence: str
```

Open and unresolved: participant roles (agent vs. target), events
spanning multiple chapters, confidence/ambiguity scoring (§26).

## 11. Relations

- **Contains:** typed edges between two entities (e.g. `ally_of`,
  `enemy_of`, `sibling_of`), each with `evidenced_at`.
- **Constructed from:** per-chapter extraction from text/co-occurrence,
  same extraction-procedure discipline as §10 Layer 2.
- **Allowed inputs:** chapter t's own text; `evidenced_at` must be the
  first chapter where the relation became explicit, never inferred later
  and back-dated.
- **Availability at prediction time:** a relation is available for
  predicting t+1 only if `evidenced_at ≤ t` (same rule as §8 component 2,
  since relations are that component's source data).
- **Classification:** **feature** (via `State(t)` component 2);
  exploratory in v1, deferred past core scope (§25) as a standalone
  prediction target.

## 12. Unresolved plotlines

- **Contains:** open narrative threads (mysteries, goals, promises)
  tracked as open/resolved per chapter.
- **Constructed from:** §8 components 6–7 — a thread is "open" at t if
  raised in 1..t with no matching resolution event in 1..t.
- **Allowed inputs:** chapters 1..t; resolution must be detected at the
  chapter where it is textually resolved, never by reading ahead to
  confirm a thread will be resolved.
- **Availability at prediction time:** yes, for chapters ≤t.
- **Classification:** **feature** (as part of `State(t)`). Full-fidelity
  thread tracking is **Later** scope (§25) — v1 may implement only the
  simplified version already covered by `State(t)` components 6–7.

## 13. Baselines

The numbers reproduced from `onepiece-faisabilite/faisabilite-etat-de-lart.md`
(persistence 53.0% F1 micro, frequency-weighted top-25 53.1%, etc.) are
**baselines to reproduce with this project's own code and evaluation
protocol**, not unquestioned ground truth, and not a mandatory bar (§22).
They were measured on the character/entity target, not the event target,
and must be re-measured on whichever target(s) each experiment uses.

| Tier | Predicts using | Construction | Available at prediction time | Supports hypothesis |
|---|---|---|---|---|
| A — Trivial/statistical | predict-nothing, most-frequent, persistence, frequency-weighted recency, union/intersection of last-k | rule-based, no learning | yes (uses only ≤t) | sanity baseline for all H1–H4 |
| B — Text-only ML | TF-IDF/embedding of chapter-window summary text | simple classifier (logistic/GBM/MLP) | yes | baseline for H1, H3 |
| C — Entity-aware | Tier B features + entity representation (§9, history only) | same classifier family | yes | tests H3 |
| D — Narrative-state | full `State(t)` (§8) as engineered features | same classifier family | yes | tests H1 |
| E — Sequential | raw chapter sequence, learned temporal dynamics | GRU/LSTM/Transformer | yes | tests H4 |

All tiers are evaluated under the identical split/protocol (§16). The
target for all tiers in v1 core is the primary event label (§10 Layer 4);
the auxiliary entity target (§9) is reported alongside, never substituted.

## 14. ML models

- **v1 core:** Embedding+MLP architecture, instantiated three ways — Tier
  B inputs, Tier C inputs, Tier D inputs — producing the H1/H3 comparison
  pair from one architecture family, removing architecture choice as a
  confound.
- **Later:** GRU/LSTM/Temporal Transformer (Tier E), gated on Tiers B–D
  clearing Tier A under §22's criteria first.

## 15. Training strategy

- Config-driven (`ncp.config.schema.Config`), fixed seeds per
  `ExperimentConfig.seed`.
- Every run records: representation tier, `State(t)` component scope
  used, event-taxonomy version, extraction version, and split/protocol
  identifier — so any result is traceable to the leakage-relevant choices
  that produced it.
- Incremental complexity ordering: Tier A → B → C → D → (gate) → E.
- Any function that builds a vocabulary, taxonomy, or threshold must take
  an explicit "as-of chapter" or "construction set" argument. No such
  function may silently default to "the whole dataset."

## 16. Chronological evaluation

**Split policy.** Strictly chronological; boundaries configurable via
`ForecastingConfig.split_ratios` / explicit chapter cut points — never
hard-coded in analysis code. Initial recommendation: approximately
80/10/10 by chapter count. The exact final cut is **[OPEN]** (§26); this
spec intentionally does not hard-code 1–1000/1001–1100/1101–1193 or any
other fixed boundary.

**Protocols** (both supported):
- **Chronological holdout** — one fixed train/val/test boundary. Cheap
  for iteration; risk of being an artifact of where the cut lands relative
  to arc boundaries.
- **Rolling-origin** (expanding or sliding window) — multiple forecast
  origins aggregated. Preferred for the final cross-tier comparison;
  window type, step size, and number of origins are **[OPEN]** (§26).

Whichever protocol is active, the event taxonomy (§10 Layer 3) and any
`State(t)` vocabulary must be constructed respecting that protocol's
boundaries — never from the full corpus.

**Metrics.** Micro-F1, Macro-F1, Precision, Recall, Precision@K,
Recall@K (K≈20) on event labels (primary) and on the auxiliary entity
target (secondary, reported alongside). Accuracy is explicitly excluded
(a predict-nothing model scores ~98.57% accuracy on the character task —
the trivial-zero-baseline problem documented in the feasibility doc).

**Hypothesis → experiment mapping** (each cell must exist as a concrete
run before a hypothesis is claimed tested):

| Hypothesis | Independent variable | Dependent variable | Baseline | Protocol | Metrics |
|---|---|---|---|---|---|
| H1 — state > text-only | representation: Tier D vs. Tier B | event-label F1/P@K/R@K | Tier B | holdout + rolling-origin | Micro-F1, Macro-F1, P@K, R@K |
| H2 — context length | `history_size` (sweep) | event-label F1 | same tier at minimal `history_size` | holdout (confirm on rolling-origin if signal found) | Micro-F1, Macro-F1 |
| H3 — entities > text-only | representation: Tier C vs. Tier B | event-label F1/P@K/R@K | Tier B | holdout + rolling-origin | Micro-F1, Macro-F1, P@K, R@K |
| H4 — sequential > static | model: Tier E vs. Tier D | event-label F1/P@K/R@K | Tier D | rolling-origin | Micro-F1, Macro-F1, P@K, R@K |

## 17. Context-length experiments

- **Hypothesis:** H2.
- **Independent variable:** `history_size` ∈ a configured sweep (small →
  full available history).
- **Dependent variable:** event-label Micro-F1/Macro-F1 (primary);
  auxiliary entity-label F1 (secondary).
- **Baseline:** same tier/model at the smallest `history_size` in the
  sweep.
- **Evaluation protocol:** holdout split for the initial sweep; confirm
  any non-monotonic finding on rolling-origin before reporting it as
  conclusive.
- **Metrics:** Micro-F1, Macro-F1, plus a metric-vs-`history_size` curve
  to locate the point of diminishing returns.
- **Confound to control:** long-context difficulty (§23) — report whether
  degradation at large `history_size` is tier-specific, to separate "more
  history helps" from "this architecture handles long context poorly."

## 18. Ablation experiments

Design principle: change exactly one representational ingredient at a
time, holding model family, split, and taxonomy version fixed.

| Ablation | Hypothesis tested | Independent variable | Dependent variable | Baseline | Protocol | Metrics |
|---|---|---|---|---|---|---|
| text-only vs. +entities | H3 | presence of §9 features | event-label F1 | text-only | holdout + rolling-origin | Micro-F1, Macro-F1, P@K/R@K |
| text-only vs. +past events as input | component of H1 | presence of §10 Layer 4 history features | event-label F1 | text-only | holdout + rolling-origin | Micro-F1, Macro-F1 |
| text-only vs. +full narrative state | H1 | presence of full `State(t)` | event-label F1 | text-only | holdout + rolling-origin | Micro-F1, Macro-F1, P@K/R@K |
| static state vs. sequential | H4 | Tier D vs. Tier E | event-label F1 | Tier D | rolling-origin | Micro-F1, Macro-F1, P@K/R@K |

**Required confound check before interpreting any delta:**
feature-overlap/correlation analysis between text embeddings and derived
entity/event/state features — a small ablation delta may reflect
redundancy, not low informativeness.

## 19. Error analysis

- Repeat/explore decomposition (Li et al., *A Next Basket Recommendation
  Reality Check*, TOIS 2023) applied to event-label predictions.
- Dedicated breakdown at arc-transition chapters (documented in the
  feasibility doc as disproportionately hard: F1 drops from ~54.2% to
  ~37.5% at arc boundaries, affecting 32/1192 transitions).
- Breakdown by `State(t)` component availability — whether errors
  concentrate on chapters where heuristic/partial v1 components (e.g.
  unresolved questions, active conflicts) were weakest.
- This section is diagnostic, explaining why a tier over/underperforms
  using predictions already produced in §16–§18 — it does not define a
  new independent run.

## 20. Summary generation

- **Contains:** a generated prose summary of chapter t+1.
- **Constructed from:** predicted event labels (not free-form generation
  from scratch), conditioned on the model's own t+1 event predictions.
- **Allowed inputs:** chapters 1..t and the model's own predicted t+1
  event labels; never the real chapter t+1 text.
- **Availability at prediction time:** yes, by construction, once gated on
  event-prediction quality.
- **Classification:** **out of v1 core scope**; deferred to **Later**
  (§25). Not part of v1's acceptance criteria (§22). Per CLAUDE.md, the
  project must not begin by directly generating the next chapter summary.

## 21. Reproducibility

- Fixed seeds, versioned configs archived per run.
- Every reported number tagged with: split/protocol identifier, taxonomy
  version, extraction version, `State(t)` component scope.
- No fabricated or placeholder results; an untested hypothesis/tier is
  reported as "not yet run," never estimated.
- Expensive intermediate artifacts (embeddings, extracted candidates)
  cached, keyed by their construction-set identifier, so a cached artifact
  built under one split boundary is never silently reused under another.

## 22. Acceptance criteria

The project's success is **not** defined as "beat the 53% F1 persistence
baseline." Minimum requirement for scientific completeness:

- Tier A baselines are reproduced reliably under the chosen protocol (a
  pipeline sanity check, not a target).
- All tiers in scope are compared under strictly identical evaluation
  conditions (same split/protocol, same event-label version).
- H1–H4 are each tested with a reported effect size and direction,
  including null or negative effects.
- Every result carries its full provenance tag (§21).
- A negative outcome ("narrative state does not improve prediction on
  this corpus, under this taxonomy") is an acceptable, complete project
  result, provided the above conditions hold.

## 23. Research risks

- **Temporal leakage** — via features, via taxonomy construction (§10
  Layer 3), via `State(t)` components built from global corpus
  statistics.
- **Retrospective wiki annotations** — chapter-t text/labels possibly
  edited with knowledge of chapters beyond t.
- **Imperfect event labels** — extraction (§10 Layer 2) precision/recall
  errors set a ceiling independent of model quality.
- **Taxonomy instability** — re-running clustering with different
  parameters/construction sets shifts category boundaries; mitigated only
  by strict versioning (§15, §21).
- **Class imbalance** — long-tailed event/entity distributions affect
  metric choice and may require frequency thresholds (§26).
- **Arc distribution shift** — chronological splits necessarily separate
  arcs; known performance cliffs at arc transitions.
- **Long-context difficulty** — standard degradation at large
  `history_size`, to be disentangled from genuine context-helps effects
  (§17).
- **Subjective definition of narrative events** — no single agreed
  definition; H1/H4 conclusions are conditional on §10's taxonomy choices.

## 24. Limitations

- **Single-work case study** — findings are specific to this manga's
  narrative structure and this wiki's annotation conventions; no claim of
  generalization to other serialized fiction without further validation.
- **Labels are wiki-derived, not independently human-verified ground
  truth** — final event labels and entity annotations inherit whatever
  errors/conventions the source wiki has, including the retrospective-
  editing risk (§23).
- **Sample size** — 1193 chapters is small by deep-learning standards;
  sequential models (Tier E) are especially exposed to overfitting, which
  is why they are gated behind simpler tiers (§14).
- **English-only source** — French/Japanese sources were evaluated and
  rejected for coverage/latency reasons in the feasibility doc; results
  say nothing about non-English fan-annotation ecosystems.
- **No causal claims** — the project tests predictive association between
  representation type and forecasting accuracy, not a causal mechanism of
  narrative construction.
- **Taxonomy-dependent conclusions** — because "event" is operationalized
  by a taxonomy built under this project's choices (§10), results cannot
  be directly compared to a differently-operationalized "event
  prediction" task elsewhere.

## 25. Out of scope

- External spoiler/leak-based signals (explicitly rejected in the
  feasibility doc; see §6b).
- Non-English wiki sources (French/Japanese).
- Real-time weekly ingestion/automation (belongs to the
  `onepiece-faisabilite` pipeline, not this project).
- Summary generation (§20) until event prediction is validated.
- Graph representation, full unresolved-plotline modeling, GRU/LSTM/
  Transformer (Tier E) — all **Later**, gated on v1 core (§22) completing
  first.

**V1 scope, explicitly:**
- **Core v1:** chronological dataset, forecasting windows, event
  taxonomy, event labels, simple baselines, text representation,
  narrative-state representation, next-event prediction, rigorous
  evaluation, ablation study.
- **Later:** graph representation, unresolved plotlines (full fidelity),
  GRU/LSTM/Transformer, summary generation.

## 26. Decision log / unresolved design decisions

| Decision | What must be resolved | Needed before |
|---|---|---|
| Publication dates | Whether/how to obtain real-world release timestamps | any external-leakage-adjacent work (§6b, §23) |
| Event taxonomy construction method | rule-based vs. NER vs. LLM-assisted; frozen vs. incremental mode | any Layer 4 event label exists |
| `taxonomy.json` role | category-by-category review of the existing `onepiece-faisabilite` output | deciding reuse vs. discard (§4, §10) |
| Event label frequency threshold | which event types are frequent enough to model individually vs. `other` | finalizing Layer 4 labels |
| Character state ontology thresholds | exact recency window for `active`/`inactive`; `unknown` trigger conditions | building §8 component 1 |
| Relationship `evidenced_at` extraction mechanism | how first-explicit-chapter is detected/verified | building §8 component 2 / §11 |
| Character appearance granularity | preserve cover/flashback distinction vs. collapsed boolean | finalizing the §9 auxiliary target |
| Exact chronological split boundaries | final cut(s), beyond the initial ~80/10/10 recommendation | any final reported number (§16) |
| Rolling-origin evaluation design | window type, step size, number of origins, aggregation method | §16's final cross-tier comparison |
| Retrospective-edit check for wiki annotations | method to verify chapter-t text wasn't edited using later-chapter knowledge | trusting any wiki-derived label as leakage-free |
| Narrative-state component scope for v1 | which of §8's nine components get full fidelity vs. heuristic vs. deferred | building Tier D |
| Event schema finalization | participant roles, multi-chapter events, confidence scoring | specifying Layer 2 extraction |

---

*This specification corresponds to the 1–26 section structure approved
during the specification-design conversation preceding this document. It
supersedes any informal notes or prior partial drafts.*

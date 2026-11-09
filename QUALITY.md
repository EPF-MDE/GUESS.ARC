# Quality requirements & test policy

Quality requirements for what we deliver to the client (Konrad), how we check them, and the
evidence that we did. Updated every project week. Requirement IDs are `REQ-n`, so they aren't
confused with the grid criteria Q1–Q3. IDs are never reused.

| Grid | What it asks | Where it lives in this file |
|---|---|---|
| **Q1** | You questioned and specified the quality requirements of your product | §1 Requirements |
| **Q2** | You defined how you'll know each requirement is met | §2 Verification |
| **Q3** | You actually ran those checks | §2 *Result* and *Evidence* columns + §3 Log |

---

## 1. Requirements (Q1)

### Delivery Thu 2026-11-12 (entities) and Fri 2026-11-13 (mid-term defense)

| ID | Requirement | Characteristic | Metric & threshold | Why it matters (client need) | Validated by client? |
|---|---|---|---|---|---|
| REQ-12 | The entity extraction finds the Characters of each chapter, and doesn't invent extra ones. *(Carried over from 2026-10-30.)* | Functional suitability | Recall ≥ 0.95 of the on-panel Characters of the Silver header found in `Registry(t)`, overall; precision ≥ 0.80 of the Registry's Characters present in the header, overall. | The entities are an input of the GRU, and the Cast is what it predicts. | ☐ |
| REQ-13 | Name variants resolve to one Entity ("Luffy" = "Monkey D. Luffy"), and different Entities stay distinct ("Fake Luffy" ≠ "Luffy"). *(Carried over from 2026-10-30.)* | Functional suitability | ≥ 95 % of extracted names resolve to a Canonical name; 0 wrong merges in a manual review of 20 random Aliases. | One Character split across several names, or two merged, corrupts the GRU's inputs and targets. | ☐ |
| REQ-19 | The entity dataset covers the whole corpus. | Functional suitability | `data/gold/registry.jsonl` covers chapters 1–1193, and every chapter has ≥ 1 Scene. | The GRU trains on the whole story, not on a sample. | ☐ |
| REQ-20 | The Registry only contains what the reader knows at chapter t (ADR 0002). | Reliability | 0 Entities in `Registry(t)` before their first Mention or Appearance. | Any future information in the inputs would leak the answer and inflate the scores. | ☐ |
| REQ-17 | Someone else can rerun the entity extraction from the README alone. | Maintainability | A teammate on a fresh clone gets the same `registry.jsonl` with 0 undocumented steps. | Konrad must be able to run the pipeline after we leave. | ☐ |
| REQ-18 | Every number shown at the defense is traceable to a run or a document. | Reliability | 100 % of the numbers on the slides point to a commit, config and chapter list, or to a document. | The jury and the client must be able to trust and check what we claim. | ☐ |
| REQ-21 | The mid-term defense fits its slot (2026-11-13, 11:15–12:45: 20 min talk, 45 min questions, then debrief). | Usability | The talk lasts ≤ 20 min in a full timed rehearsal before 2026-11-13. | Going over the time cuts into the questions, where the work is evaluated. | ☐ |

### Delivery Fri 2026-10-30: GRU presentation and entity dataset

Committed: a presentation of how the GRU works and the entity dataset. For the events, we only
committed to start looking into them. Vectorisation wasn't part of this delivery.

| ID | Requirement | Characteristic | Metric & threshold | Why it matters (client need) | Validated by client? |
|---|---|---|---|---|---|
| REQ-5 | The Silver corpus covers every published chapter, 1 to 1193, with no gaps. | Functional suitability | 1193 files, 0 missing chapter numbers. | Every later stage reads the Silver Files. | ☐ |
| REQ-6 | Every Silver File has a front-matter whose `chapter` matches its file name, `complete: true` and a `revision_id`. | Reliability | 0 files failing. | A mislabelled or incomplete file would silently shift the chapter sequence. | ☐ |
| REQ-7 | Every Silver File has a non-empty Long Summary, plus its Short Summary and Chapter Notes sections. | Functional suitability | 0 empty Long Summaries; min/median/max length reported. | The Long Summary is the text the extraction works on. | ☐ |
| REQ-8 | The header's `character_count` matches the Characters actually listed. | Reliability | 0 mismatches. | This list is the reference for entity extraction (REQ-12). | ☐ |
| REQ-15 | The GRU pipeline design is written down: inputs, what it predicts for chapter n+1, the baselines it must beat, and the metrics. | Maintainability | A design document covers all four points: yes / no. | Konrad needs to understand and agree with the approach before we build it. | ☑ 2026-10-30, Konrad |
| REQ-16 | The design uses no future information: chronological train/val/test split, everything fitted on training chapters only. | Reliability | The design specifies a chronological split and fitting on training chapters only: yes / no. | Leakage would make the results meaningless. | ☑ 2026-10-30, Konrad |

REQ-12 and REQ-13 (entities) were also committed for this delivery. They were not finished and
are carried over to 2026-11-12 (see above).

### Delivery Fri 2026-10-23: Taxonomy Gold research and POC

| ID | Requirement | Characteristic | Metric & threshold | Why it matters (client need) | Validated by client? |
|---|---|---|---|---|---|
| REQ-1 | The taxonomy is defined in a documented schema, and each structural decision is recorded with its rationale. | Maintainability | Schema document exists and every structural choice has an ADR: yes / no. | The client must be able to understand and extend the taxonomy. | ☑ 2026-10-23, Konrad |
| REQ-2 | A POC tags real chapters into that schema with an LLM. | Functional suitability | ~10 chapters tagged into valid files. | Shows whether the taxonomy can actually be produced. | ☑ 2026-10-23, Konrad (accepted as partial) |
| REQ-3 | The research concludes, with evidence, whether the LLM route can produce the Taxonomy Gold for all 1193 chapters. | Performance | The conclusion cites measured limits (quotas, tokens per chapter, chapters tagged): yes / no. | Konrad decides whether to keep investing in this route. | ☑ 2026-10-23, Konrad |
| REQ-4 | If the route doesn't scale, an alternative pipeline is proposed, with why it's more likely to work. | Functional suitability | An alternative is presented with its inputs, outputs and trade-offs: yes / no. | Avoids a dead end for the rest of the project. | ☑ 2026-10-23, Konrad |

### Backlog (not committed yet)

Kept here so the IDs stay reserved. Each comes back into a delivery when a sprint commits to it.

- **REQ-9**: each chapter gets exactly one Chapter Embedding, built from its Long Summary only.
- **REQ-10**: every set of vectors comes with a manifest (model, chunking rule, chapter list, silver `revision_id`s).
- **REQ-11**: re-running vectorisation on the same input gives identical vectors.
- **REQ-14**: events are extracted from each chapter's Long Summary (who did what to whom), each traceable to its source sentence.

## 2. Verification (Q2 → Q3)

Status: ⏳ not run yet · ✅ pass · ⚠️ partial · ❌ fail (what we do about it is in §3)

### Delivery Thu 2026-11-12 and Fri 2026-11-13

| ID | Verification method | Pass criterion | When | Owner | Result | Evidence |
|---|---|---|---|---|---|---|
| REQ-12 | Compare `Registry(t)` Characters with the Silver header's on-panel Characters, per chapter, then aggregate. | Recall ≥ 0.95 and precision ≥ 0.80 | Before delivery (12/11) | Team | ⏳ | |
| REQ-13 | Count extracted names resolved to a Canonical name; manually review 20 random Aliases. | ≥ 95 % resolved, 0 wrong merges | Before delivery (12/11) | Team | ⏳ | |
| REQ-19 | Read `registry.jsonl` and `registry_quality.json`. | Chapters 1–1193 present, ≥ 1 Scene each | Before delivery (12/11) | Team | ⏳ | |
| REQ-20 | Test: for every Entity, no Registry row with `valid_from` before its first Mention or Appearance. | 0 violations | Automatic (test suite) | Team | ⏳ | |
| REQ-17 | A teammate follows the README on a fresh clone and notes every step that failed. | Same output, 0 undocumented steps | Before delivery (12/11) | Team | ⏳ | |
| REQ-18 | Spot-check each number on the slides against its run output or document. | 100 % traceable | Before defense (13/11) | Team | ⏳ | |
| REQ-21 | Full timed rehearsal of the talk. | ≤ 20 min | Before defense (13/11) | Team | ⏳ | |

### Delivery Fri 2026-10-30

| ID | Verification method | Pass criterion | When | Owner | Result | Evidence |
|---|---|---|---|---|---|---|
| REQ-5 | `scripts/quality/check_silver.py` counts the files and lists missing numbers. | 1193 files, 0 missing | Each sprint | Team | ✅ | 2026-10-26 run: 1193 files (1193 expected), no missing chapters. `data/bronze/chapters.jsonl` also has 1193 lines. |
| REQ-6 | Same script, per file. | 0 files failing | Each sprint | Team | ✅ | Same run: 0 files failing. |
| REQ-7 | Same script; also reports the Long Summary length. | 0 empty Long Summaries | Each sprint | Team | ✅ | Same run: min 97, median 598, max 2094 words. |
| REQ-8 | Same script. | 0 mismatches | Each sprint | Team | ✅ | Same run: `character_count` matches in all 1193 files. |
| REQ-15 | A teammate reviews the design document against the four points. | All four covered | Before demo | Team | ✅ | `GRU.md` (delivered to Konrad on Teams; also on branch `data_event`): inputs (§0, §3), prediction of chapter n+1 (§4.5), baselines "persistance" and global frequency (§3.4), metrics F1 and Precision@K. |
| REQ-16 | Review of the design; leakage-guard test once the split code exists. | Chronological split, fitting on training chapters only | Before demo | Team | ✅ | `GRU.md` §2.7: train 1..N, validation N+1..M, test M+1..T, never mixed; §3.4: sliding origins; §4.5: decision threshold tuned on validation, never on test. |
| REQ-12, REQ-13 | Entity extraction compared with the Silver header. | See 2026-11-12 | Before demo | Team | ⚠️ | Not finished on 2026-10-30 (first `Registry(t)` in PR #80, ENT-02 to ENT-08 still open). Carried over to 2026-11-12. |

Output of the run behind REQ-5 to REQ-8:

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

To check that the check itself works, we ran it on a copy of two chapters with one Long Summary
emptied and `--expected 3`. It reported `Chapitres manquants : [3]` and
`chapter_0002.md: Long Summary vide`, then exited with code 1.

### Delivery Fri 2026-10-23

| ID | Verification method | Pass criterion | When | Owner | Result | Evidence |
|---|---|---|---|---|---|---|
| REQ-1 | Check the schema document and the ADRs. | Every structural choice has an ADR | Before demo | Team | ✅ | Schema: `docs/taxonomy-schema.md` and `.json` (commit `3bfa198`). Decisions: ADRs 0001–0006 (commit `8c0f99f`). Both on branch `search/taxonomy`. |
| REQ-2 | Run `API/taxonomy_client.py` on the POC chapters and count the valid tagged files. | ~10 chapters | Before demo | Team | ⚠️ | **2 chapters** tagged out of ~10: the free LLM tiers didn't allow more in the time we had. Pipeline on branch `API_LLM_taxonomie` (fallback chain across 5 providers, quota tracking, repair of malformed answers, 15 test files). |
| REQ-3 | Measure quotas, tokens per chapter and chapters actually tagged. | The conclusion rests on measurements | Before demo | Team | ✅ | **The LLM route doesn't scale to 1193 chapters on free tiers** (`API/README.md` on `API_LLM_taxonomie`): about 5–7k tokens per chapter; Groq allows 8k tokens per minute, so at most one chapter per minute; Gemini about 20 requests per day; OpenRouter's free models share 50 requests per day. |
| REQ-4 | Present the alternative to the client. | Inputs, outputs and trade-offs presented | Before demo | Team | ✅ | GRU pipeline proposed: forecast chapter n+1 from vectorised past chapters plus extracted entities and events, without a full LLM taxonomy. |

## 3. Log (one entry per project week)

### Weeks of 02/11 & 09/11 (entities Thu 12/11, mid-term defense Fri 13/11)
- Added: REQ-19, REQ-20, REQ-21. REQ-12 and REQ-13 carried over with measurable thresholds. REQ-9–11 and REQ-14 moved to the backlog: they were never committed.
- Checked: nothing yet (all ⏳).
- Planned to show: the finished entity dataset (`Registry(t)`) with its recall/precision (REQ-12, REQ-13, REQ-19, REQ-20), then the mid-term defense on 13/11.
- Next: once the entities are done, benchmark an API solution with an Anthropic model for the following sprints.

### Week of 26/10 (delivery Fri 30/10)
- Added: REQ-15, REQ-16 (GRU design); REQ-12, REQ-13 (entities).
- Checked: REQ-5–8 ✅ (Silver corpus, 2026-10-26); REQ-15, REQ-16 ✅ (`GRU.md`); REQ-12, REQ-13 ⚠️, entities not finished.
- Shown to client: the presentation of how the GRU works (`GRU.md`, delivered on Teams). The entity dataset wasn't finished. Events: work started, nothing promised.
- Client said: satisfied, but disappointed about the entities.
- Decision: continue with the GRU pipeline; finish the entities first, then benchmark an API solution with an Anthropic model.
- Next: finish the entities (REQ-12, REQ-13, REQ-19, REQ-20) for 12/11.

### Week of 19/10 (delivery Fri 23/10)
- Added: REQ-1–4.
- Checked: REQ-1, REQ-3, REQ-4 ✅; REQ-2 ⚠️ (2 chapters instead of ~10).
- Shown to client: the taxonomy (REQ-1); the 2 chapters tagged by the LLM pipeline (REQ-2); the research result: tagging chapter summaries with free LLMs can't scale to 1193 chapters (REQ-3); the GRU pipeline as an alternative (REQ-4).
- Client said: satisfied with the work done; validated REQ-1–4, with REQ-2 accepted as partial.
- Decision: stop building the Taxonomy Gold with LLMs; move to the GRU pipeline.
- Next: GRU presentation and entity dataset for 30/10.

## 4. Data & confidentiality rules

- Data that must **never** be committed (paths, file types): `data/` (bronze, silver, gold and `state.json`) and `.env` (API keys).
- Where the data actually lives (who has access): generated locally by each teammate from the public English One Piece Fandom wiki (`python -m guess_arc.ingestion`). The source is public, under CC BY-SA, and used for academic purposes with attribution.
- Tools/services **not** allowed by the client: none so far. Sending chapter text (public wiki content) to the Anthropic API is allowed, with the key kept in `.env`.
- Personal data involved (GDPR) and how it is handled: none. The corpus only covers fictional characters.
- Matching `.gitignore` entries are in place: ☑ (`data/`, `.env`)

# QUALITY.md

Quality requirements for what we deliver to the client (Konrad), how we check them, the
evidence that we did, and what the client validated. Updated every week and attached to
that week's client commitment (see §3 Log).

Requirement IDs are `REQ-n`, so they aren't confused with the grid criteria Q1–Q3.
Each requirement belongs to one delivery (column **Delivery**), and IDs are never reused.

## §1 Requirements and how we check them

### Delivery 2026-10-23: Taxonomy Gold research and POC

| ID | Requirement | How we check it |
|---|---|---|
| REQ-1 | The taxonomy is defined in a documented schema, and each structural decision is recorded with its rationale. | `docs/taxonomy-schema.md` exists and every structural choice has an ADR (`docs/adr/0001`–`0006`). |
| REQ-2 | A POC tags real chapters into that schema with an LLM: about 10 chapters. | Run `API/taxonomy_client.py` on the POC chapters and count the valid tagged files it writes. |
| REQ-3 | The research concludes, with evidence, whether the LLM route can produce the Taxonomy Gold for all 1193 chapters. | The conclusion cites measured limits (quotas, tokens per chapter, chapters actually tagged) rather than opinion. |
| REQ-4 | If the route doesn't scale, an alternative pipeline is proposed, with why it's more likely to work. | An alternative is presented to the client with its inputs, outputs and trade-offs. |

### Delivery 2026-10-30: GRU pipeline research and POC (vectorisation and extraction)

The POC runs on **10 chapters at most**.

**Input data: the Silver Files**

| ID | Requirement | How we check it |
|---|---|---|
| REQ-5 | The corpus covers every published chapter, 1 to 1193, with no gaps. | `scripts/quality/check_silver.py` counts the files and lists missing numbers. |
| REQ-6 | Every Silver File has a front-matter whose `chapter` matches its file name, `complete: true` and a `revision_id`. | Same script, per file. |
| REQ-7 | Every Silver File has a non-empty Long Summary, plus its Short Summary and Chapter Notes sections. | Same script; also reports the min/median/max Long Summary length. |
| REQ-8 | The header's `character_count` matches the Characters actually listed. This list is our reference for entity extraction (REQ-12). | Same script. |

**Vectorisation**

| ID | Requirement | How we check it |
|---|---|---|
| REQ-9 | Each POC chapter gets exactly one Chapter Embedding, built from its Long Summary only: no header, no Short Summary, no Chapter Notes, so the cast can't leak into the vector. | Test: the vector count matches the chapter count; a header marker word never reaches the embedded text. |
| REQ-10 | Every set of vectors comes with a manifest (model, chunking rule, chapter list, silver `revision_id`s), so vectors from different settings can't be mixed. | Test: the manifest exists and matches the vectors; loading with a different config fails. |
| REQ-11 | Re-running vectorisation on the same input gives identical vectors. | Run it twice and compare hashes. |

**Extraction of entities and events**

| ID | Requirement | How we check it |
|---|---|---|
| REQ-12 | Entities (Characters) are extracted from each POC chapter's Long Summary and match the Silver header's character list. | Precision and recall against the header list (on-panel Characters), per chapter. |
| REQ-13 | Name variants resolve to one Character ("Luffy" = "Monkey D. Luffy"), and different Characters stay distinct ("Fake Luffy" ≠ "Luffy"). | Count the extracted names that map to a header Character; manually review the ones that don't. |
| REQ-14 | Events are extracted from each POC chapter's Long Summary: who did what to whom, with each event traceable to the sentence it came from. | A teammate reviews every event of the POC chapters against its source sentence and against the chapter's Chapter Notes (the wiki's list of key events); we report the share judged correct and the share of Chapter Notes covered. |

**GRU pipeline research**

| ID | Requirement | How we check it |
|---|---|---|
| REQ-15 | The GRU pipeline design is written down: inputs (chapter vectors, entities, events), what it predicts for chapter n+1, the baseline it must beat (persistence, 53% micro F1) and the metrics. | A design document is committed to the repo and reviewed by a teammate against this list. |
| REQ-16 | The design uses no future information: chronological train/val/test split, and everything fitted on training chapters only. | Review of the design; leakage-guard test once the split code exists. |

**For the whole delivery**

| ID | Requirement | How we check it |
|---|---|---|
| REQ-17 | Someone else can rerun the POC from the README alone. | A teammate follows the README on a fresh clone and notes every step that failed. |
| REQ-18 | Every number shown to the client is traceable to a run (commit, config, chapters). | Spot-check each number on the slides or in the demo against its run output. |

## §2 Result and Evidence

Result: **PASS** (checked and met) · **PARTIAL** (met in part, see evidence) · **FAIL**
(checked, not met) · **NOT YET** (the work isn't done yet).

### Delivery 2026-10-23

| ID | Result | Evidence | Validated by client? |
|---|---|---|---|
| REQ-1 | **PASS** | Schema: `docs/taxonomy-schema.md` and `.json` (commit `3bfa198`). Decisions: ADRs 0001–0006 (commit `8c0f99f`). Both on branch `search/taxonomy`. | ☑ 2026-10-23, Konrad |
| REQ-2 | **PARTIAL** | **2 chapters** tagged out of the ~10 targeted: the free LLM tiers didn't allow more in the time we had. Pipeline: branch `API_LLM_taxonomie` (`API/taxonomy_client.py`, a fallback chain across 5 providers, quota tracking, repair of malformed answers, 15 test files). TODO: commit the 2 tagged chapters; `data/` is git-ignored, so they aren't on GitHub yet. | ☑ 2026-10-23, Konrad |
| REQ-3 | **PASS** | Conclusion: **the LLM route doesn't scale to 1193 chapters on free tiers.** Measured limits (`API/README.md` on `API_LLM_taxonomie`): one chapter costs about 5–7k tokens; Groq allows 8k tokens per minute, so at most one chapter per minute; Gemini allows about 20 requests per day; OpenRouter's free models share 50 requests per day. Only 2 chapters were tagged in practice. | ☑ 2026-10-23, Konrad |
| REQ-4 | **PASS** | GRU pipeline proposed and presented to the client: forecast chapter n+1 from vectorised past chapters plus extracted entities and events, so we no longer depend on a full LLM taxonomy. The embedding side is specified in issue #78. | ☑ 2026-10-23, Konrad |

### Delivery 2026-10-30

| ID | Result | Evidence | Validated by client? |
|---|---|---|---|
| REQ-5 | **PASS** | 2026-10-26: `check_silver.py` → 1193 files (1193 expected), no missing chapters. `data/bronze/chapters.jsonl` also has 1193 lines. | ☐ |
| REQ-6 | **PASS** | Same run: 0 files failing. | ☐ |
| REQ-7 | **PASS** | Same run: every Long Summary is non-empty, with min 97, median 598 and max 2094 words. | ☐ |
| REQ-8 | **PASS** | Same run: `character_count` matches the listed Characters in all 1193 files. | ☐ |
| REQ-9 – REQ-11 | NOT YET | Vectorisation POC in progress (issue #78). | ☐ |
| REQ-12 – REQ-14 | NOT YET | Extraction POC in progress. | ☐ |
| REQ-15 – REQ-16 | NOT YET | GRU design document in progress. | ☐ |
| REQ-17 – REQ-18 | NOT YET | Checked just before the delivery. | ☐ |

Output of the run behind REQ-5 to REQ-8:

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

To check that the check itself works, we ran it on a copy of two chapters with one Long
Summary emptied and `--expected 3`. It reported `Chapitres manquants : [3]` and
`chapter_0002.md: Long Summary vide`, then exited with code 1.

## §3 Log

One entry per client delivery, newest first. Each entry says what was committed, where
that commitment is written, which requirements apply, what the client saw, and what they
said.

### Delivery Friday 2026-10-30: GRU pipeline research and POC

| | |
|---|---|
| **Committed to deliver** | Research on the GRU pipeline, and a POC of its first stages: **vectorisation** of chapters and **extraction of entities and events**, on 10 chapters at most. |
| **Where it's written** | Meeting notes of 2026-10-23 with Konrad. TODO: link or path to the notes. |
| **Requirements** | REQ-5 – REQ-8 (input data), REQ-9 – REQ-11 (vectorisation), REQ-12 – REQ-14 (extraction), REQ-15 – REQ-16 (GRU research), REQ-17 – REQ-18 (reproducibility). |
| **Status on 2026-10-26** | REQ-5 – REQ-8 PASS; the rest NOT YET (see §2). |
| **Planned to show the client** | The GRU design document (REQ-15, REQ-16); vectors and their manifest for the POC chapters (REQ-9 – REQ-11); extracted entities with their precision and recall (REQ-12, REQ-13); extracted events next to their source sentences (REQ-14). |
| **Shown to client** | To fill in on Friday. |
| **Client said** | To fill in on Friday. |
| **Validated** | To fill in on Friday: tick each confirmed REQ in §2 with date and name. |

### Delivery Friday 2026-10-23: Taxonomy Gold research and POC

| | |
|---|---|
| **Committed to deliver** | Research on how to build the Taxonomy Gold, and a small POC of it (about 10 chapters). |
| **Where it's written** | Meeting notes of 2026-10-16 with Konrad. TODO: confirm date and link. |
| **Requirements** | REQ-1 – REQ-4. |
| **Shown to client** | The current taxonomy (REQ-1); the 2 chapters tagged by the LLM pipeline (REQ-2); the research result: tagging chapter summaries with free LLMs doesn't work and can't work at the scale of 1193 chapters (REQ-3); the research on a new pipeline (the GRU pipeline), which is more likely to give good results (REQ-4). |
| **Client said** | Satisfied with the work done. |
| **Validated** | The whole deliverable: REQ-1 – REQ-4, Konrad, 2026-10-23. REQ-2 was accepted as PARTIAL (2 chapters instead of ~10). |
| **Decision** | Stop building the Taxonomy Gold with LLMs; move to the GRU pipeline (next delivery). |

## §4 Coding practices (CP1)

What we already do (visible on GitHub):

- **One issue → one branch → one PR**, merged after review (PRs #1, #73, #76, #77).
  Issues are written as user stories with acceptance criteria (#78).
- **Decisions are recorded as ADRs** (`docs/adr/` on `search/taxonomy`, ADR 0001 on
  `architecture`), and **shared vocabulary** lives in `CONTEXT.md` (on `search/taxonomy`),
  so code, issues and docs use the same terms.
- **Small, descriptive commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`);
  secrets kept out of git (`.env` ignored).
- **Tests with pytest/unittest, without network access**: 15 test files on
  `API_LLM_taxonomie`, and 34 parser and bronze/silver contract tests on `architecture`.
- **Installable package and configuration instead of hard-coded values**: `pyproject.toml`
  and `src/guess_arc/` on `architecture`; `ruff` is configured in `next-chapter-prediction`.

What we start this week:

- Every check in §1 becomes a script or a test that anyone can rerun. The first one is
  `scripts/quality/check_silver.py` (REQ-5 – REQ-8).
- Tests are written together with the POC code (REQ-9 – REQ-13), not after it.
- Every result file records its commit, config and chapter list (REQ-18).

Known gaps: no CI runs the tests on each PR yet, and the tests on other branches weren't
rerun for this report.

## §5 Documentation (D1)

| Document | For whom | Status |
|---|---|---|
| `README.md` | Anyone cloning the repo: setup, ingestion, running the checks | Exists; "Vérifications qualité" section added this week. POC usage to be added (REQ-17). |
| `CONTEXT.md` | Everyone: the project's vocabulary | On `search/taxonomy`; to bring to `main`. |
| `docs/adr/` | Future maintainers: why the structure is what it is | ADRs 0001–0006 (taxonomy) on `search/taxonomy`; ADR 0001 (wiki source) on `architecture`. To bring to `main`. |
| `docs/taxonomy-schema.md` | Reference for the taxonomy shown on 2026-10-23 | On `search/taxonomy`; no longer extended, since the taxonomy route was dropped. |
| GRU design document | Whoever builds the GRU pipeline | To write this week (REQ-15). |
| `QUALITY.md` | Client and teacher: what "good" means and the proof | This file, updated every week. |
| Issue #78 | Whoever implements the vectorisation | Full spec with user stories. |

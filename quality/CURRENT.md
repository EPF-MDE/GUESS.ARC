# Current quality requirements

> **Generated, do not edit.** Rebuilt from the threads in `requirements/` by `python scripts/quality/regenerate.py`. To change it, record an entry in a thread and regenerate (see [README.md](README.md)).

What the team must reach now: every open requirement (not signed off ✅, not rejected, not dropped) committed to a delivery, plus every recurring one with its latest result. Every requirement that ever existed, backlog included, is listed in [OVERVIEW.md](OVERVIEW.md).

| Grid | What it asks | Where it is shown |
|---|---|---|
| **Q1** | You questioned and specified the quality requirements of your product | Each requirement below: statement, characteristic, metric & threshold, why. Its thread shows what the team proposed and what the client accepted, amended or rejected. |
| **Q2** | You defined how you'll know each requirement is met | *Verification*, *When* and *Owner* of each requirement below |
| **Q3** | You actually ran those checks | *Latest result* and its evidence below; every `verified` entry, with its evidence and raw output, in the threads |

## REQ-5 · Silver corpus complete

The Silver corpus covers every published chapter, 1 to 1193, with no gaps.

- **Characteristic:** Functional suitability
- **Metric & threshold:** 1193 files, 0 missing chapter numbers.
- **Why (client need):** A missing chapter leaves a hole in the story the forecasts learn from and are judged on.
- **Verification:** `scripts/quality/check_silver.py` counts the files and lists missing numbers.
- **When:** Each sprint
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** yes
- **Client status:** signed off ✅
- **Latest result:** ✅ (2026-10-26)

Evidence:

2026-10-26 run: 1193 files (1193 expected), no missing chapters. `data/bronze/chapters.jsonl` also has 1193 lines.

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

Thread: [requirements/REQ-5.yaml](requirements/REQ-5.yaml)

## REQ-6 · Silver front-matter consistent

Every Silver File has a front-matter whose `chapter` matches its file name, `complete: true` and a `revision_id`.

- **Characteristic:** Reliability
- **Metric & threshold:** 0 files failing.
- **Why (client need):** Forecasting chapter n+1 relies on the chapter order; a mislabelled or incomplete file would silently shift it.
- **Verification:** `scripts/quality/check_silver.py`, per file.
- **When:** Each sprint
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** yes
- **Client status:** signed off ✅
- **Latest result:** ✅ (2026-10-26)

Evidence:

2026-10-26 run: 0 files failing.

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

Thread: [requirements/REQ-6.yaml](requirements/REQ-6.yaml)

## REQ-7 · Silver summaries present

Every Silver File has a non-empty Long Summary, plus its Short Summary and Chapter Notes sections.

- **Characteristic:** Functional suitability
- **Metric & threshold:** 0 empty Long Summaries; 0 files missing the Short Summary or Chapter Notes section.
- **Why (client need):** A chapter without its summary contributes nothing to the forecasts.
- **Verification:** `scripts/quality/check_silver.py`; it also reports the Long Summary length.
- **When:** Each sprint
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** yes
- **Client status:** signed off ✅
- **Latest result:** ✅ (2026-10-26)

Evidence:

2026-10-26 run: min 97, median 598, max 2094 words.

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

Thread: [requirements/REQ-7.yaml](requirements/REQ-7.yaml)

## REQ-8 · Silver character_count matches

The header's `character_count` matches the Characters actually listed.

- **Characteristic:** Reliability
- **Metric & threshold:** 0 mismatches.
- **Why (client need):** The entity quality figures shown to Konrad (REQ-11) are only as trustworthy as this list.
- **Verification:** `scripts/quality/check_silver.py`.
- **When:** Each sprint
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** yes
- **Client status:** signed off ✅
- **Latest result:** ✅ (2026-10-26)

Evidence:

2026-10-26 run: `character_count` matches in all 1193 files.

```text
$ python scripts/quality/check_silver.py
Fichiers silver           : 1193 (attendu 1193)
Chapitres manquants       : aucun
Fichiers en échec         : 0
Mots du Long Summary      : min 97, médiane 598, max 2094
RÉSULTAT                  : OK
```

Thread: [requirements/REQ-8.yaml](requirements/REQ-8.yaml)

## REQ-9 · GRU pipeline design written down

The GRU pipeline design is written down: inputs, what it predicts for chapter n+1, the baselines it must beat, and the metrics.

- **Characteristic:** Maintainability
- **Metric & threshold:** 4/4 points covered in a written design document.
- **Why (client need):** Konrad must be able to check that the model answers his question before weeks go into building it.
- **Verification:** A teammate reviews the design document against the four points.
- **When:** Before demo
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** no
- **Client status:** signed off ⚠️
- **Latest result:** ⚠️ (2026-10-30)

Evidence:

The pipeline design exists only as a block diagram (image), validated by Konrad on 2026-10-30. The written design document doesn't exist yet; once written, it will be reviewed against the four points and submitted to Konrad for validation.

Thread: [requirements/REQ-9.yaml](requirements/REQ-9.yaml)

## REQ-10 · No future information in the GRU design

The design uses no future information: chronological train/val/test split, everything fitted on training chapters only.

- **Characteristic:** Reliability
- **Metric & threshold:** 2/2 rules specified in the design (chronological split; fitting on training chapters only), and 0 violations in the leakage-guard test once the split code exists.
- **Why (client need):** Konrad needs scores that hold on chapters not yet published; leakage would inflate them.
- **Verification:** Review of the design; leakage-guard test once the split code exists.
- **When:** Before demo
- **Owner:** Team
- **Delivery:** 2026-10-30
- **Recurring:** no
- **Client status:** accepted
- **Latest result:** ❌ (2026-10-30)

Evidence:

0/2 rules written down: neither the chronological split nor fitting on training chapters only appears in the block diagram or in any document. Only the input side is covered: ADR 0002 (`docs/adr/0002-reader-knowledge-only.md` on branch `extraction/entities`) keeps future facts out of KG(t). The leakage-guard test doesn't exist yet (no split code). Action: write both rules into the design document (REQ-9).

Thread: [requirements/REQ-10.yaml](requirements/REQ-10.yaml)

## REQ-11 · Characters found, none invented

The entity extraction finds the Characters of each chapter in its Long Summary, and doesn't invent extra ones.

- **Characteristic:** Functional suitability
- **Metric & threshold:** The two proxies from the extraction's quality report (ENT-02 #81, ENT-04 #83). **Recall proxy**: share of Characters with an Appearance in the chapter's CharTable that have ≥ 1 Mention in the same chapter's Long Summary; ≥ 0.95 overall, ≥ 0.80 in every chapter. **Precision proxy**: share of Alias-matched Mentions of Characters whose Character is in that chapter's Cast (Appearance, Recall or Cover appearance); ≥ 0.80 overall, ≥ 0.50 in every chapter.
- **Why (client need):** A missed or invented Character feeds the GRU a wrong history, so Konrad's forecasts get worse.
- **Verification:** Read the recall proxy and precision proxy from the extraction's quality report (`registry_quality.json`), overall and per chapter.
- **When:** Before delivery (12/11)
- **Owner:** Team
- **Delivery:** 2026-11-12
- **Recurring:** no
- **Client status:** awaiting client
- **Latest result:** ⚠️ (2026-10-30)

Evidence:

Not finished on 2026-10-30 (first `Registry(t)` in PR #80, ENT-02 to ENT-08 still open).

Thread: [requirements/REQ-11.yaml](requirements/REQ-11.yaml)

## REQ-12 · Name variants resolved

Name variants resolve to one Entity ("Luffy" = "Monkey D. Luffy"), and different Entities stay distinct ("Fake Luffy" ≠ "Luffy").

- **Characteristic:** Functional suitability
- **Metric & threshold:** ≥ 95 % of extracted names resolve to a Canonical name; 0 wrong merges in a manual review of 20 random Aliases.
- **Why (client need):** One Character split across several names, or two merged, corrupts the GRU's inputs and targets.
- **Verification:** Count extracted names resolved to a Canonical name; manually review 20 random Aliases.
- **When:** Before delivery (12/11)
- **Owner:** Team
- **Delivery:** 2026-11-12
- **Recurring:** no
- **Client status:** awaiting client
- **Latest result:** ⚠️ (2026-10-30)

Evidence:

Not finished on 2026-10-30 (first `Registry(t)` in PR #80, ENT-02 to ENT-08 still open).

Thread: [requirements/REQ-12.yaml](requirements/REQ-12.yaml)

## REQ-13 · Entity extraction rerunnable from the README

Someone else can rerun the entity extraction from the README alone.

- **Characteristic:** Maintainability
- **Metric & threshold:** A teammate on a fresh clone gets the same `registry.jsonl` with 0 undocumented steps.
- **Why (client need):** Konrad must be able to run the pipeline after we leave.
- **Verification:** A teammate follows the README on a fresh clone and notes every step that failed.
- **When:** Before delivery (12/11)
- **Owner:** Team
- **Delivery:** 2026-11-12
- **Recurring:** no
- **Client status:** awaiting client
- **Latest result:** ⏳ not verified yet

Thread: [requirements/REQ-13.yaml](requirements/REQ-13.yaml)

## REQ-14 · Entity dataset covers the whole corpus

The entity dataset covers the whole corpus.

- **Characteristic:** Functional suitability
- **Metric & threshold:** `data/gold/entities/registry.jsonl` covers chapters 1–1193, and every chapter has ≥ 1 Scene.
- **Why (client need):** The GRU trains on the whole story, not on a sample.
- **Verification:** Read `registry.jsonl` and `registry_quality.json`.
- **When:** Before delivery (12/11)
- **Owner:** Team
- **Delivery:** 2026-11-12
- **Recurring:** no
- **Client status:** awaiting client
- **Latest result:** ⏳ not verified yet

Thread: [requirements/REQ-14.yaml](requirements/REQ-14.yaml)

## REQ-15 · Registry limited to what the reader knows

The Registry only contains what the reader knows at chapter t (ADR 0002, `docs/adr/0002-reader-knowledge-only.md` on branch `extraction/entities`).

- **Characteristic:** Reliability
- **Metric & threshold:** 0 Entities in `Registry(t)` before their first Mention or Appearance.
- **Why (client need):** Any future information in the inputs would leak the answer and inflate the scores.
- **Verification:** Test: for every Entity, no Registry row with `valid_from` before its first Mention or Appearance.
- **When:** Automatic (test suite)
- **Owner:** Team
- **Delivery:** 2026-11-12
- **Recurring:** yes
- **Client status:** awaiting client
- **Latest result:** ⏳ not verified yet

Thread: [requirements/REQ-15.yaml](requirements/REQ-15.yaml)

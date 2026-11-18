# Current quality requirements

> **Generated, do not edit.** Rebuilt from the threads in `requirements/` by `python scripts/quality/regenerate.py`. To change it, record an entry in a thread and regenerate (see [README.md](README.md)).

What the team must reach now: every open requirement (not signed off ✅, not rejected), plus every recurring one with its latest result. Every requirement that ever existed is listed in [OVERVIEW.md](OVERVIEW.md).

| Grid | What it asks | Where it is shown |
|---|---|---|
| **Q1** | You questioned and specified the quality requirements of your product | Each requirement below: statement, characteristic, metric & threshold, why. Its thread shows what the team proposed and what the client accepted, amended or rejected. |
| **Q2** | You defined how you'll know each requirement is met | *Verification*, *When* and *Owner* of each requirement below |
| **Q3** | You actually ran those checks | *Latest result* and its evidence below; every `verified` entry, with its evidence and raw output, in the threads |

## REQ-2 · LLM tagging POC on real chapters

A POC tags real chapters into that schema with an LLM.

- **Characteristic:** Functional suitability
- **Metric & threshold:** ≥ 10 chapters tagged into files that validate against the schema.
- **Why (client need):** Konrad needs to see real chapters tagged before deciding whether the taxonomy is worth producing.
- **Verification:** Run `API/taxonomy_client.py` on the POC chapters and count the valid tagged files.
- **When:** Before demo
- **Owner:** Team
- **Delivery:** 2026-10-23
- **Recurring:** no
- **Client status:** signed off ⚠️
- **Latest result:** ⚠️ (2026-10-23)

Evidence:

**2 chapters** tagged out of 10: the free LLM tiers didn't allow more in the time we had. Pipeline on branch `API_LLM_taxonomie` (fallback chain across 5 providers, quota tracking, repair of malformed answers, 15 test files).

Thread: [requirements/REQ-2.yaml](requirements/REQ-2.yaml)

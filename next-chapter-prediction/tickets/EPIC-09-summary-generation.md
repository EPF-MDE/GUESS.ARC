# EPIC-09 — Summary Generation

## Status: Later / out of v1 scope — no v1 tickets

This epic file exists only to satisfy the requested roadmap structure and to
record why it stays empty. Per the instruction *"do not create tickets for
speculative features that are explicitly out of scope for v1,"* **no
implementation ticket is created here.**

## Why this epic has no tickets (SPEC anchors)

- §20 classifies summary generation as "**out of v1 core scope**; deferred
  to **Later** (§25). Not part of v1's acceptance criteria (§22)."
- §25: "Summary generation (§20) until event prediction is validated" is
  listed explicitly under "Out of scope."
- `CLAUDE.md`: "Do not begin by directly generating the next chapter
  summary" and the pipeline diagram marks summary generation "optional,"
  after event prediction, not before or alongside it.
- The secondary research question this would eventually serve — "Does
  better event prediction improve generated summaries?" (§2) — has no
  experiment spec written yet in §17–§19; writing implementation tickets
  ahead of an experiment design would itself violate the "no giant
  tickets / no speculative features" rule, since there would be no
  acceptance criteria to write them against.

## What happens when this epic opens

§20 is explicit about the eventual shape of the work: a generated summary of
chapter t+1, constructed from the model's own **predicted** t+1 event labels
(never the real chapter t+1 text), gated on event-prediction quality. When
EPIC-06 (and, if applicable, EPIC-07) has validated event prediction, the
first steps for this epic are:

1. Add the missing experiment specification for the §2 secondary question
   ("Does better event prediction improve generated summaries?") to
   `SPEC.md` — independent variable, dependent variable, baseline, protocol,
   metrics — the same way §17/§18 specify H2 and the ablations. This project
   treats `SPEC.md` as the single source of truth (document header); an
   experiment without a spec entry should not get a ticket.
2. Only then open implementation tickets, scoped the same way every other
   epic in this roadmap is: one ticket per pipeline stage (predicted-labels
   → conditioning input, generation, evaluation of generated text), each with
   its own Non-goals forbidding access to the real chapter t+1 text.

Do not build a summary-generation module, prompt template, or generation
config now "for later convenience" — doing so would implement a future
ticket inside an earlier one, which the project's workflow explicitly
forbids.

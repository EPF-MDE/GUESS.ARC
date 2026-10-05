# EPIC-07 — Sequential Models (Tier E)

## Status: Later / gated — no v1 tickets

This epic file exists only to satisfy the requested roadmap structure and to
record the gate condition. Per the instruction *"do not create tickets for
speculative features that are explicitly out of scope for v1,"* **no
implementation ticket is created here.**

## Why this epic has no tickets yet (SPEC anchors)

- §14: "Later: GRU/LSTM/Temporal Transformer (Tier E), gated on Tiers B–D
  clearing Tier A under §22's criteria first." The gate has an explicit
  precondition (EPIC-03 through EPIC-06 must clear §22) that has not been
  evaluated at roadmap-writing time.
- §22 acceptance criteria are about the project's overall scientific
  completeness (H1–H4 each tested with a reported effect size), not a
  numeric bar to beat — so "clearing the gate" means EPIC-06's H1/H2/H3 runs
  exist and are reported, not that they show a positive effect. A null or
  negative H1/H3 result (explicitly acceptable per §22) still clears the
  gate; what the gate withholds is literally starting Tier E work before
  there is anything for it to be compared against.
- §24: "Sample size... sequential models (Tier E) are especially exposed to
  overfitting, which is why they are gated behind simpler tiers."
- §25: Tier E is listed under "Later," explicitly deferred past core v1
  scope.

## What happens when the gate clears

Once EPIC-06 (T041–T049) is complete and reported, open exactly one ticket
set for this epic, scoped the same way EPIC-06 was: a shared sequential
architecture ticket (GRU/LSTM/Transformer, per §14 — model choice among
these is itself an open implementation detail to settle at that time, not
now) and a single H4 experiment ticket (Tier E vs. Tier D, per §16's mapping
table: independent variable = model family, dependent variable = event-label
F1/P@K/R@K, baseline = Tier D, protocol = rolling-origin only — §16
specifically does not permit a holdout-only H4 claim). The §18 ablation row
"static state vs. sequential" is the natural first ablation ticket for that
future epic, reusing EPIC-06's Tier D run (T044) as its baseline arm.

Do not pre-build Tier E's data loaders, training loops, or config
scaffolding now "to save time later" — per §15's incremental-complexity
ordering ("Tier A → B → C → D → (gate) → E") and per the project's own rule
against implementing future tickets as part of an earlier one.

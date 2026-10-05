# T017 - Exploratory `taxonomy.json` review & comparison report

## Objective

Produce a category-by-category comparison report between this project's own
Layer 3 taxonomy (T012) and the exploratory
`onepiece-faisabilite/output/taxonomy.json` (NER + embedding + HDBSCAN
pipeline output), to inform — but not by itself decide — whether any part
of the exploratory taxonomy should be reused, adapted, or discarded.

## Context

SPEC §4: "`onepiece-faisabilite/output/` contains an exploratory tag
taxonomy... This is raw exploratory material only. It is explicitly not
adopted as this project's event/entity vocabulary until its categories are
inspected and evaluated." SPEC §10, Layer 3: "the existing exploratory
`onepiece-faisabilite/output/taxonomy.json` is not adopted as this layer's
taxonomy. Its categories must be inspected and evaluated first." SPEC §26
lists "`taxonomy.json` role" as a decision needed "before: deciding reuse
vs. discard." This ticket produces the inspection; the reuse/discard
decision itself is a project call made from the report's findings, not a
coding deliverable.

## Scope

- Load `onepiece-faisabilite/output/taxonomy.json` (categories: `perso,
  lieu, objet, event, rel, groupe, pouvoir, fruit, navire, arme,
  poneglyphe`) read-only.
- For the `event` category specifically (the only one relevant to Layer 3's
  event taxonomy — the others are entity/object/relation-shaped and out of
  this ticket's scope), list its sub-clusters/tags and compare them against
  T012's frozen taxonomy categories: overlap, near-misses (semantically
  similar but differently named), categories present in one but absent in
  the other.
- Write the comparison as a committed report (not just console output),
  e.g. `experiments/reports/taxonomy_json_comparison.md`, with an explicit
  recommendation (reuse / adapt / discard / partial-reuse) and the
  reasoning, for human sign-off.

## Non-goals

- Do not import or wire `taxonomy.json` into any pipeline code — this
  ticket is read-only analysis. Any future reuse is a separate ticket,
  opened only after this report's recommendation is accepted.
- Do not review the non-event categories (`perso`, `lieu`, `objet`, etc.)
  for taxonomy purposes — those are out of this ticket's scope; entity/
  object signals in this project come from the wiki front-matter (§9) and
  from EPIC-05's own extraction (T033, T039), not from this exploratory
  artifact.

## Inputs

- `onepiece-faisabilite/output/taxonomy.json` (read-only, external to this
  project's codebase per §4).
- T012 (this project's own frozen taxonomy, for comparison).

## Outputs

- `experiments/reports/taxonomy_json_comparison.md`

## Acceptance criteria

- The report enumerates every `event`-category entry in `taxonomy.json` and
  states, for each, whether a corresponding category exists in T012's
  taxonomy.
- The report's recommendation section is explicit (one of reuse / adapt /
  discard / partial-reuse) with reasoning tied to concrete overlap/gap
  findings, not a generic statement.

## Tests

- A smoke test that the report-generation script runs without error and
  that `taxonomy.json` parses as valid JSON with the documented top-level
  categories present.
- No leakage-relevant test needed — this ticket reads no chapter text and
  writes no feature/label used by any model.

## Dependencies

T012.

## Risks

- **Temporal causality:** none — this is a one-off comparative analysis
  between two already-built artifacts, producing a document, not a feature.
- **Taxonomy instability (§23):** the report should note that `taxonomy.json`
  was built by a different pipeline (NER + HDBSCAN over free text, no
  temporal-causality discipline applied) and is therefore not directly
  comparable as a "ground truth" — any reuse must still pass through T012's
  construction-set-respecting pipeline, never imported as a frozen
  pre-built vocabulary wholesale.

## Definition of done

- [ ] Report committed with the full category-by-category comparison.
- [ ] Explicit recommendation recorded for project sign-off.
- [ ] No pipeline code changed as a result of this ticket alone.

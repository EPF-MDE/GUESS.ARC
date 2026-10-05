# T010 - Layer 2 event candidate extraction

## Objective

Implement a versioned, chapter-by-chapter event candidate extraction
procedure that turns each chapter's own Layer 1 raw notes (and/or long
summary) into structured candidates matching SPEC §10's minimal schema.

## Context

SPEC §10, Layer 2: "Contains: short structured/semi-structured event
mentions extracted from chapter t's own notes/summary. Constructed from: an
extraction procedure (method **[OPEN]**: rule-based / NER / LLM-assisted)
applied chapter-by-chapter... Allowed inputs: chapter t's own text, plus a
fixed shared extraction procedure whose parameters must never be fit on
statistics computed over chapters beyond t." The method choice is [OPEN]
(§26); this ticket resolves it for v1 by implementing a **rule-based**
extractor (cheapest, no external corpus-wide fitting, matches §15's
incremental-complexity principle), while keeping the procedure swappable.

## Scope

- `ncp.annotations.layer2.EventCandidate`: dataclass matching SPEC §10's
  schema (`chapter`, `event_type` [free-text at this layer, normalized only
  at Layer 3], `participants: list[str]`, `location: str | None`,
  `object: str | None`, `evidence: str`).
- `ncp.annotations.layer2.extract_candidates(chapter: ChapterRecord, *, extraction_version: str) -> list[EventCandidate]`:
  a rule-based extractor over `long_summary` + Layer 1 bullets — sentence
  segmentation, trigger-word/verb matching (reuse `AnnotationConfig.event_lexicon`
  / `event_lexicon_path` already present in the config schema), participant
  extraction via the chapter's own front-matter character list (restricting
  participant candidates to characters actually listed for that chapter,
  per §9).
- `extraction_version` is a required, explicit argument (string tag),
  stored on every candidate, per §15/§21's versioning requirement — no
  default that silently means "latest."
- Apply per chapter independently; no function in this ticket may read any
  chapter other than the one being processed.

## Non-goals

- Do not implement NER- or LLM-assisted extraction in this ticket — the
  interface (`extract_candidates`) must allow a future alternate
  implementation to be swapped in, but only the rule-based one ships now.
- Do not normalize `event_type` into a closed taxonomy — that is Layer 3
  (T012). Layer 2's `event_type` is free text (e.g. raw trigger lemma).
- Do not assign participant roles (agent vs. target) — SPEC §10 explicitly
  lists this as open/unresolved ("Open and unresolved: participant roles
  (agent vs. target)... §26").

## Inputs

- T009 (Layer 1 raw notes), T003 (validated corpus, for chapter-level
  front-matter character lists used as participant candidates).
- `src/ncp/config/schema.py` (`AnnotationConfig`).

## Outputs

- `src/ncp/annotations/layer2.py`

## Acceptance criteria

- Running extraction over the full corpus with a fixed `extraction_version`
  produces at least one candidate for every chapter with non-empty Layer 1
  notes (zero candidates for a chapter is a reportable fact, not silently
  swallowed).
- No candidate for chapter `t` references text from any other chapter —
  verified by construction (function signature takes one `ChapterRecord`)
  and by a direct test.
- Re-running with the same `extraction_version` and the same chapter input
  is deterministic (identical output).

## Tests

- Unit tests against 5-10 hand-picked chapters with manually verified
  expected candidates (at least approximate — exact extraction quality is
  T011's job, this ticket's tests check the *mechanism*, not full recall).
- Determinism test (same input twice → identical output).
- A test asserting the function signature/type system makes it impossible
  to pass more than one chapter's text into a single extraction call.

## Dependencies

T009, T003.

## Risks

- **Temporal causality:** by construction, this function takes exactly one
  chapter and cannot read ahead — the main residual risk is a lexicon or
  config file that was itself tuned by inspecting future chapters during
  development. Mitigate by noting in the PR/commit which chapters were
  used to hand-tune `event_lexicon` (should be a small train-only sample,
  never test-split chapters).
- **Imperfect event labels (§23):** rule-based extraction has a precision/
  recall ceiling independent of any downstream model — this is expected and
  acceptable per §23/§24, not a blocking defect, but must be measured (T011)
  before Layer 4 labels are trusted.

## Definition of done

- [ ] `extract_candidates` implemented, versioned, deterministic.
- [ ] Full-corpus run completes without error and produces a per-chapter
      candidate-count summary for manual review.
- [ ] All listed tests pass.

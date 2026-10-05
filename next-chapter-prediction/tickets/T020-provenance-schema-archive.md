# T020 - Run/result provenance schema & archive

## Objective

Define and implement the provenance record every reported result must
carry — split/protocol identifier, taxonomy version, extraction version,
`State(t)` component scope, config snapshot — and the archive mechanism
that persists it alongside every run's metrics.

## Context

SPEC §21: "Every reported number tagged with: split/protocol identifier,
taxonomy version, extraction version, `State(t)` component scope... No
fabricated or placeholder results; an untested hypothesis/tier is reported
as 'not yet run,' never estimated." SPEC §15: "Every run records:
representation tier, `State(t)` component scope used, event-taxonomy
version, extraction version, and split/protocol identifier — so any result
is traceable to the leakage-relevant choices that produced it." This ticket
is where that requirement becomes a concrete, enforced schema rather than
an aspiration.

## Scope

- `ncp.evaluation.provenance.RunProvenance`: dataclass with
  `run_id`, `tier` (`"A"`..`"E"` or baseline name), `split_protocol`
  (`"holdout"|"rolling_origin"`, `construction_set_id`), `taxonomy_version`,
  `extraction_version`, `state_component_scope` (which of §8's nine
  components were included, if applicable), `config_snapshot` (full
  `Config.to_dict()`), `seed`.
- `archive_run(result: ProtocolResult, provenance: RunProvenance, experiments_dir: Path) -> Path`:
  writes a self-contained run record (metrics + provenance) under
  `experiments/<run_id>/result.json`, never overwriting an existing
  `run_id`.
- A `load_run(path) -> tuple[ProtocolResult, RunProvenance]` reader, so
  later tickets (T045, T046, T050) consume archived runs rather than
  re-running models to produce a report.
- A guard: `archive_run` raises if any required provenance field is
  missing/empty — a run cannot be archived "provenance-incomplete."

## Non-goals

- Do not implement the experiment-report generation itself (H1/H3 reports,
  rolling-origin aggregation) — that is T045/T046/T050, which *consume*
  archived runs produced here.
- Do not implement a database or web UI — a flat, versioned directory of
  JSON records is sufficient for v1's scale (dozens, not millions, of runs).

## Inputs

- T019 (`ProtocolResult`).

## Outputs

- `src/ncp/evaluation/provenance.py`

## Acceptance criteria

- Every field SPEC §21 names is present and non-empty on every archived
  run, enforced by `archive_run`'s guard.
- Two runs with different `run_id`s never collide on disk; attempting to
  archive a duplicate `run_id` raises rather than silently overwriting.
- `load_run` round-trips an archived run to an equivalent in-memory object.

## Tests

- Unit test for the round-trip (archive → load → equal).
- Test that archiving with a missing required field raises.
- Test that archiving a duplicate `run_id` raises rather than overwriting.

## Dependencies

T019.

## Risks

- **Temporal causality:** indirect — this ticket does not itself construct
  features, but it is the enforcement point for §21's "no fabricated or
  placeholder results." A missing or wrong `construction_set_id` in a
  provenance record would hide a leakage bug from later audit (T054); the
  non-empty-field guard is the main defense.

## Definition of done

- [ ] `RunProvenance`, `archive_run`, `load_run` implemented.
- [ ] All listed tests pass.
- [ ] One real run (from T021, once available) successfully archived and
      reloaded as a smoke test.

# T054 - Reproducibility/provenance audit

## Objective

Audit every reported number produced across EPIC-03/06/08 and confirm each
one carries complete §21 provenance, with no fabricated or placeholder
result anywhere in the project's reports.

## Context

SPEC §21: "No fabricated or placeholder results; an untested hypothesis/
tier is reported as 'not yet run,' never estimated." SPEC §22: "Every
result carries its full provenance tag." This is the project's final
quality gate before any result set is considered complete — it checks the
*process* (did every report follow the rules this roadmap set up), not any
new scientific finding.

## Scope

- `ncp.evaluation.audit.audit_reports(experiments_dir: Path, reports_dir: Path) -> AuditReport`:
  for every archived run under `experiments/`, verify complete T020
  provenance (no empty required field); for every generated report under
  `experiments/reports/`, verify it cites only archived run IDs that
  actually exist (no report referencing a number that cannot be traced
  back to a real, archived run).
- A final audit document (`experiments/reports/reproducibility_audit.md`)
  listing: total runs archived, any provenance gaps found (and whether
  fixed), confirmation that H1–H4's status is stated accurately (H1/H3
  tested per T050; H2 tested per T047; H4 explicitly "not yet run" per
  EPIC-07's gate, never estimated).

## Non-goals

- Do not re-run any experiment to "fix" a finding — this ticket only
  audits existing artifacts; any gap found that requires a re-run is
  logged as a follow-up ticket, not silently patched by regenerating a
  number without re-deriving it properly.
- Do not audit code quality/style — this ticket is about result
  provenance specifically, not a general code review.

## Inputs

- T020 (archive format), T050 (final H1/H3 report), and every other
  report-producing ticket's output (T024, T045–T049, T051–T053).

## Outputs

- `src/ncp/evaluation/audit.py`,
  `experiments/reports/reproducibility_audit.md`.

## Acceptance criteria

- Every archived run passes the provenance-completeness check (reusing
  T020's own guard as a regression check across the whole archive, not
  just at write-time).
- Every report's cited numbers trace back to a real archived run — no
  orphan/invented figures.
- H4's status is explicitly recorded as "not yet run" (per EPIC-07's gate),
  never given an estimated or implied value anywhere in any report.

## Tests

- Unit test on a synthetic `experiments/` directory with one deliberately
  incomplete run, confirming the audit flags it.
- Unit test on a synthetic report referencing a non-existent run ID,
  confirming the audit flags it.

## Dependencies

T020, T050.

## Risks

- **Temporal causality:** none new — this is a meta-level audit of
  process compliance, not a new feature/leakage surface. Its value is in
  catching *process* violations of §21/§22 (e.g. a report drafted before
  its underlying run finished, left in place after the run's numbers
  changed) before they are mistaken for final results.

## Definition of done

- [ ] `audit_reports` implemented and tested.
- [ ] Audit run against the real `experiments/` directory and
      `reproducibility_audit.md` committed.
- [ ] Any provenance gap found is either fixed (and re-audited) or
      explicitly logged as a follow-up ticket — never silently ignored.

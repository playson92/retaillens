# RetailLens working instructions

This repository is the starting point for B1 RetailLens. The user has requested
implementation of the complete local MVP, using the portfolio-project-template
process. Execute CODEX_TASK_RETAILLENS.txt and docs/PROJECT_PLAN.md.

## Scope and continuity

- Active project: B1 RetailLens. Portfolio category order: B, C, D, A.
- Implement stages 00 to 05 autonomously. A stage boundary is an internal
  checkpoint, not a request for permission to continue.
- docs/PROJECT_PLAN.md defines scope; docs/DATA_CONTRACT.md defines proposed
  analytical rules; docs/PROJECT_STATE.json records actual progress and evidence.
- Read current code, Git state and latest run handoff before resuming. Continue
  from actual progress instead of creating another master plan.
- Complete all independent work before reporting an external blocker.
- Local dependencies, local containers and small local commits are within scope.
  Work on feat/retaillens-mvp; preserve unrelated changes. No automatic merge,
  remote publication, paid service or use of company systems is in this task.
- Follow CONTRIBUTING.md. Keep Python 3.12, src/tests structure, Ruff and pytest.
- Additional agents may review independent data, model or diff work. Assign clear
  ownership; one integrator verifies the result.

## Evidence

- Implement real behavior; a static health response is only a starter smoke check.
- Record executed checks and their exit codes. A workflow file is not a successful
  GitHub Actions run; a valid PBIP definition is not a verified Desktop report.
- Use PASS, FAIL, NOT_RUN, PARTIAL and BLOCKED precisely. Fix implementation
  failures instead of relabelling them as environment limitations.
- Keep real Olist input and synthetic fixtures clearly separated.
- Each run writes a new output/codex_runs/<UTC_TIMESTAMP>/ directory with a
  compact REVIEW_BUNDLE.zip, manifest, review, patch, verification log and handoff.
- README and portfolio case study: English. Report to the user: Polish.

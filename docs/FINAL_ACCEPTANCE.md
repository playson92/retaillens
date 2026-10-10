# Final local MVP acceptance

## Decision and exact implementation

Review date: **10 October 2026**. **B1 RetailLens local MVP: ACCEPTED / PASS.**
**RL-08: CLOSED_ACCEPTED.** Local Docker execution is accepted. The review found no
material defects requiring another implementation fix.

| Evidence identity | Accepted value |
| --- | --- |
| Implementation commit | `cd8ad721933e0fa9c5e1636aa61a3a57e75cc237` |
| Git tree | `adc1d583ba564493082b5bcc974ac6b468658379` |
| Local evidence run | `20261009T2049086587846Z` |
| Accepted archive | `output/codex_runs/20261009T2049086587846Z/REVIEW_BUNDLE.zip` |
| Archive SHA256 | `b13695ca4db4d97e91ac3a4149daf2df4217f982cc95dfe4c4b85cc92089a598` |

This decision applies to that implementation commit and tree. It does not
automatically approve later code changes. The subsequent closure commit records
the decision through documentation only and needs no repeat acceptance of the
same implementation.

## Accepted evidence and provenance

The following are **previously executed checks and the supplied review results**,
not tests performed while recording this acceptance.

| Scope | Accepted evidence | Run or review |
| --- | --- | --- |
| Windows / Codex | 77 tests PASS; Ruff PASS; Windows PowerShell parser for 14 scripts PASS | `20261009T2049086587846Z` |
| Actual local Linux Docker | All 14 gates PASS: build, full pinned Olist v2, fixture, comparison of 9 result sets using 7 queries per mode, expected tolerance failure, cleanup after success and error | `20261009T2049086587846Z` |
| Power BI Desktop endpoint refresh | Two fresh real/synthetic projects refreshed against `127.0.0.1:5435`; 8 tables and 5 KPIs per project; 6 final control queries | `20261009T2049086587846Z` |
| Independent review integrity | 202 source files and 301 evidence files verified; accepted Git tree reproduced from the patch | Review of the accepted run, 2026-10-10 |
| Independent review checks | 73 tests PASS; 4 Windows-only tests SKIP; Docker/Portable result comparison and 44 Power BI/SQL fields PASS | Review of the accepted run, 2026-10-10 |
| Earlier local MVP and RL-01–RL-07 | Historical acceptance remains valid; 32 DAX queries and 962 comparisons, with no mismatches, remain accepted | `20261007T204100Z`; review 2026-10-08 |

The historical MVP identity remains `accepted_mvp_run=20261007T204100Z` and
`accepted_mvp_head=922502a8ae65fd87597a98abffe0707fa031b84e`.
The later RL-08 acceptance is recorded separately in
[PROJECT_STATE.json](PROJECT_STATE.json). Earlier runs and bundles are preserved.

## Status and limits

- Local MVP: **READY_ACCEPTED**. Container acceptance: **PASS**.
- RL-08: **CLOSED_ACCEPTED**, with no outstanding material local defects.
- **REMOTE_CI: NOT_RUN**. A successful local Docker run is not a remote GitHub
  Actions execution. No merge, push or publication is authorized by this closure.
- The overall project state remains **PARTIAL solely because remote CI is
  unexecuted**; the local scope is accepted and has no pending implementation review.
- Historical PASS results retain their recorded evidence runs. Application tests,
  imports, Docker scenarios and Desktop refreshes are not rerun for this
  documentation-only change.

Analytical definitions remain in [DATA_CONTRACT.md](DATA_CONTRACT.md); this
decision changes no KPI, SQL, model, DAX or data. Repeat-purchase follow-up keeps
`observation_end=2018-09-01`, an assumed start-of-day boundary before the sparse
September/October tail. **Source completeness is not certified.** Source-slice
results do not establish profit, accounting revenue, churn or causal effects.
The accepted real Olist and synthetic fixture evidence remains separate.

## Preserved coexistence configuration

| Service | Recorded endpoint or storage |
| --- | --- |
| RetailLens Portable | `127.0.0.1:5435`; existing `output/postgres_data` |
| WTA PostgreSQL | `127.0.0.1:5433` |
| WTA dashboard | `http://127.0.0.1:8501` |
| Isolated Docker acceptance scenario | Host port `6433`; its containers stopped after the accepted run; named volumes retained |

These describe the accepted run and preserved configuration, not a fresh service
health check. Recording the closure does not start, stop or refresh any service,
regenerate credentials or alter storage.

## Documentation closure record

The closure run is `output/codex_runs/20261010T084859794283Z/`. Its compact
`REVIEW_BUNDLE.zip` contains the documentation patch, current source snapshot,
manifest, handoff and checks actually performed for this step. It references the
accepted run and archive hash above instead of repackaging their large evidence.

The current checks cover Git identity and clean baseline, the accepted archive
SHA256, JSON validity and preserved acceptance fields, documentation-only diff,
`git diff --check`, patch reconstruction and ZIP inventory/integrity.
Their outcomes and exact exit codes are recorded in the closure run; the commit
that records the documentation is identified in its manifest and handoff.

No further review of the same accepted implementation is requested. Remote CI
remains unexecuted; any later remote action needs separate authorization.
Portfolio category order remains **B → C → D → A**.

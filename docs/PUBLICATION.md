# Repository publication and remote CI

The public repository is **[playson92/retaillens](https://github.com/playson92/retaillens)**.
Default and published branch: **`feat/retaillens-mvp`**.
Publication was explicitly authorized on 10 October 2026, after confirming the
account, absent target repository, exact source SHA and full reachable history.
The repository was created once, then published with ordinary pushes. History is
preserved; no merge, force-push, tag or release was performed.

## First successful remote verification

| Identity | Value |
| --- | --- |
| Checked commit | `f6e165e7d93b0bdd2593fd352ae9ccbce8bb8b10` |
| Workflow / event | `.github/workflows/ci.yml` / `push` |
| Run | [CI #38081359468](https://github.com/playson92/retaillens/actions/runs/38081359468) |
| Conclusion | Completed success; REMOTE_CI PASS |
| Checked at UTC | `2026-10-10T19:51:06.533694+00:00` |
| Local publication evidence run | `20261010T121427904382Z` |

| Required job | Executed job / evidence | Result |
| --- | --- | --- |
| quality | [Python quality checks](https://github.com/playson92/retaillens/actions/runs/38081359468/job/114298769498) | PASS / completed success |
| tmdl | [Official TMDL parser](https://github.com/playson92/retaillens/actions/runs/38081359468/job/114298769787) | PASS / completed success |
| postgres | [PostgreSQL business contract](https://github.com/playson92/retaillens/actions/runs/38081359468/job/114298769651) | PASS / completed success |
| docker | [Docker build and Compose fixture demo](https://github.com/playson92/retaillens/actions/runs/38081359468/job/114298769705) | PASS / completed success |

Quality executed Ruff, formatting, **157 tests PASS / 12 platform skips / 26 integration
deselections**, and official schema/reference validation on Linux / Python 3.12.
PostgreSQL executed **26 integration tests PASS** against PostgreSQL 17.6 and its
fixture demo. The Windows job used the pinned official TOM parser. Docker built
the image, ran Compose fixture/demo checks and the expected tolerance failure,
then cleaned up its own services. A skipped individual platform test is distinct
from a skipped required job; all four jobs above completed successfully.

## Failure, diagnosis and bounded fix

The initially approved portfolio commit
`605f4ffe9183a03e82e89ec3f993dfe2322d2a49` was published first.
[Its run #38080645129](https://github.com/playson92/retaillens/actions/runs/38080645129)
failed quality while the other three required jobs passed. A broad CRLF rule for
`powerbi/**/*.json` changed the checkout bytes of 12 vendored schemas, invalidating
their pinned SHA-256 values and causing eight report-validation test failures.

The only implementation-related publication fix is a more specific
`powerbi/schemas/*.json text eol=lf` rule in [.gitattributes](../.gitattributes).
Schema bytes in Git, manifest hashes, checksum validation, SQL, DAX and KPI
definitions were preserved. An isolated checkout reproduced all 12 mismatches
before the fix, then matched all 12 hashes and passed the existing validator.
The existing Windows validator regression module passed **29/29 tests**.

A broader local pytest attempt was **BLOCKED during collection** by Windows
application-control rejection of the psycopg/libpq DLL. That failed attempt is
retained in local evidence; it is not reported as a local suite PASS. The actual
Linux quality and PostgreSQL runs above provide the completed remote results.
No Windows security policy was changed.

## Scope and retained acceptance

[Final local acceptance](FINAL_ACCEPTANCE.md) retains the exact accepted
implementation commit, earlier runs and Desktop/real-data results.
The four [real screenshots](images/README.md) and [small SQL proof set](evidence/real/README.md)
are unchanged accepted evidence. CI uses synthetic control data; it does not
claim another full Olist import, Desktop refresh or new business findings.
The assumed `observation_end=2018-09-01` and uncertified source completeness remain.

[PROJECT_STATE.json](PROJECT_STATE.json) records the checked first-successful SHA.
This record is written by a later documentation commit; it does not claim to
describe its own commit hash. CI for that final published documentation commit,
its SHA, run URL and four job outcomes are saved in the ignored local publication
run and completion report. The [workflow page](https://github.com/playson92/retaillens/actions/workflows/ci.yml)
also exposes subsequent completed runs.

Local Portable remains configured at `127.0.0.1:5435` with retained
`output/postgres_data`. WTA PostgreSQL 5433/dashboard 8501 remain separate.
No local service was started, stopped or refreshed for publication.
Private configuration, raw input, PostgreSQL storage and Power BI cache are
excluded from the published source and its history. MIT code, Olist
CC BY-NC-SA 4.0 derivatives and Microsoft schema notices retain separate
[data-source attribution](DATA_SOURCES.md).

B1 RetailLens is published and its required remote gate passed. No repeat
acceptance of the same local implementation is requested.

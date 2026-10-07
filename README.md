# RetailLens — B1

Marketplace analytics from official Olist CSVs to PostgreSQL and a four-page Power BI project.
Built on Jonatan Tomaszewicz's Python 3.12 template. Portfolio order: **B → C → D → A**.
Python handles ingestion/provenance; SQL owns analytical rules; Power BI consumes published marts
in Import mode. RetailLens compares delivered merchandise value, deliveries, reviews, payment
reconciliation and observed repeat purchases with explicit populations and exclusions.

## Actual verification

Full official **Olist version 2** has run on PostgreSQL 17.6. Reimport/rebuild preserve counts
and metrics. Python quality, unit tests, PostgreSQL business tests, official Microsoft JSON
schemas and official TOM TMDL parsing have passed. Details: [PROJECT_STATE.json](docs/PROJECT_STATE.json).

**Overall: PARTIAL.** Desktop and Docker are absent. Desktop open/refresh, DAX execution, visual
QA, Docker build/Compose and remote Actions remain **NOT_RUN**. Authored/parsed definitions do
not prove a working Desktop dashboard. No rendered screenshots or deployment are claimed.

## Run on Windows

Python 3.12 is required. From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1 -Backend Auto
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo.ps1 -Mode synthetic
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo.ps1 -Mode real -ObservationEnd 2018-09-01
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\open_powerbi.ps1 -Mode real
```

Setup creates a private `.env`, installs `requirements.lock`, then starts Docker Compose or
an isolated portable PostgreSQL at `127.0.0.1:5433`. It preserves credentials, other services
and volumes. Pass `-Python C:\path\to\python.exe` if needed. Windows portable binaries come
from EDB with pinned SHA256; the database stays in ignored `output/postgres_data`. Stop with
`.\.venv\Scripts\python.exe scripts\local_postgres.py stop`.
The per-process execution-policy argument supports Windows' default script restriction
without changing the user's global policy.

The real demo reuses or downloads `olistbr/brazilian-ecommerce/versions/2` to `data/raw/olist-v2`.
No Kaggle account was needed here. If access later requires consent/authentication, follow
[the official source instructions](docs/DATA_SOURCES.md). Existing nonempty inputs are not overwritten.

Opening Power BI prepares an ignored local copy in `output/powerbi/<mode>`. With an installed
Desktop, enable PBIP/PBIR features if requested, select Database authentication for PostgreSQL,
enter credentials from local `.env`, and refresh. No password is stored in TMDL. See
[POWER_BI.md](docs/POWER_BI.md) for the runtime checklist. `demo.ps1 -OpenReport` opens after import.

## Docker / Linux

Generate private credentials in `.env` from `.env.example`, then:

```bash
mkdir -p output data/raw
# Allow container user 1000 to write output and data/raw using your local ownership policy.
docker compose up -d --wait db
docker compose run --rm app
docker compose run --rm app demo --mode real --observation-end 2018-09-01 --output /app/output/real
docker compose stop
```

`docker/Dockerfile` uses Python 3.12 and Compose uses PostgreSQL 17.6. Host clients connect to
`127.0.0.1:5433`; app containers use `db:5432`. Change occupied `DATABASE_PORT` and prepare the
local report again. No command deletes volumes. Docker execution is pending; portable PostgreSQL
was executed here.
When switching from Portable to Docker, stop the portable cluster first using the command
above; each backend has its own database storage, so run the demo to populate the chosen backend.

## CLI

Run `.\.venv\Scripts\python.exe -m retaillens <command>` (or installed `python -m retaillens`).
Warehouse commands accept `--mode real|synthetic`; modes have separate database schemas.

| Command | Behavior |
| --- | --- |
| `fixture` | Generate artificial CSVs in `data/sample` |
| `download --mode real` | Download pinned official Olist v2 |
| `profile --mode real --output output/profile` | Hashes, counts, nulls, validity, keys and months |
| `import --mode real --observation-end 2018-09-01` | Atomic raw/staging/mart publication and audit |
| `build --mode real` | Rebuild SQL marts, optionally with changed tolerance |
| `quality --mode real` | Model invariants, nonzero exit on failure |
| `analyse --mode real --output output/analysis` | Execute all analytical queries, export CSV/JSON |
| `export --mode real --output output/report_data/real` | Export marts for inspection |
| `demo --mode real --observation-end 2018-09-01` | Source, import, model, quality, analyses, exports |

Options: `--input`, `--version`, `--start`, `--end` (exclusive), `--observation-end`, `--tolerance`.
Money uses Decimal/NUMERIC; default tolerance is 0.01 BRL. Evidence records the model's actual
tolerance. Change the historical observation boundary by reimporting with the intended value.
Power BI connects to PostgreSQL rather than the CSV exports.

## Executed real results

Whole source: purchases **2016-09-04 through 2018-10-17**, all segments/statuses, 0.01 BRL
tolerance. Repeat follow-up assumes the **start of 2018-09-01**; sparse later rows do not prove
complete observation. First/last source months are flagged; no unsupported growth estimate is made.

| Metric | SQL result |
| --- | --- |
| Source orders | 99,441 |
| Delivered GMV | 13,221,498.11 BRL / 96,478 qualifying orders |
| Delivered AOV | 137.0415857501 BRL |
| On time | 88,587 / 95,097 = 93.1544%; 1,381 delivered exclusions |
| Delivered reconciliation | 96,178 matched; 299 mismatches; 1 not comparable |
| Observed repeat within 90 days | 1,519 / 75,703 = 2.0065%; 17,655 incomplete windows |

These are source-slice metrics, not profit, accounting revenue, churn or causal estimates.
The separate fixture gives **340.00 BRL GMV**, **6 eligible orders**, **3/5 on time**, **1/4 repeat**.
See [CASE_STUDY.md](docs/CASE_STUDY.md) for three evidence-linked findings.

## Verify and review

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1 -Postgres
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\parse_tmdl.ps1 -Download
.\.venv\Scripts\python.exe scripts\validate_powerbi.py --postgres --mode real
```

PostgreSQL tests replace only `rl_synthetic`; run sequentially outside its demo. They check
exact financial outcomes, ambiguous reviews, unknown references, conflicting keys, repeat
boundaries, transaction rollback and schema isolation. CI retains Ruff/pytest and adds PostgreSQL,
official schemas and Docker/Compose fixture checks without real Olist downloads on each PR.

Run evidence, Polish review, patch, manifest, handoff and `REVIEW_BUNDLE.zip` are under
`output/codex_runs/<UTC_TIMESTAMP>`. Bundles omit secrets, environments, databases, full inputs,
Git and caches. Work is left for review on `feat/retaillens-mvp`, without merge or publication.

```mermaid
flowchart LR
    A[Olist v2 or synthetic CSV] --> B[Python profile and lineage]
    B --> C[PostgreSQL raw and typed staging]
    C --> D[SQL order/item/cohort marts]
    D --> E[Versioned SQL evidence]
    D --> F[Power BI Import TMDL and PBIR]
```

Read [contract](docs/DATA_CONTRACT.md), [architecture](docs/ARCHITECTURE.md),
[demo](docs/DEMO.md), [plan](docs/PROJECT_PLAN.md), [template provenance](docs/TEMPLATE_ADAPTATION.md)
and [contribution rules](CONTRIBUTING.md).

Code/artificial fixtures: MIT, author **Jonatan Tomaszewicz**. Olist inputs and derived evidence
retain [CC BY-NC-SA 4.0 terms](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
Microsoft schema attribution is retained separately. Next work after runtime review: Desktop
screenshots, source completeness agreement, incremental snapshots and investigation of mismatches.

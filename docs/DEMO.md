# Three-minute demo

Prepare: `scripts/setup.ps1`, then `scripts/demo.ps1 -Mode real -ObservationEnd 2018-09-01`.
Invoke scripts with `powershell -NoProfile -ExecutionPolicy Bypass -File` as shown in README;
this works with the host's default restricted script policy without a global policy change.
With Desktop installed, run `scripts/open_powerbi.ps1 -Mode real`, authenticate from local
`.env` and refresh. Accepted run `20261007T204100Z` passed Desktop open, refresh, DAX/SQL and all four pages in both modes;
32 required queries and 962 strict comparisons passed. Evidence is in PROJECT_STATE.json;
opening, refresh, DAX and visual QA are independent controls.

**0:00–0:40 — Overview.** Identify source/version and observation assumption. Explain 13.22
million BRL delivered item GMV and 137.04 BRL full-order AOV. Filter purchase date; explain
boundary-month flags and why there is no unsupported growth claim.

**0:40–1:20 — Deliveries and reviews.** Show 88,587/95,097 on time and 1,381 delivered date
exclusions. Compare scores alongside counts/coverage. Association does not establish causation.

**1:20–2:00 — Sellers and categories.** Filter seller/category, inspect item value and Segment
item value per order. Seller delivery uses single-seller orders; categories do not receive
whole-order delivery outcomes. Repeat cohorts intentionally ignore segment selection.

**2:00–2:40 — Data quality.** Show 299 delivered mismatches and one incomparable order. Filter
reconciliation status, inspect expected/paid/delta/order ID. Global quality warnings retain
their source-wide scope under purchase-date filters.

**2:40–3:00 — Engineering proof.** Show the contract, independent SQL aggregation, one rollback
or equal-price fixture test and the review bundle. Include NOT_RUN gates in the presentation.

Without Desktop, present executed SQL evidence and authored definitions with that limitation
stated. Do not claim a rendered dashboard. Synthetic demo: GMV340.00 BRL, on-time3/5, repeat1/4.
Tests replace only synthetic mode, so run its demo again after testing for canonical fixture.

Troubleshooting: change an occupied DATABASE_PORT and regenerate local report; select Portable
without Docker; install Python3.12 rather than changing required version. Connection failures
are failed executions, not skipped tests. No command resets unrelated projects or volumes.

## Current RL-08 verification and coexistence

Run `20261009T2049086587846Z`, baseline `42f359e1b8f92e140246f1e5d7d8bd02212a2489`,
preserves the accepted cluster, schemas, source hashes and business rules.
WTA remains healthy at PostgreSQL5433 and dashboard8501. Port5434 was occupied too;
private RetailLens configuration now uses5435 with database/username/password retained.

~~~powershell
$env:DATABASE_PORT = '5435'
.\.venv\Scripts\python.exe scripts\local_postgres.py start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_docker.ps1
~~~

The process-only override prevents an inherited old port from overriding private .env.
Readiness and capture require authenticated `SHOW data_directory` matching the preserved
Windows path, with case/slash normalization. An unrelated server is refused before data
queries/creation. An already running owned cluster is reused without restart.

The actual Docker entrypoint completed on Linux: isolated project/image/6433host port,
build, PostgreSQL health, fixture and full Olist v2 with observation_end2018-09-01,
all9result sets/7queries per mode, intentional negative-tolerance exit1, and both finally
cleanup phases. Own containers stopped; named volumes remain. All14gates PASS in
`docker_verification.json`. Image:
`sha256:31d1ca0afb534ea6d0eb90ea318c54ce5adbae916c13259a85410a6021546c1d`.

## Fresh Desktop reports on5435

Both fresh projects opened and actually refreshed on this Windows machine:

| Mode | Project |
| --- | --- |
| real | `C:\projekty\retaillens\output\powerbi\real\20261009T205857907973Z-zrxzkqat\RetailLens.pbip` |
| synthetic | `C:\projekty\retaillens\output\powerbi\synthetic\20261009T205858485709Z-4ziudmlx\RetailLens.pbip` |

Current `evidence/endpoint-refresh.json` verifies TOM provider/source, eight table counts,
source hashes and five main KPIs through six final ADOMD queries:
real99441orders/112650items/13221498.11BRL GMV/137.0416AOV/93.15435818%on time/2.00652550%repeat;
synthetic8orders/10items/340BRL GMV/56.6667AOV/60%on time/25%repeat.
Currency precision, Decimal comparison allowances and NULL semantics are unchanged.

`real-refreshed-overview.png` and `synthetic-refreshed-overview.png` are real current
screenshots, full source date ranges and no additional segment selection. Historical
four-page visual QA and32DAX/962comparisons remain accepted in run20261007T204100Z.

Helpers resolve environment > SettingsPath/.env > defaults and retain exact source,
PostgreSQL, PID, schema and SELECT guards. DOM submission alone retained an empty password
in this Desktop version. Native input now waits for actual processing, commits with Tab
and clicks only an unoccluded control in the verified owned credential dialog. Existing
credentials stay private. Failed initial imports/attempts remain in evidence; final
refresh and production authentication passed.

Final:77scoped tests, Ruff lint/format40Python files and Windows PowerShell5.1 parser14scripts
PASS. REMOTE_CI NOT_RUN; no merge/push/publication.
Bundle: `output/codex_runs/20261009T2049086587846Z/REVIEW_BUNDLE.zip`.

# Architecture and model

Python 3.12, setuptools, src/tests, Ruff and pytest preserve the supplied template.
`requirements.lock` is shared by setup, Docker and CI. PowerShell orchestrates the same CLI/SQL.

## Ingestion and atomic publication

`rl_real` and `rl_synthetic` are separate, allowlisted warehouse schemas. Search paths include
only the selected schema and implicit pg_catalog, never public fallback. `rl_audit.ingestion_runs`
records attempts/results. An advisory transaction lock serializes writers by mode. Import
truncates explicitly owned source tables and rebuilds explicitly owned marts in one PostgreSQL
transaction. Failed COPY/TRUNCATE/DROP/CREATE rolls back to the previous publication; unrelated
tables and volumes remain. Reimport produces identical source counts/KPI.

`raw_records` retains original strings as JSONB with SHA256 and logical CSV record number
(not physical newline). `source_files` and `run_metadata.source_manifest` retain source counts,
hashes/version. Original files stay in data/raw. Optional geolocation is retained, hashed and
counted as a source file; it is deliberately not loaded into raw/staging/marts. State-level
questions do not need its million rows, and naive ZIP-code joins would multiply facts.

Parser: naive timestamps keep source calendar; money is finite, nonnegative, at most two
decimals and inside NUMERIC(18,2). Invalid optional fields become NULL plus an issue, with raw
values preserved. Missing keys and all rows in a conflicting key group are excluded from
typed staging and reported. Identical typed duplicates are deduplicated with provenance.
Reviews retain every source row because review_id/order_id is not a unique review key.

Orphans remain staged and get issues. Unresolved item products/sellers map to `__unknown__`
dimension members. Missing customer mapping excludes person cohorts independently of GMV.
Rejected item/payment rows prevent remaining partial totals from qualifying as complete sides.
Uncertain/unresolved seller identity excludes seller delivery/review attribution.

## Grains

| Object | Key / grain | Notes |
| --- | --- | --- |
| raw_records | table + SHA256 + CSV record | Original strings |
| stg_orders | accepted order_id | One order |
| stg_items | (order_id, order_item_id) | Sequence is not quantity |
| stg_payments | (order_id, payment_sequential) | Installments do not multiply value |
| stg_reviews | file + record number | All opinions |
| mart_orders | order_id primary key | Independent item/payment/review aggregates |
| mart_items | (order_id, order_item_id) primary key | Attributable segment item values |
| dim_date | source purchase date | Boundary month flag |
| dim_product / dim_seller | source ID | Unknown member; translated category fallback |
| mart_cohorts | customer_unique_id | First observed delivered purchase across whole source |
| quality_summary | issue type/severity | Counts overlap, not distinct bad-order totals |
| run_metadata | one current publication | Source/window/boundary/tolerance |

## Populations and Power BI filters

M1/M2 require delivered, valid purchase dates and all item prices. M3 has independent date
eligibility; approval/carrier timestamps, when present, must be chronological, and approval
must not follow handoff. Promise/actual are source days. Eligible delay is max(actual-promise,0).
M4 uses complete separately aggregated monetary sides and the recorded NUMERIC tolerance.
M5 uses whole-source first delivered observations with full assumed 90-day windows. Equal
first timestamps are counted separately, not treated as later repeats. Cohorts use grouped
joins instead of one repeated full scan per person.

Power BI: Date→Orders, Date→Cohorts, Orders→Items, Product→Items, Seller→Items, all single
direction. Items have one active date path through Orders. Product/seller filters affect
segment items, not full-order AOV. Seller delivery uses explicit TREATAS to single_seller_id
for single-seller orders. Category does not attribute a whole-order delivery result. Repeat
uses first-purchase date and ignores product/seller; quality summaries/source labels stay global.
Money is fixed decimal in TMDL and Currency.Type in Power Query. No credentials are embedded.

Four PBIR pages have native bound visuals and documented interactions. Official JSON schemas
and TOM parse metadata; they do not execute Power Query/DAX or verify visual rendering.

## Tradeoffs

Full refresh simplifies historical versioning and atomic publication. The importer buffers one
required source table at a time, retaining raw and typed copies; memory scales with that CSV.
The tested required Olist files have roughly 550,000 rows combined. Future larger sources can
use temporary streaming staging and incremental snapshots. No extra frontend/cloud/dbt is needed.

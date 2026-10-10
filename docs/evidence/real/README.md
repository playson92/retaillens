# Small real-data evidence set

These are the same saved outputs from accepted run `20261007T204100Z`. They are
aggregate results and source provenance, not a new analysis or the full warehouse.
Mode: **real**, official **Olist v2**, all segments/statuses where the query defines
them; dates **[2016-09-04, 2018-10-18)**, tolerance **0.01 BRL**,
`observation_end=2018-09-01`. Source completeness is not certified.

| Claim | Existing SQL or independent control | Saved result |
| --- | --- | --- |
| GMV, AOV and eligible delivery counts | [03_overview.sql](../../../sql/03_overview.sql) | [03_overview.csv](03_overview.csv) |
| Review means, counts and coverage | [05_deliveries_reviews.sql](../../../sql/05_deliveries_reviews.sql), [grouped control](../../../scripts/check_real_run.py) | [05_deliveries_reviews.csv](05_deliveries_reviews.csv), [sql_evidence.json](sql_evidence.json) |
| Reconciliation by status | [07_reconciliation.sql](../../../sql/07_reconciliation.sql) | [07_reconciliation.csv](07_reconciliation.csv) |
| Observed repeat and window exclusions | [08_repeat.sql](../../../sql/08_repeat.sql) | [08_repeat.csv](08_repeat.csv) |
| Actual parameters and source identity | [analytical contract](../../DATA_CONTRACT.md) | [run_metadata.csv](run_metadata.csv), [source_manifest.json](source_manifest.json) |

The deliveries query groups by state and on-time flag. The independent control
in `sql_evidence.json` records the overall groups used in the case study; do not
average state means to reproduce them. Reconciliation CSV includes all statuses;
the case-study finding selects **delivered** only. Repeat is a person-cohort
measure and is not seller/category churn.

[provenance.json](provenance.json) records original paths, original and published byte hashes,
parameters, retrieval metadata and attribution. Git text copies normalize CRLF to LF
only; rows, numeric values and metadata remain unchanged. Published hashes refer
to Git/source-snapshot bytes (LF); a Windows checkout can restore CRLF. Originals and previous bundles
remain local and unchanged. Full analysis JSON, per-order diagnostics, raw CSVs,
Parquet/database files and private settings are excluded from this public subset.

Olist and collaborators; source metadata license **CC BY-NC-SA 4.0**:
[official dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
The MIT code license is separate. See [case study](../../CASE_STUDY.md) and
[data sources](../../DATA_SOURCES.md).

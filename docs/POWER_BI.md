# Power BI artifact and runtime verification

The repository contains `powerbi/RetailLens.pbip`, the local `RetailLens.Report` PBIR folder,
and `RetailLens.SemanticModel` TMDL folder. Pages, measures, partitions, relationships and
native visuals are authored; the user does not need to design the report. Default mode is
real; the opening script prepares a local copy for either mode and the current host parameters.

## Checks that actually ran

Official JSON schemas are vendored with revision/hash manifest in `powerbi/schemas`. The
validator checks JSON schema, no BOM, relative model path, unique IDs, report field references,
visual query roles, layout bounds, interactions, date slicers and static measure dependencies.
`--postgres --mode real` also checks source columns and unique, nonnull relationship keys.
Both the Python validator and official TOM19.117.0 compare the actual five relationships with
`model_contract.json`: names, completeness, endpoints, activation, cardinalities and filter
direction. Omitted properties use TMDL defaults. Negative copies with a missing relationship
file, inactive purchase-date path, timestamp endpoint or changed filtering fail with nonzero
exit codes. These checks execute neither M nor DAX.

Use `--project <exact RetailLens.pbip>` for Python and `-ProjectPath <exact RetailLens.pbip>`
for TOM to validate a prepared copy. Neither falls back to a sibling source project.
See the current run's `evidence/powerbi_final/` for source and exact final real/synthetic results.

The model's money type is TOM/TMDL Decimal (Power BI fixed decimal), with Currency.Type in M.
It supports the source's two-decimal amounts exactly. Reconciliation status is decided in
PostgreSQL NUMERIC; display-only tolerance is text so finer configured tolerance is retained.
[Microsoft documents the fixed decimal/TOM Decimal mapping](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types).

## Completed runtime verification

Run `20261007T204100Z` used official Store Desktop **2.158.1304.0** and official ADOMD
**19.117.0** against the actual Desktop-hosted model. Both modes passed DESKTOP_OPEN,
DATA_REFRESH, DAX_RUNTIME_RECONCILIATION and VISUAL_QA. Real executed **17/17 required queries
and 553 strict comparisons**; synthetic executed **15/15 and 409 comparisons**. There were
no mismatches. Each mode executed all five supplied EVALUATE blocks, the 49-measure matrix,
imported-table/source-identity proofs and applicable edge cases. SQL expected values came
from read-only PostgreSQL queries at identical filters.

Evidence: `output/codex_runs/20261007T204100Z/evidence/powerbi_runtime/runtime.json`,
`comparison-real-v2.json`, `comparison-synthetic-v2.json`, `dax-*-v2.json`,
`sql_expected_v2.json`, `runtime_sql_proofs.json` and `*-final-*.png`.
The runtime manifest records tool hashes, source identity, prepared model/report hashes,
exact PBIP paths and screenshot hashes. Both prepared projects remained unchanged after preparation.
`evidence/powerbi_final/` contains official schema and TOM checks of these same final copies.

All four native pages rendered in both modes. Native UI selections verified books+s1
(150 BRL / three segment orders / 50 per order), order o3 diagnostics, an empty date range
and separation of full-order/cohort/global-quality scope from item selections. Tables retain
native scrolling and tooltips for long IDs and crowded axes.

Amounts/sums and counts agree exactly; ratios allow at most 1e-10 absolute difference.
Power BI fixed-decimal averages allow at most 0.00005 BRL and must round to identical cents:
real AOV137.0416 versus SQL137.0415857501191982, both137.04. Only imported_at metadata allows
1/300 second for Desktop datetime precision. NULL is never accepted as numeric zero.

The January2018+s2 case exposed a real zero-numerator defect: before eligible1/on-timeBLANK/
rateBLANK, after1/0/0. Six base counts use COALESCE0; DIVIDE still returns BLANK when its
population is empty. Duplicate native slicer headers were hidden and the quality metadata
row enlarged after actual clipping. Earlier failed refresh/launch/early-query attempts are
retained as history; final successful gates have separate artifacts and exit codes.

## First open

1. Prepare the warehouse using `scripts/demo.ps1 -Mode real -ObservationEnd 2018-09-01`.
   Invoke scripts via `powershell -NoProfile -ExecutionPolicy Bypass -File` (README).
2. Use Power BI Desktop (2.158.1304.0 is installed here) and enable PBIP/PBIR features if requested.
3. Run `scripts/open_powerbi.ps1 -Mode real` (optionally `-DesktopPath <exe>`).
4. For PostgreSQL Database authentication, enter DATABASE_USER/PASSWORD from local `.env`.
   Desktop connects to resolved DATABASE_HOST:DATABASE_PORT and DATABASE_NAME;
   current Portable RetailLens is 127.0.0.1:5435. Environment > private .env > defaults.
   Do not type those credentials into TMDL or commit local Desktop settings.
5. Refresh all tables, confirm source/version/observation labels and inspect all four pages.

The script prints the exact new `output/powerbi/<mode>/<UTC timestamp>-<unique suffix>/RetailLens.pbip`
and opens that file after validation. Every invocation prepares a fresh directory, so old visuals
and `.pbi/unappliedChanges.json` cannot replace the reviewed definitions. Previous sessions and
user edits are preserved. Pipeline and PBIP use the same environment > `.env` > defaults
precedence for host, port and database. Passwords remain in Desktop's credential store;
they are absent from TMDL, preparation evidence and Git.
If the PostgreSQL connector prompts for its supported driver in your Desktop version, follow
[Microsoft's connector instructions](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

## Runtime checklist

Record each gate separately with date, mode/source and result:

- DESKTOP_OPEN: source and local copy open without schema/model/report errors.
- DATA_REFRESH: PostgreSQL partitions import all eight tables and source labels agree.
- DAX_RUNTIME_RECONCILIATION: run `powerbi/RetailLens.SemanticModel/DAXQueries/Reconciliation.dax`
  in DAX Query View, compare SQL at identical dates/segments/populations; compare money to cents
  and unrounded ratios within1e-10, without judging only formatted card labels.
- VISUAL_QA: Overview, Deliveries and reviews, Sellers and categories, Data quality all render;
  legends/units/counts/coverage readable, slicers/crossfilters correct, diagnostic order IDs
  discoverable. Capture screenshots only from this actual render and label data mode.

Whole-source real expected values: GMV13,221,498.11; eligible96,478; AOV137.0415857501191982;
on-time88,587/95,097; reconciliation matched96,178/mismatch299/incomparable1 for delivered;
repeat1,519/75,703 with observation_end2018-09-01. Use the run's CSV/JSON for exact evidence.

Synthetic runtime checks (reimport canonical fixture before refresh):

| Selection | Expected |
| --- | --- |
| All | GMV340; six GMV orders; AOV340/6; on-time3/5; repeat1/4 |
| Purchase dates January2018 | GMV230; three GMV orders; AOV230/3; on-time2/3; repeat1/3 |
| Category books, all dates | Segment item value240; six segment orders; value/order40 |
| Seller s1, all dates | Segment item value210; three segment orders; value/order70; single-seller on-time1/2 |
| Category/seller filter | Full-order AOV and cohort repeat retain their defined global segment scope |
| Equal-price o3 | Item value80; conflicting latest reviews excluded; multi-seller delivery attribution excluded |
| Payment o1 | expected110/paid110/delta0 despite two payments and installment counts |
| Payment o8 | delta0.01 matched under default tolerance |

Date filters use purchase date for orders, first purchase for cohorts. Order status/customer
state/category/seller do not change cohorts through inactive/unlinked paths. Product/seller
do affect item segment measures. Single-seller delivery is explicitly attributed by TREATAS;
it is not a category-specific causal metric. Source metadata/quality snapshots stay global.

Consult `docs/PROJECT_STATE.json` and the current run's `evidence/powerbi_runtime/` for executed
gates and exact evidence. Installation and process launch alone do not prove report opening;
an evaluating refresh dialog does not prove data loading. Preserve unavailable gates separately
from errors actually observed. Do not mark runtime PASS from JSON/TOM or matching SQL alone.

## Accepted portfolio presentation

Local MVP/report and Docker are accepted; RL-01–RL-08 are CLOSED_ACCEPTED.
REMOTE_CI remains NOT_RUN. The later RL-08 Desktop endpoint refresh used 5435;
the earlier complete model/rendering checks above remain historical accepted evidence.
See [final acceptance](FINAL_ACCEPTANCE.md), [real screenshots](images/README.md)
and [presentation guide](PRESENTATION.md). No runtime checks were repeated to prepare
these documentation and image copies.

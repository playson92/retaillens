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
Official TOM19.117.0 deserializes the TMDL model. These checks execute neither M nor DAX.
See the run's `pbip_validation.json`, `pbip_postgres.json` and `tmdl_parse.json` for exact counts.

The model's money type is TOM/TMDL Decimal (Power BI fixed decimal), with Currency.Type in M.
It supports the source's two-decimal amounts exactly. Reconciliation status is decided in
PostgreSQL NUMERIC; display-only tolerance is text so finer configured tolerance is retained.
[Microsoft documents the fixed decimal/TOM Decimal mapping](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types).

## First open

1. Prepare the warehouse using `scripts/demo.ps1 -Mode real -ObservationEnd 2018-09-01`.
   Invoke scripts via `powershell -NoProfile -ExecutionPolicy Bypass -File` (README).
2. Install/use Power BI Desktop and enable PBIP/PBIR features if the version requests them.
3. Run `scripts/open_powerbi.ps1 -Mode real` (optionally `-DesktopPath <exe>`).
4. For PostgreSQL Database authentication, enter DATABASE_USER/PASSWORD from local `.env`.
   Desktop connects to host DATABASE_HOST:DATABASE_PORT (default127.0.0.1:5433), database retaillens.
   Do not type those credentials into TMDL or commit local Desktop settings.
5. Refresh all tables, confirm source/version/observation labels and inspect all four pages.

The script creates `output/powerbi/real/RetailLens.pbip` without changing tracked definitions.
The authored source uses relative paths and credentials stay in Desktop's credential store.
If the PostgreSQL connector prompts for its supported driver in your Desktop version, follow
[Microsoft's connector instructions](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

## Remaining runtime checklist — NOT_RUN on implementation host

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

Desktop absence is a specific external verification gap, not a reason to omit report files.
Do not mark these runtime gates PASS on the basis of JSON, TOM parse or matching SQL tests.

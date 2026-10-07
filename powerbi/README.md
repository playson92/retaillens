# RetailLens Power BI project

The project contains the complete authored report and Import model: four PBIR
pages, 55 native visuals, eight SQL-backed TMDL tables, 49 DAX measures and five
single-direction relationships. Definition validation and report execution are
separate checks. An official schema or TMDL parse does not demonstrate that the
report has opened, refreshed or rendered in Desktop.

Start the database and prepare real or synthetic marts using the repository demo
commands, then open the existing project:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/open_powerbi.ps1 -Mode real
```

For the fixture use `-Mode synthetic`. The model defaults to real data. Both modes
share definitions but use separate PostgreSQL schemas, `rl_real` and
`rl_synthetic`; the mode is displayed on every page. On first connection, use
Desktop's **Database** credentials for `localhost:5433`, database `retaillens`,
with the local username and password from `.env`. Credentials are entered only
into Desktop's local credential store. Select **Refresh**. No Power BI account,
Service publication or manually designed visuals are needed for the local report.
Use Desktop **Transform data > Edit parameters** if connection settings differ.
Parameters `ServerHost`, `ServerPort`, `DatabaseName` and `DataMode` are text
expressions in `RetailLens.SemanticModel/definition/expressions.tmdl`.

The Desktop client uses the published host port (default `localhost:5433`). A
client inside Compose uses service `db` and its internal port `5432`. Refresh the
whole model after changing DataMode; a partial table refresh must not mix modes.

| Page | Content and filter behavior |
| --- | --- |
| Overview | Delivered GMV in BRL, same-population AOV and order count, monthly trends, repeat cohorts, window exclusions and global source metadata. Date filters purchase/first-purchase dates. Order/group selection does not change the repeat KPI. |
| Deliveries and reviews | Eligible denominator, on-time rate, late days, customer states, selected latest review distribution and timing groups with order counts and review coverage. Missing/inconsistent dates and ambiguous reviews have separate counts. |
| Sellers and categories | Item value, item value per segment order and shares. Seller/category filters affect item metrics. Seller delivery/reviews use single-seller orders and ignore product/category selection; global multi-seller exclusions are visible. |
| Data quality | Global rule occurrences, payment matching with comparable denominator, noncomparable share, all-status order diagnostics, exact reconciliation tolerance text and source SHA256. Date/order/status filters do not change the global quality snapshot. |

All pages have a field-bound date range slicer. The Data quality page has an order
ID dropdown and an order ID filter in the Filters pane; use the dropdown's Search
menu to find a specific order. All chart, table and slicer interactions are
persisted in each page's `visualInteractions`. There are no custom visuals or
image mockups. Tables and charts use real semantic field bindings in
`visual.query.queryState`, not static values. Textboxes explain the population.
Schema validation confirms native query roles, but native rendering still
requires Desktop validation.

Relationships are `Date -> Orders -> Items`, `Date -> Cohorts`,
`Product -> Items` and `Seller -> Items`. Every arrow represents one-way filtering
from a unique dimension/parent key to its child; there is no bidirectional filter
or ambiguous path. Seller timing uses `TREATAS` onto `Orders[single_seller_id]`,
with `seller_count = 1`; it does not allocate multi-seller outcomes. Cohorts are
computed before report-period filters, identify `customer_unique_id`, require the
recorded assumed 90-day observation window and exclude equal-time purchases as
later events. The date filter acts on the customer's first observed purchase;
category, seller, order status and customer-state selections do not act on M5.

Money columns use TMDL/TOM `decimal` and Power Query `Currency.Type`, which are
fixed decimal with four fractional digits. Olist input amounts have two decimal
digits, so their cents are preserved. TOM `double` would be floating point and is
unused here. Reconciliation decisions are made in PostgreSQL `NUMERIC`, never
from visual floats; the configurable tolerance is imported as SQL-cast text so
arbitrary metadata precision remains visible. Ratios and averages may return
floating results and are compared to SQL with appropriate numerical tolerance.
[Microsoft's data-type mapping](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types)
describes TOM `DataType.Decimal` as the fixed decimal type.

Run offline and PostgreSQL checks:

```powershell
.venv\Scripts\python.exe scripts/validate_powerbi.py --postgres --mode real --output output/pbip-validation.json
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/parse_tmdl.ps1 -Download -Output output/tmdl-validation.json
```

The JSON validator uses 12 pinned Microsoft schemas, including every referenced
schema, without network access. `schemas/manifest.json` records the repository
commit and SHA256 for each schema. It checks required JSON properties, UTF-8
without BOM, relative paths, page/visual IDs, native field roles, field references,
static DAX dependencies, page bounds and explicit interaction coverage. With
`--postgres`, it compares all imported columns and unique non-null one-side keys
to the selected warehouse schema.

`parse_tmdl.ps1` uses Microsoft's official `TmdlSerializer` from pinned
`Microsoft.AnalysisServices` 19.117.0, net472 assemblies in Windows PowerShell. Its
optional `-Download` obtains the package from NuGet and checks its pinned SHA256.
The parser can run without the .NET SDK and without a model server. A successful
parse validates metadata and preserves DAX/Power Query expressions as text; it
does not execute those expressions. Package binaries remain under ignored
`output/tools`, excluded from the review bundle.

`RetailLens.SemanticModel/DAXQueries/Reconciliation.dax` provides an executable
runtime comparison query. After refresh, run it in Desktop's DAX query view and
compare with the SQL exports for the same date window and mode. The fixture query
adds seller/category filter scenarios and zero-denominator behavior. Execute all
queries, then inspect every page including empty selections, order lookup,
category/seller filter interaction, date range and missing-review groups. Save
real screenshots only after rendering and label their data mode.

Authored definitions can be regenerated deterministically with
`python powerbi/build_definitions.py`; this resets connection defaults to real
data and replaces the generated report/model definitions. Do not run it over
uncommitted Desktop edits. Schema refresh is a separate explicit network action,
`python powerbi/download_schemas.py`; ordinary validation never refreshes schemas.

The definitions follow Microsoft's documented
[PBIP structure](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview),
[PBIR structure](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report),
[semantic model structure](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
and [TMDL format](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview).
The base theme is CY26SU02; report/page/visual schemas are 3.3.0/2.1.0/2.9.0,
and report definition content version is 2.0.0. Use a current compatible Desktop
release. Definition JSON, TMDL parsing, Desktop open, refresh, DAX reconciliation
and visual QA must retain separate evidence statuses.

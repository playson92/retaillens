# Power BI definition review

This review covers the authored semantic model and report definitions. The SQL
warehouse contract was coordinated separately and checked against both real and
synthetic PostgreSQL schemas. Checks were executed locally on 7 October 2026.

| Gate | Result and evidence |
| --- | --- |
| Official PBIP/PBIR JSON schemas | PASS: 65 definition JSON files validated offline using 12 official Microsoft schemas pinned to commit `51c4d1bb5e31565eccfddc1f70c694ee71a183b8`. |
| Semantic references / layout / interactions | PASS: eight tables, 49 measures, four ordered pages, 55 native visuals and 114 field references; unique IDs, relative paths, native query roles, page bounds and explicit interaction coverage validated. |
| Warehouse field and relationship keys | PASS: real and synthetic source columns present; Orders, Date, Product and Seller relationship keys unique and non-null. |
| Official TMDL parser | PASS: Microsoft.AnalysisServices 19.117.0 `TmdlSerializer` loaded all eight tables, 49 measures, five relationships and five expressions at compatibility level 1600. |
| Money storage metadata | PASS: official TOM deserialization confirms six monetary columns use fixed `Decimal`; Power Query applies `Currency.Type`. Arbitrary-precision tolerance is SQL-cast text. |
| Desktop open / refresh | NOT_RUN: requires Power BI Desktop and its PostgreSQL connector runtime. |
| DAX execution and SQL agreement | NOT_RUN: static dependencies are checked; the actual DAX engine has not run. Ready-to-run queries are in `DAXQueries/Reconciliation.dax`. |
| Visual QA / screenshots | NOT_RUN: no report pages were rendered. Layout bounds are a static check, not an inspection of UI rendering. |

The review checked the five KPI populations against the analytical contract.
GMV and AOV share the eligible delivered population; seller/category metrics use
eligible item amounts and explicitly name segment value per order. Delivery
does not depend on money completeness. Review comparisons use a single selected
valid response and show sample size and coverage. Payment matching uses the
SQL-derived complete-side status and delivered comparable denominator. The
missing-payment measure includes absent payment rows via `ISBLANK(paid_amount)`,
and preserves legitimate zero amounts. Repeat cohorts use first purchases
calculated in SQL before report filters and retain full-window exclusions.

All relationships filter in one direction. Seller timing uses explicit
single-seller `TREATAS`; category selection filters seller item value but does
not filter the seller delivery/review visual. Repeat ignores non-date order and
segment selections. Global quality/provenance visuals have no incoming visual
filters. Every page displays data mode and source version, source calendar dates
remain timezone-naive, and explanatory text defines blank denominators and
avoids causal attribution.

The schema intentionally allows arbitrary native visual formatting object names.
Consequently, schema validation cannot prove that Power BI accepts every visual
property or renders every field as intended. The runtime gates remain separate
and must be completed after installing/opening Desktop; no screenshots or
runtime PASS claims have been fabricated.

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
| Desktop open / refresh | PASS: official Desktop 2.158.1304.0 opened/refreshed exact fresh real and synthetic copies; imported table counts and Run identity match independent PostgreSQL proofs. |
| DAX execution and SQL agreement | PASS: actual Desktop-hosted model executed the five supplied EVALUATE blocks per mode and the full 49-measure filter matrix via official ADOMD 19.117.0; 32 required queries, 962 strict comparisons, no mismatches. |
| Visual QA / screenshots | PASS: all four native pages inspected in both modes; eight genuine final screenshots and actual date/category/seller/order UI interactions retained in the runtime evidence. |

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
property or renders every field as intended. The separate actual runtime checks
are recorded in `output/codex_runs/20261007T204100Z/evidence/powerbi_runtime/runtime.json`,
with exact PBIP paths, input hashes, engine catalogs, source identities and raw
results. Native scrolling/tooltips remain for long tables and crowded axes.

Runtime exposed a positive-denominator zero-numerator issue: January 2018 and
seller s2 had one eligible order but BLANK on-time count/rate. Six base counters
now use COALESCE0; the actual corrected model returns 1/0/0 while empty-denominator
rates remain BLANK. Independent SQL v2 retains that distinction. Monetary sums
agree exactly; Currency-derived averages agree to cents and within 0.00005,
other numeric comparisons use absolute tolerance 1e-10. UI inspection also found
clipped dropdowns and a metadata row; hiding duplicate slicer field headers and
enlarging the metadata table resolved these in both final rendered modes.

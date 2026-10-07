# Three-minute demo

Prepare: `scripts/setup.ps1`, then `scripts/demo.ps1 -Mode real -ObservationEnd 2018-09-01`.
Invoke scripts with `powershell -NoProfile -ExecutionPolicy Bypass -File` as shown in README;
this works with the host's default restricted script policy without a global policy change.
With Desktop installed, run `scripts/open_powerbi.ps1 -Mode real`, authenticate from local
`.env` and refresh. The current run passed Desktop open, refresh, DAX/SQL and all four pages in both modes;
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

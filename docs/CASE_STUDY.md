# RetailLens: trustworthy marketplace metrics

Joining raw items, payments and reviews can multiply money; missing dates and incomplete
follow-up change denominators. RetailLens makes those choices reproducible from Olist to
PostgreSQL and a reviewable Power BI project.

Official Olist v2 (CC BY-NC-SA 4.0): 99,441 orders, purchases 2016-09-04–2018-10-17. Study:
whole source, tolerance 0.01 BRL, assumed follow-up through start of 2018-09-01. September has
16 and October 4 source orders, none delivered; the sparse tail is excluded from follow-up,
but the chosen cutoff still does not prove completeness. Run `20261007T191556Z`, evidence at
`output/codex_runs/20261007T191556Z/evidence/real/`, also included in the review bundle.

## Three supported findings

1. **Observed reviews differ between delivery groups.** 88,587 eligible on-time orders have
   88,101 reviews, mean 4.28984; 6,510 late orders have 6,357 reviews, mean 2.26915. Evidence:
   `sql/05_deliveries_reviews.sql`, grouped SQL in `scripts/check_real_run.py`, `sql_evidence.json`.
   Investigate late-delivery segments and communications. This is association, not evidence
   that delivery interventions cause that score difference. Coverage is 99.45% vs 97.65%;
   1,381 delivered orders lack valid date/chronology eligibility. State comparisons need counts.

2. **A small complete delivered population needs financial investigation.** 96,178 orders match,
   299 exceed one-cent tolerance, 1 is incomparable. Evidence: `sql/07_reconciliation.sql` and
   `reconciliation_diagnostics.csv`. Mismatches total +2,832.14 BRL paid-minus-expected, about
   0.310% of comparable delivered orders. Inspect order/source records before inferring refunds,
   losses or allocations. Tolerance applies per order; matched deltas need not sum to zero.

3. **Observed repeat is low under the chosen historical window.** 1,519/75,703 eligible persons
   repeat within 90 days (2.00653%), with 17,655 incomplete windows excluded. Evidence:
   `sql/08_repeat.sql` and export. This supports designing a future controlled repeat-purchase
   experiment; it is not churn or CLV. First observed is not necessarily first-ever purchase;
   255 simultaneous first-timestamp orders are not later repeats. Seller/category filters do
   not change this person-cohort metric.

## Decisions and verification boundary

Money is Decimal/NUMERIC; facts aggregate separately before joining. Whole-order delivered
GMV is 13,221,498.11 BRL over 96,478 orders; AOV137.04159 BRL. Equal-price items sum normally,
without SUM(DISTINCT). Latest valid review wins; conflicting latest scores are excluded with
raw rows retained. Synthetic tests cover that ambiguity, although Olist had no latest tie
conflict under these rules.

Separate real/fixture schemas prevent invented findings. A transaction publishes raw/staging/
marts together. Reimport/rebuild preserve results. Independent review found uncertain seller
attribution, tolerance evidence and public fallback risks; regressions protect the fixes.
Four native PBIR pages and 49 DAX measures are authored and officially parsed/schema-validated.

Overall acceptance is **PARTIAL**: Docker/Compose, Desktop opening/refresh, DAX reconciliation,
visual QA and remote Actions were not run. No screenshots are supplied. Next: execute
`docs/POWER_BI.md` on an installed Desktop and test Compose on a Docker-enabled machine.

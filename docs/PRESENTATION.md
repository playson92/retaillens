# Present RetailLens in three minutes

## Prepare once before presenting

Use the [README setup](../README.md) with Python 3.12, the configured Portable
database and Power BI Desktop. The accepted checkout uses **127.0.0.1:5435** and
preserved `output/postgres_data`. Match configuration: process environment >
private `.env` > defaults; select another free port on a new machine.
Prepare real marts using the existing `scripts/demo.ps1 -Mode real -Backend Portable -ObservationEnd 2018-09-01`, then `scripts/open_powerbi.ps1 -Mode real` through
the PowerShell invocation shown in README. Authenticate locally and refresh all tables.
Do these preparation steps before the timed talk.

Confirm **real / olist-v2**, full source dates, assumed cutoff 2018-09-01 and no
extra page filters. Keep [case study](CASE_STUDY.md), [small SQL results](evidence/real/README.md)
and [acceptance](FINAL_ACCEPTANCE.md) ready. The [existing detailed demo](DEMO.md)
is the source scenario; this page is its short presenter guide.

## Timed talk

| Time | Page / action | Explain |
| --- | --- | --- |
| 0:00–0:40 | Overview; show source labels, then change purchase dates | Delivered item GMV 13.22 million BRL and whole-order AOV 137.04 BRL; exclusions and boundary months prevent an unsupported growth claim. |
| 0:40–1:20 | Deliveries and reviews; compare timing groups | 88,587/95,097 on time; 1,381 date exclusions. Review means 4.29 vs 2.27 need counts and coverage; association is not causation. |
| 1:20–2:00 | Sellers and categories; change one category or seller | Item-grain segment value; single-seller delivery attribution; person-cohort repeat ignores those segment filters. |
| 2:00–2:40 | Data quality; inspect reconciliation/status and an order | 299 delivered mismatches and 1 incomparable; global quality snapshot has a different scope from selected order diagnostics. |
| 2:40–3:00 | Open linked SQL/result and acceptance record | Trace one result to its denominator/query, distinguish historical local acceptance from the exact-SHA four-job remote PASS. |

Reset filters after each example so the next page starts from its stated scope.
If Desktop is unavailable at presentation time, show the
[previously executed real captures](images/README.md) and SQL results explicitly
as recorded evidence; do not describe this as a new live session.
A film is optional. **No recording file is supplied or claimed.**

## Published repository and verified CI

The public repository is [playson92/retaillens](https://github.com/playson92/retaillens).
Its default branch is `feat/retaillens-mvp`. First publication was explicitly
authorized after the history/private-file audit; no merge or force-push was used.
[PUBLICATION.md](PUBLICATION.md) records the first successful exact-SHA run and all
four required jobs. The earlier portfolio preparation had no remote; that is a
historical fact, not the current repository status.

To inspect a later deliberately published commit, run from this checkout:

~~~powershell
$publishedSha = git rev-parse HEAD
gh run list --repo playson92/retaillens --workflow ci.yml --branch feat/retaillens-mvp --commit $publishedSha --event push --json databaseId,headSha,event,status,conclusion,url
~~~

Select the actual run ID and inspect its jobs. PASS requires completed success for
quality, official Windows TMDL, PostgreSQL business contract and Docker/Compose.
Pending, skipped or missing checks are not PASS. Ordinary CI uses the synthetic
fixture and does not download full Olist or run Power BI Desktop.

README, all four real images, case-study links and the small SQL result set are
published. Keep MIT code, Olist-derived CC BY-NC-SA 4.0 attribution and Microsoft
schema notices separate. Local `output/`, raw CSVs, PostgreSQL storage, credentials
and Power BI cache remain excluded. Further remote writes require their own
authorized scope; this guide does not enable automatic publication.

Local Docker/Power BI acceptance does not need repetition for documentation
changes. No tag, release, public Power BI Service deployment or video is supplied.
Further implementation changes do not inherit the accepted commit's review
automatically. Portfolio order stays **B → C → D → A**.

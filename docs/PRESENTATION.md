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
| 2:40–3:00 | Open linked SQL/result and acceptance record | Trace one result to its denominator/query, distinguish actual local PASS from REMOTE_CI NOT_RUN. |

Reset filters after each example so the next page starts from its stated scope.
If Desktop is unavailable at presentation time, show the
[previously executed real captures](images/README.md) and SQL results explicitly
as recorded evidence; do not describe this as a new live session.
A film is optional. **No recording file is supplied or claimed.**

## First repository publication — future manual execution

The project is locally accepted and prepared for sharing. At portfolio preparation
there was **no configured Git remote**. The following commands are instructions
for a separately authorized first publication; they were not executed here.

1. Choose GitHub owner, visibility and intended default branch. Keep MIT code,
   Olist-derived CC BY-NC-SA 4.0 attribution and Microsoft schema notices separate.
   The four PNGs and aggregate proof subset have provenance; full local `output/`,
   raw input, database storage, credentials and Power BI cache stay excluded.
2. Review the local tracked diff/source and sign in to the intended GitHub account.
   For a new public repository with the name `retaillens` and no existing origin,
   run the example below sequentially from the repository root, stopping on a non-zero
   exit code. Choose `--private` instead
   if that is the intended visibility. If the repository/origin already exists,
   verify and use it instead of creating a duplicate.

~~~powershell
gh auth status
gh repo create retaillens --public --source . --remote origin
git push -u origin feat/retaillens-mvp
$publishedSha = git rev-parse HEAD
gh run list --workflow ci.yml --branch feat/retaillens-mvp --commit $publishedSha --json databaseId,headSha,status,conclusion,url
~~~

The commands do not request a merge. An empty remote may initially select the
first published branch as its default; choose the intended default separately.
`git push` is a future publication action, not an action already taken in this run.

3. [.github/workflows/ci.yml](../.github/workflows/ci.yml) already triggers on
   `feat/**` pushes. Record the run URL, **head SHA**, each job conclusion and logs:
   Python quality/offline tests/schema validation, Windows official TOM,
   PostgreSQL business contract and Docker/Compose fixture. Ordinary CI does not
   download full Olist. After choosing the actual run ID from the list, use
   `gh run watch <run-id> --exit-status`. Pending/skipped/missing jobs are not PASS.
4. Keep **REMOTE_CI: NOT_RUN** until an actual run for the published SHA exists.
   Then update state with its real outcome and evidence: PASS only for completed
   required checks; failures need investigation, not relabelling.
5. Check the published branch's README image/relative links and case study rendering.
   Add a repository description and topics if desired. No tag, release, public
   Power BI Service deployment or video is required for this local MVP.

Local Docker/Power BI acceptance does not need repetition for these documentation
changes. Further implementation changes do not inherit the accepted commit's
review automatically. Portfolio order stays **B → C → D → A**.

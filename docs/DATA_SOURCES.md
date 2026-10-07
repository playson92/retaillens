# Data and technical sources

Verified during implementation on 7 October 2026. Official Olist was downloaded,
profiled, imported and analysed on PostgreSQL 17.6 in run 20261007T191556Z. Review-fix run
20261007T204100Z reused, reprofiled and reimported those pinned bytes and records new SQL,
reimport and before/after evidence rather than inheriting previous test claims.
Raw data stay local and excluded from Git/review ZIP; small derived evidence is included.
Kaggle public datasets/list API confirms dataset id 55151, currentVersionNumber 2,
lastUpdated 2021-10-01T19:08:27.97Z and licenseName CC BY-NC-SA 4.0.
Pinned handle: olistbr/brazilian-ecommerce/versions/2.
The initial supported download resolved latest to archive 2; the metadata and file
SHA256 manifest pin that exact downloaded publication for subsequent runs.

## Data

Olist official dataset:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Historical dataset, described as 2016–2018; source license CC BY-NC-SA 4.0.
At implementation time verify the displayed license, original file names,
schema, actual date range and version. Keep attribution and source terms
separate from the MIT license of project code.

Official Kaggle client:
https://github.com/Kaggle/kagglehub

Try supported public download first. Authentication is only required for some
resources; do not assume a token is always required or always unnecessary.
Use existing authorized local credentials without printing them. If consent or
login is actually required, complete independent fixture work and report the
specific missing step. Do not use an unverified mirror to conceal a source issue.
Pin a concrete dataset version and record checksums after the first download.

## Power BI

https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview
https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview
https://learn.microsoft.com/en-us/power-query/connectors/postgresql
https://learn.microsoft.com/en-us/power-bi/guidance/star-schema
https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp

Microsoft documents programmatic PBIP/TMDL/PBIR authoring. Use supported JSON
schemas and TMDL, with pinned schema identifiers in the project. Do not confuse
the documented PBIR definition/report.json with the unsupported old report.json
format. Model/report definition versions are separate from the PBIR report
version; choose a compatible combination from the official documentation.
The Authoring MCP can help with models and DAX when available, but does not
author report pages or their layout. It is optional; do not make an additional
service or subscription a dependency of this local project.

## Inherited quality tooling

https://github.com/actions/checkout
https://github.com/actions/setup-python

The provided template uses v7 of both actions. Preserve or deliberately pin
supported versions after verification; do not downgrade from stale assumptions.

## Source manifest to produce during implementation

For each input: official URL, dataset version, retrieval time, license reference,
file name, SHA256, row count, actual date range, parsing decisions and data mode.
For findings: query path/version, input manifest, parameters and output path.

## Implemented source records

Local SOURCE.json records mode, official URL, version, retrieval time and license.
It also pins each CSV SHA256; reuses/imports reject changed real input files.
The current manifest is in output/codex_runs/20261007T204100Z/evidence/real/source_manifest.json;
the previous run remains available separately.
Required CSV counts total 550,759 rows; optional geolocation has 1,000,163 rows,
retained/profiled outside the warehouse MVP. Source purchase range is
2016-09-04T21:15:19 through 2018-10-17T17:30:18, naive source timestamps.
Dataset derivatives retain source license/attribution separately from MIT code.

Python resolved dependencies are pinned in requirements.lock. The inherited v7
checkout/setup-python actions were verified against their official repositories,
then preserved. Portable PostgreSQL17.6 comes from the EDB binary distribution;
scripts/local_postgres.py pins its archive URL/SHA256. Actual server version is
recorded in sql_evidence.json. Docker image tags are version pinned, not digest pinned;
Docker build/Compose have not been executed here.

Power BI schema source revisions and hashes are in powerbi/schemas/manifest.json.
The official TOM parser version 19.117.0 and
NuGet SHA256 are pinned by scripts/parse_tmdl.ps1. Schema/parser validation is distinct
from Desktop, Power Query and DAX runtime checks; consult PROJECT_STATE.json for their actual
current outcomes. Desktop 2.158.1304.0 was installed using the official Microsoft Store package
9NTXR16HNW1T. The run retains the installation command, exit code and runtime evidence.

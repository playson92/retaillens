# Template adaptation

Source: portfolio-project-template.zip supplied by Jonatan Tomaszewicz.
Date: 7 October 2026.
Source archive SHA256: 2dbe488ed094405a95ea7aef45ef8038f941381222d6073f5526543dba6a103b

All 19 authored files were read. Seven are empty .gitkeep placeholders.
Source code/configuration amount to 8045 bytes.
The original archive also contains a local Python environment and caches.
The starter uses authored files, without copying that environment or Git history.
Original per-file hashes are in TEMPLATE_SOURCE_MANIFEST.json.

## Retained

- Author Jonatan Tomaszewicz and MIT code license.
- Python >=3.12,<3.13; src layout and setuptools.
- pytest strict config/markers; Ruff py312, line length 100 and original lint rules.
- Branches per feature/fix, focused local commits, tests and documentation updates.
- Existing GitHub Actions quality workflow and read-only workflow permissions.
- Separate raw, processed, sample, docs, SQL, scripts and Docker directories.
- Local-first execution; optional cloud is not required by this MVP.

## Actual contents of the original template

One static health_check and one matching test; pyproject, quality workflow,
configuration examples and documentation. SQL, Docker and data directories were
placeholders. The archive does not prove successful installation, CI, database
integration, an Olist import or a report.

## Adaptation made in this starter

- Distribution/module renamed to retaillens and test import updated.
- README describes starter status; project plan and execution task added.
- Separate analytical contract, source notes and state file added.
- Category order changed to B, C, D, A; current project B1.
- Runtime output and Power BI cache/local settings excluded from Git.
- Text normalized to UTF-8 without BOM; Power BI/Windows line ending rules added.
- Local example database parameters use retaillens and host port 5433.

The adaptation is a starting point for Codex. Pipeline, database, models and
report remain implementation work. The original supplied archive is preserved.

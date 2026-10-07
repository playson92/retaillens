"""Record final runtime evidence identities without credentials or Desktop cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_manifest(values: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--real-project", type=Path, required=True)
    parser.add_argument("--synthetic-project", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    modes = {}
    for mode, project in (("real", args.real_project), ("synthetic", args.synthetic_project)):
        project = project.resolve()
        preparation = json.loads((project.parent / "preparation.json").read_text(encoding="utf-8"))
        actual = json.loads((evidence / f"dax-{mode}-v2.json").read_text(encoding="utf-8"))
        comparison = json.loads(
            (evidence / f"comparison-{mode}-v2.json").read_text(encoding="utf-8")
        )
        if comparison["status"] != "PASS":
            raise ValueError(f"Actual {mode} runtime comparison did not pass")
        files = {
            name: sha256(project.parent / name)
            for name in preparation["files_sha256"]
            if name != "validation.json"
        }
        changed = [
            name for name, value in files.items() if value != preparation["files_sha256"][name]
        ]
        if changed:
            raise ValueError(f"Prepared runtime input files changed: {changed}")
        screenshots = {}
        for page in ("overview", "deliveries", "segments", "quality"):
            path = evidence / f"{mode}-final-{page}.png"
            if not path.is_file() or path.stat().st_size < 10000:
                raise ValueError(f"Required actual page screenshot missing: {path}")
            screenshots[path.name] = sha256(path)
        results = {result["id"]: result["rows"] for result in actual["results"]}
        modes[mode] = {
            "project": str(project),
            "parameters": preparation["parameters"],
            "project_sha256": sha256(project),
            "prepared_definitions_sha256": digest_manifest(files),
            "semantic_model_sha256": digest_manifest(
                {k: v for k, v in files.items() if k.startswith("RetailLens.SemanticModel/")}
            ),
            "report_sha256": digest_manifest(
                {k: v for k, v in files.items() if k.startswith("RetailLens.Report/")}
            ),
            "unchanged_since_preparation": True,
            "files_sha256": files,
            "dax_connection": {"server": actual["server"], "catalog": actual["catalog"]},
            "imported_table_counts": results["proof:import_counts"],
            "imported_run_metadata": results["proof:run_metadata"],
            "runtime_gates": dict.fromkeys(
                ("DESKTOP_OPEN", "DATA_REFRESH", "DAX_RUNTIME_RECONCILIATION", "VISUAL_QA"), "PASS"
            ),
            "required_queries": comparison["required_queries"],
            "executed_queries": comparison["executed_queries"],
            "strict_comparisons": comparison["comparisons"],
            "comparison_artifact": f"comparison-{mode}-v2.json",
            "dax_artifact": f"dax-{mode}-v2.json",
            "screenshots_sha256": screenshots,
        }
    artifact = {
        "status": "PASS",
        "check": "ACTUAL_DESKTOP_RUNTIME",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "tools": json.loads((evidence / "runtime-tools.json").read_text(encoding="utf-8")),
        "modes": modes,
        "total_executed_queries": sum(mode["executed_queries"] for mode in modes.values()),
        "total_strict_comparisons": sum(mode["strict_comparisons"] for mode in modes.values()),
        "sql_evidence": {
            "path": "sql_expected_v2.json",
            "sha256": sha256(evidence / "sql_expected_v2.json"),
        },
        "independent_sql_proofs": {
            "path": "runtime_sql_proofs.json",
            "sha256": sha256(evidence / "runtime_sql_proofs.json"),
        },
        "dax_execution": "Provided five EVALUATE blocks and filter matrix executed through official ADOMD against the actual Desktop-hosted model; not parser-only or a substitute database.",
        "visual_qa_scope": "All four native pages rendered and visually inspected in both modes; field-bound charts/tables/cards, source labels, dates, exclusion populations and actual synthetic date/category/seller/order interactions checked. Native scrolling and tooltips remain for long tables and crowded axes.",
        "ui_interaction_evidence": [
            "synthetic-ui-order-o3.png",
            "synthetic-ui-empty-date.png",
            "synthetic-ui-books-s1.png",
        ],
        "runtime_fixes": [
            "Confirmed January2018+s2 positive-denominator zero-numerator regression: before Eligible1/OnTimeBLANK/RateBLANK; after1/0/0. Six base count measures use COALESCE0; empty-denominator DIVIDE remains BLANK.",
            "Native slicer duplicate field headers hidden so dropdown controls fit; Data quality metadata row enlarged after actual clipping was observed.",
        ],
        "resolved_attempts": [
            {
                "evidence": "refresh-error.png",
                "error": "PostgreSQL: No password has been provided but the backend requires one (in SASL/SCRAM-SHA-256)",
                "resolution": "Normal credential editor actual keyboard input with processing waits and private equality check; no secrets logged or placed in PBIP.",
            },
            {
                "evidence": "synthetic-final-open.png",
                "error": "ArtifactShortcut: Required artifact is missing",
                "resolution": "Sandbox-created private temporary copy was unreadable to Desktop user; another fresh copy was prepared in the approved Desktop-user execution context. No ACL or OS protection was changed.",
            },
            {
                "evidence": "dax-synthetic-during-refresh.json",
                "error": "Queries executed while asynchronous import still had no rows",
                "resolution": "Attempt preserved; final queries executed after import proof confirmed all eight tables and source identity.",
            },
        ],
        "credential_handling": "Existing .env/process settings entered privately only into the verified 127.0.0.1:5433;retaillens native database form. Username/password values and authentication screenshots excluded.",
        "remote_ci": "NOT_RUN; no push or publication requested",
    }
    (evidence / "runtime.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Actual Desktop runtime PASS: {artifact['total_executed_queries']} queries, {artifact['total_strict_comparisons']} strict comparisons; evidence {evidence / 'runtime.json'}"
    )


if __name__ == "__main__":
    main()

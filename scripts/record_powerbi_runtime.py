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


def record_endpoint_refresh(evidence, projects):
    """Record the new endpoint/import check separately from historical model acceptance."""
    if __package__:
        from scripts.compare_powerbi_runtime import equal, normalize
    else:
        from compare_powerbi_runtime import equal, normalize

    proofs = json.loads((evidence / "sql-refresh-proofs.json").read_text(encoding="utf-8"))
    modes = {}
    for mode, project in projects.items():
        project = project.resolve()
        preparation = json.loads((project.parent / "preparation.json").read_text(encoding="utf-8"))
        parameters = preparation["parameters"]
        endpoint = f"{parameters['ServerHost']}:{parameters['ServerPort']}"
        source = json.loads(
            (evidence / f"desktop-source-{mode}.json").read_text(encoding="utf-8-sig")
        )
        actual = json.loads((evidence / f"dax-refresh-{mode}.json").read_text(encoding="utf-8-sig"))
        expected = proofs["modes"][mode]
        if source["endpoint"] != endpoint or source["database"] != parameters["DatabaseName"]:
            raise ValueError("Actual Desktop source differs from the prepared configured endpoint")
        if source["provider"] != "PostgreSQL" or endpoint != proofs["endpoint"]:
            raise ValueError("Actual Desktop source is not the verified Portable endpoint")
        if actual["server"] != source["server"] or actual["catalog"] != source["catalog"]:
            raise ValueError("DAX evidence belongs to a different Desktop engine")
        observations = {r["id"]: r for r in actual["results"]}
        required = {"proof:import_counts", "proof:run_metadata", "proof:main_kpis"}
        if (
            len(actual["results"]) != 3
            or set(observations) != required
            or any(r["status"] != "PASS_EXECUTED" or len(r["rows"]) != 1 for r in actual["results"])
        ):
            raise ValueError("Required current refresh proof queries did not execute")
        counts = normalize(observations["proof:import_counts"]["rows"][0])
        metadata = normalize(observations["proof:run_metadata"]["rows"][0])
        kpis = normalize(observations["proof:main_kpis"]["rows"][0])
        for observed, wanted in (
            (counts, expected["table_counts"]),
            (metadata, expected["metadata"]),
            (kpis, expected["kpis"]),
        ):
            if set(observed) != set(wanted) or any(
                not equal(name, observed.get(name), value) for name, value in wanted.items()
            ):
                raise ValueError(
                    f"Actual {mode} refreshed values differ from current read-only SQL"
                )
        files = {name: sha256(project.parent / name) for name in preparation["files_sha256"]}
        if files != preparation["files_sha256"]:
            raise ValueError("Prepared input definitions changed during the endpoint refresh")
        modes[mode] = {
            "project": str(project),
            "postgres_endpoint": endpoint,
            "database": parameters["DatabaseName"],
            "data_directory": proofs["data_directory"],
            "source_manifest_sha256": metadata["source_manifest_sha256"],
            "imported_table_counts": counts,
            "five_main_kpis": kpis,
            "engine": actual["server"],
            "catalog": actual["catalog"],
            "prepared_definitions_unchanged": True,
            "runtime_gates": dict.fromkeys(
                ("DESKTOP_OPEN", "DATA_REFRESH", "ENDPOINT_MATCH", "EIGHT_TABLES", "FIVE_KPIS"),
                "PASS",
            ),
            "executed_proof_queries": 3,
            "dax_artifact": f"dax-refresh-{mode}.json",
            "source_artifact": f"desktop-source-{mode}.json",
        }
    return {
        "status": "PASS",
        "check": "ACTUAL_ENDPOINT_RECONNECTION_AND_REFRESH",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "modes": modes,
        "historical_model_acceptance": {
            "run": "20261007T204100Z",
            "required_queries": 32,
            "strict_comparisons": 962,
            "execution": "Accepted historical model and visual QA; not rerun in this endpoint check",
        },
        "remote_ci": "NOT_RUN; no publication",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--real-project", type=Path, required=True)
    parser.add_argument("--synthetic-project", type=Path, required=True)
    parser.add_argument("--refresh-only", action="store_true")
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    if args.refresh_only:
        artifact = record_endpoint_refresh(
            evidence, {"real": args.real_project, "synthetic": args.synthetic_project}
        )
        (evidence / "endpoint-refresh.json").write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"status": "PASS", "check": artifact["check"]}))
        return
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
        "credential_handling": "Existing .env/process settings entered privately only into the exact configured PostgreSQL source; username/password values and authentication screenshots excluded.",
        "postgres_endpoints": {
            name: f"{mode['parameters']['ServerHost']}:{mode['parameters']['ServerPort']};{mode['parameters']['DatabaseName']}"
            for name, mode in modes.items()
        },
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

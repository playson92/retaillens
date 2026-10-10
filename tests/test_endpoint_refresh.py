import json

import pytest
from scripts.record_powerbi_runtime import record_endpoint_refresh, sha256


def artifacts(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    projects = {}
    modes = {}
    for mode in ("real", "synthetic"):
        directory = tmp_path / mode
        directory.mkdir()
        project = directory / "RetailLens.pbip"
        project.write_text("{}")
        projects[mode] = project
        counts = dict.fromkeys(
            ("Orders", "Items", "Date", "Product", "Seller", "Cohorts", "Quality", "Run"), 1
        )
        metadata = {"data_mode": mode, "source_manifest_sha256": "a" * 64}
        kpis = {
            "Order Count": 1,
            "Delivered GMV": "0.00",
            "Delivered AOV": "0.00",
            "On Time Rate": None,
            "Observed Repeat 90d Rate": None,
        }
        preparation = {
            "parameters": {
                "ServerHost": "127.0.0.1",
                "ServerPort": "5434",
                "DatabaseName": "retaillens",
            },
            "files_sha256": {"RetailLens.pbip": sha256(project)},
        }
        (directory / "preparation.json").write_text(json.dumps(preparation))
        source = {
            "endpoint": "127.0.0.1:5434",
            "database": "retaillens",
            "provider": "PostgreSQL",
            "server": "localhost:55555",
            "catalog": mode,
        }
        (evidence / f"desktop-source-{mode}.json").write_text(json.dumps(source))
        rows = {
            "proof:import_counts": counts,
            "proof:run_metadata": metadata,
            "proof:main_kpis": kpis,
        }
        actual = {
            "server": source["server"],
            "catalog": source["catalog"],
            "results": [
                {"id": name, "status": "PASS_EXECUTED", "rows": [values]}
                for name, values in rows.items()
            ],
        }
        (evidence / f"dax-refresh-{mode}.json").write_text(json.dumps(actual))
        modes[mode] = {"table_counts": counts, "metadata": metadata, "kpis": kpis}
    proof = {
        "endpoint": "127.0.0.1:5434",
        "data_directory": "C:/projects/retaillens/output/postgres_data",
        "modes": modes,
    }
    (evidence / "sql-refresh-proofs.json").write_text(json.dumps(proof))
    return evidence, projects


def test_new_refresh_record_keeps_historical_model_evidence_separate(tmp_path):
    evidence, projects = artifacts(tmp_path)
    result = record_endpoint_refresh(evidence, projects)
    assert result["status"] == "PASS"
    assert result["historical_model_acceptance"]["strict_comparisons"] == 962
    assert all(mode["executed_proof_queries"] == 3 for mode in result["modes"].values())
    assert result["modes"]["real"]["postgres_endpoint"] == "127.0.0.1:5434"


@pytest.mark.parametrize(
    "change", ["endpoint", "engine", "null_zero", "missing_rows", "counts", "hash"]
)
def test_new_refresh_cannot_pass_for_wrong_source_or_unimported_model(tmp_path, change):
    evidence, projects = artifacts(tmp_path)
    path = evidence / "dax-refresh-real.json"
    actual = json.loads(path.read_text())
    if change == "endpoint":
        source_path = evidence / "desktop-source-real.json"
        source = json.loads(source_path.read_text())
        source["endpoint"] = "127.0.0.1:5433"
        source_path.write_text(json.dumps(source))
    elif change == "engine":
        actual["catalog"] = "another-model"
    elif change == "null_zero":
        actual["results"][2]["rows"][0]["On Time Rate"] = 0
    elif change == "missing_rows":
        actual["results"][1]["rows"] = []
    elif change == "counts":
        actual["results"][0]["rows"][0]["Orders"] = 0
    else:
        actual["results"][1]["rows"][0]["source_manifest_sha256"] = "b" * 64
    path.write_text(json.dumps(actual))
    with pytest.raises(ValueError):
        record_endpoint_refresh(evidence, projects)


def test_refresh_recorder_runs_as_a_standalone_script(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    from scripts import record_powerbi_runtime

    evidence, projects = artifacts(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(record_powerbi_runtime.__file__).resolve()),
            "--refresh-only",
            "--evidence",
            str(evidence),
            "--real-project",
            str(projects["real"]),
            "--synthetic-project",
            str(projects["synthetic"]),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
    assert (evidence / "endpoint-refresh.json").is_file()

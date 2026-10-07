"""Protect runtime evidence from missing queries, altered proofs and BLANK/zero swaps."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.build_runtime_dax_queries import dax_string
from scripts.compare_powerbi_runtime import compare, equal, required_queries

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime_case():
    expected = {
        "cases": {"full_source": {"measures": {"Delivered GMV": "100.00", "On Time Rate": None}}},
        "supplied_evaluate_queries": {"1_full_source": [{"GMV_BRL": "100.00"}]},
    }
    proofs = {
        "proofs": {
            "import_counts": [{"Orders": 2}],
            "run_metadata": [{"data_mode": "synthetic", "source_version": "fixture-v1"}],
        },
        "edges": {
            "seller_s2_zero_numerator": {"rows": [{"Eligible": 1, "OnTime": 0, "Rate": "0E-20"}]}
        },
    }
    actual = {
        "server": "localhost:12345",
        "catalog": "unit-fixture",
        "results": [
            {"id": name, "status": "PASS_EXECUTED", "rows": copy.deepcopy(rows)}
            for name, rows in required_queries(expected, proofs).items()
        ],
    }
    return expected, proofs, actual


def test_complete_runtime_queries_and_independent_proofs_pass(runtime_case):
    expected, proofs, actual = runtime_case
    report = compare("synthetic", expected, actual, proofs)
    assert report["status"] == "PASS"
    assert report["required_queries"] == report["executed_queries"] == 5
    assert report["comparisons"] == 9


@pytest.mark.parametrize(
    "remove_id",
    [
        None,
        "case:full_source",
        "supplied:1_full_source",
        "proof:import_counts",
        "proof:run_metadata",
        "edge:seller_s2_zero_numerator",
    ],
)
def test_missing_queries_fail_with_nonzero_cli_exit(runtime_case, remove_id, tmp_path):
    expected, proofs, actual = runtime_case
    actual["results"] = [
        result for result in actual["results"] if remove_id and result["id"] != remove_id
    ]
    expected_file, proofs_file, actual_file, output = [
        tmp_path / name for name in ("expected.json", "proofs.json", "actual.json", "report.json")
    ]
    expected_file.write_text(json.dumps({"modes": {"synthetic": expected}}), encoding="utf-8")
    proofs_file.write_text(json.dumps({"modes": {"synthetic": proofs}}), encoding="utf-8")
    actual_file.write_text(json.dumps(actual), encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "scripts/compare_powerbi_runtime.py"),
            "--mode",
            "synthetic",
            "--expected",
            str(expected_file),
            "--proofs",
            str(proofs_file),
            "--actual",
            str(actual_file),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 1, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert any(item["error"] == "Required query missing" for item in report["mismatches"])


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "failed", "count", "source", "edge"])
def test_corrupt_runtime_results_fail(runtime_case, mutation):
    expected, proofs, actual = runtime_case
    by_id = {result["id"]: result for result in actual["results"]}
    if mutation == "duplicate":
        actual["results"].append(copy.deepcopy(actual["results"][0]))
    elif mutation == "unknown":
        actual["results"].append({"id": "case:unknown", "status": "PASS_EXECUTED", "rows": []})
    elif mutation == "failed":
        by_id["proof:import_counts"]["status"] = "FAIL"
    elif mutation == "count":
        by_id["proof:import_counts"]["rows"][0]["Orders"] = 3
    elif mutation == "source":
        by_id["proof:run_metadata"]["rows"][0]["data_mode"] = "real"
    else:
        by_id["edge:seller_s2_zero_numerator"]["rows"][0]["Rate"] = None
    assert compare("synthetic", expected, actual, proofs)["status"] == "FAIL"


@pytest.mark.parametrize(
    ("name", "actual", "expected", "matches"),
    [
        ("Rate", None, 0, False),
        ("Rate", 0, None, False),
        ("Rate", None, None, True),
        ("Rate", 0.0, "0E-20", True),
        ("Count", False, 0, False),
        ("Delivered GMV", "100.00000001", "100.00", False),
        ("Delivered AOV", "56.6667", "56.6666666666666667", True),
        ("Delivered AOV", "56.6668", "56.6666666666666667", False),
        ("Delivered AOV", "1.01500", "1.01496", False),
        ("Rate", "0.33333333333", "0.3333333333333333", True),
        ("Rate", "0.33333333", "0.3333333333333333", False),
        ("Rate", "NaN", "0.0", False),
        ("analysis_start", "2018-01-01T00:00:00", "2018-01-01", True),
        ("analysis_start", "2018-01-01T03:00:00", "2018-01-01", False),
        ("imported_at", "2026-10-07T20:57:39.790", "2026-10-07T20:57:39.791803", True),
        ("imported_at", "2026-10-07T20:57:39.780", "2026-10-07T20:57:39.791803", False),
    ],
)
def test_strict_null_financial_and_datetime_semantics(name, actual, expected, matches):
    assert equal(name, actual, expected) is matches


@pytest.mark.parametrize(
    ("value", "literal"),
    [
        ('książki "premium"', '"książki ""premium"""'),
        (r"folder\seller", '"folder\\seller"'),
        ("s2", '"s2"'),
        ("", '""'),
    ],
)
def test_dax_literals_preserve_unicode_backslashes_and_double_quotes(value, literal):
    assert dax_string(value) == literal

"""Complete SQL evidence comparison regressions; no Docker or DB mutation required."""

import copy
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_docker_results.py"
SPEC = importlib.util.spec_from_file_location("check_docker_results", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def document(mode="synthetic"):
    """A complete small analysis document, preserving the pinned smoke-check facts."""
    facts = CHECKER.FACTS[mode]
    start, end = (
        ("2018-01-01", "2018-06-02") if mode == "synthetic" else ("2016-09-04", "2018-10-18")
    )
    metadata = {
        "data_mode": mode,
        "source_version": facts["source_version"],
        "source_manifest_sha256": "a" * 64,
        "analysis_start": start,
        "analysis_end_exclusive": end,
        "observation_end": facts["observation_end"],
        "observation_basis": "Explicit historical coverage assumption",
        "imported_at": "2026-10-07T19:00:00",
        "reconciliation_tolerance": "0.01",
    }
    results = {}
    for name, columns in CHECKER.COLUMNS.items():
        row = {field: ("value" if field in CHECKER.TEXT_COLUMNS else 0) for field in columns}
        results[name] = [row]
    results["03_overview"][0].update(facts["03_overview"])
    results["08_repeat"][0].update(facts["08_repeat"])
    results["04_trend"][0].update(year_month="2018-01", is_boundary_month=True)
    results["05_deliveries_reviews"][0].update(
        customer_state="SP", is_on_time=True, mean_review_score="4.25", review_coverage="1"
    )
    results["06_segments"][0].update(
        category="books",
        seller_id="s1",
        seller_state="SP",
        delivered_segment_item_value_brl="100.00",
        item_value_share="0.5",
    )
    results["07_reconciliation"] = [
        {
            "order_status": "delivered",
            "reconciliation_status": status,
            "orders": count,
            "expected_brl": "110.00",
            "paid_brl": "110.00",
            "delta_brl": "0.00",
        }
        for status, count in facts["reconciliation"].items()
    ]
    results["run_metadata"] = [metadata]
    result = {
        key: metadata[key]
        for key in (
            "data_mode",
            "source_version",
            "source_manifest_sha256",
            "observation_end",
            "observation_basis",
            "reconciliation_tolerance",
        )
    }
    result.update(
        parameters={"start": start, "end": end},
        results=results,
        queries=[
            {"path": f"sql/{name}.sql", "sha256": "b" * 64, "rows": len(results[name])}
            for name in CHECKER.QUERY_NAMES
        ],
    )
    return result


@pytest.mark.parametrize("mode", ["real", "synthetic"])
def test_complete_documents_and_known_business_facts_pass(mode):
    reference = document(mode)
    result = CHECKER.compare_analysis(copy.deepcopy(reference), reference)
    assert result["status"] == "PASS"
    assert result["known_facts"] == "PASS"
    assert result["compared_result_sets"] == 9
    assert result["compared_queries"] == 7


def test_ordering_timestamp_and_equivalent_decimal_scales_do_not_change_results():
    reference = document()
    second = copy.deepcopy(reference["results"]["06_segments"][0])
    second.update(category="toys", seller_id="s2", delivered_segment_item_value_brl="100.00")
    reference["results"]["06_segments"].append(second)
    reference["queries"][3]["rows"] = 2
    actual = copy.deepcopy(reference)
    actual["results"]["06_segments"].reverse()  # Equal-valued SQL tie may order differently.
    actual["queries"].reverse()
    actual["results"]["03_overview"][0]["delivered_gmv_brl"] = Decimal("340")
    actual["results"]["06_segments"][0]["delivered_segment_item_value_brl"] = "100.0000"
    actual["results"]["run_metadata"][0]["imported_at"] = "2026-10-09T12:00:00"
    before = copy.deepcopy(actual)
    assert CHECKER.compare_analysis(actual, reference)["status"] == "PASS"
    assert actual == before  # Comparator cannot rewrite its inputs.


@pytest.mark.parametrize(
    ("table", "field", "changed"),
    [
        ("03_overview", "delivered_aov_brl", "0.01"),
        ("04_trend", "is_boundary_month", False),
        ("05_deliveries_reviews", "mean_review_score", "4.250000000000000001"),
        ("06_segments", "delivered_segment_item_value_brl", "100.01"),
        ("07_reconciliation", "delta_brl", "-0.01"),
        ("08_repeat", "simultaneous_orders_excluded_as_repeat", 1),
        ("09_seller_delivery", "mean_review_score", None),
        ("quality_summary", "affected_rows", 1),
    ],
)
def test_each_sql_result_set_is_compared_exactly(table, field, changed):
    reference = document()
    actual = copy.deepcopy(reference)
    actual["results"][table][0][field] = changed
    result = CHECKER.compare_analysis(actual, reference)
    assert result["status"] == "FAIL"
    assert any(f"results.{table}" in failure for failure in result["mismatches"])


def test_null_and_zero_remain_different():
    reference = document()
    actual = copy.deepcopy(reference)
    reference["results"]["09_seller_delivery"][0]["mean_review_score"] = None
    actual["results"]["09_seller_delivery"][0]["mean_review_score"] = "0"
    assert CHECKER.compare_analysis(actual, reference)["status"] == "FAIL"


@pytest.mark.parametrize("change", ["source_hash", "query_hash", "dates", "basis", "extra"])
def test_provenance_parameters_and_extra_fields_cannot_be_ignored(change):
    reference = document()
    actual = copy.deepcopy(reference)
    if change == "source_hash":
        actual["source_manifest_sha256"] = "c" * 64
        actual["results"]["run_metadata"][0]["source_manifest_sha256"] = "c" * 64
    elif change == "query_hash":
        actual["queries"][0]["sha256"] = "c" * 64
    elif change == "dates":
        actual["parameters"]["end"] = "2018-06-03"
        actual["results"]["run_metadata"][0]["analysis_end_exclusive"] = "2018-06-03"
    elif change == "basis":
        actual["observation_basis"] = "A different assumption"
        actual["results"]["run_metadata"][0]["observation_basis"] = "A different assumption"
    else:
        actual["extra"] = "unexpected result"
    assert CHECKER.compare_analysis(actual, reference)["status"] == "FAIL"


def test_duplicate_rows_cannot_disappear_during_canonical_sorting():
    reference = document()
    actual = copy.deepcopy(reference)
    actual["results"]["06_segments"].append(copy.deepcopy(actual["results"]["06_segments"][0]))
    actual["queries"][3]["rows"] = 2
    assert CHECKER.compare_analysis(actual, reference)["status"] == "FAIL"


@pytest.mark.parametrize("kind", ["empty", "queries", "table", "column", "rows", "not_object"])
def test_empty_or_impoverished_documents_are_rejected(kind):
    reference = document()
    actual = copy.deepcopy(reference)
    if kind == "empty":
        actual = {}
    elif kind == "queries":
        actual["queries"] = []
    elif kind == "table":
        del actual["results"]["06_segments"]
    elif kind == "column":
        del actual["results"]["06_segments"][0]["item_value_share"]
    elif kind == "rows":
        actual["results"]["06_segments"] = []
        actual["queries"][3]["rows"] = 0
    else:
        actual = []
    assert CHECKER.compare_analysis(actual, reference)["status"] == "FAIL"


def test_two_identical_documents_cannot_pass_with_wrong_known_facts():
    reference = document()
    reference["results"]["03_overview"][0]["delivered_gmv_brl"] = "999"
    result = CHECKER.compare_analysis(copy.deepcopy(reference), reference)
    assert result["status"] == "FAIL"
    assert result["known_facts"] == "FAIL"


@pytest.mark.parametrize("value", [True, 340.0, "NaN", "Infinity"])
def test_inexact_and_nonfinite_money_is_rejected(value):
    reference = document()
    actual = copy.deepcopy(reference)
    actual["results"]["03_overview"][0]["delivered_gmv_brl"] = value
    assert CHECKER.compare_analysis(actual, reference)["status"] == "FAIL"


def test_cli_mode_mismatch_writes_failure_and_returns_nonzero(tmp_path):
    source = tmp_path / "analysis.json"
    source.write_text(json.dumps(document()), encoding="utf-8")
    result_path = tmp_path / "comparison.json"
    code = CHECKER.main(
        [
            "--mode",
            "real",
            "--actual",
            str(source),
            "--reference",
            str(source),
            "--output",
            str(result_path),
        ]
    )
    assert code == 1
    assert json.loads(result_path.read_text())["status"] == "FAIL"


def test_capture_refuses_to_overwrite_previous_results(tmp_path):
    old = tmp_path / "previous.json"
    old.write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        CHECKER.capture_portable(tmp_path)
    assert old.read_text() == "preserve me"


def test_capture_flags_cannot_change_the_portable_connection(tmp_path):
    with pytest.raises(SystemExit) as caught:
        CHECKER.main(["--capture-portable", "--mode", "real", "--output", str(tmp_path)])
    assert caught.value.code == 2

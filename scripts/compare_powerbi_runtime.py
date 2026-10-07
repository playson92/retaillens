"""Compare every required Desktop query with independent SQL, including import proofs."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

NUMERIC_LITERAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
DATE_FIELDS = {"analysis_start", "analysis_end_exclusive", "observation_end"}
AVERAGES = {"Delivered AOV", "Segment Item Value Per Order", "AOV_BRL", "Segment_Value_Per_Order"}
EXACT_MONEY = {
    "Delivered GMV",
    "Delivered Segment Item Value",
    "Expected Amount BRL",
    "Paid Amount BRL",
    "Payment Delta BRL",
    "GMV_BRL",
    "Segment_Value",
    "Seller_Item_Value",
    "reconciliation_tolerance",
}


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    return {key.split("[")[-1].rstrip("]"): value for key, value in row.items()}


def equal(name: str, actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if name in DATE_FIELDS:
        try:
            observed = datetime.fromisoformat(str(actual))
            wanted = datetime.fromisoformat(str(expected))
            return observed.date() == wanted.date() and observed.time() == time(0)
        except ValueError:
            return False
    if name == "imported_at":
        # Power BI DateTime stores multiples of 1/300 second. This allowance
        # does not relax monetary, date or source identity comparisons.
        # https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types
        try:
            delta = datetime.fromisoformat(str(actual)) - datetime.fromisoformat(str(expected))
            return abs(Decimal(str(delta.total_seconds()))) <= Decimal(1) / Decimal(300)
        except (ValueError, TypeError):
            return False
    if isinstance(expected, (int, float)) or (
        isinstance(expected, str) and NUMERIC_LITERAL.fullmatch(expected)
    ):
        if isinstance(actual, bool):
            return False
        try:
            a, e = Decimal(str(actual)), Decimal(str(expected))
            if not a.is_finite() or not e.is_finite():
                return False
            if isinstance(expected, int):
                return a == e
            if name in AVERAGES:
                return abs(a - e) <= Decimal("0.00005") and a.quantize(
                    Decimal("0.01")
                ) == e.quantize(Decimal("0.01"))
            if name in EXACT_MONEY:
                return a == e
            return abs(a - e) <= Decimal("1e-10")
        except (InvalidOperation, ValueError):
            return False
    return actual == expected


def required_queries(expected: dict[str, Any], proofs: dict[str, Any]) -> dict[str, Any]:
    required = {"case:" + name: [case["measures"]] for name, case in expected["cases"].items()}
    if not required:
        raise ValueError("At least one independently expected case is required")
    required.update(
        {
            "supplied:" + name: rows
            for name, rows in expected["supplied_evaluate_queries"].items()
            if name != "2_suppressed_all_blank_groups"
        }
    )
    for name in ("import_counts", "run_metadata"):
        required["proof:" + name] = proofs["proofs"][name]
    for name, edge in proofs["edges"].items():
        required["edge:" + name] = edge["rows"]
    return required


def compare(mode: str, expected: dict[str, Any], actual: dict[str, Any], proofs: dict[str, Any]):
    required = required_queries(expected, proofs)
    results = actual.get("results", [])
    mismatches = []
    comparisons = 0
    ids = Counter(result.get("id") for result in results)
    for name in sorted(required.keys() - ids.keys()):
        mismatches.append({"query": name, "error": "Required query missing"})
    for name in sorted(ids.keys() - required.keys(), key=str):
        mismatches.append({"query": name, "error": "Unknown query ID"})
    for name, count in ids.items():
        if count != 1:
            mismatches.append({"query": name, "error": "Duplicate query ID", "count": count})
    if mode == "synthetic" and "edge:seller_s2_zero_numerator" not in required:
        mismatches.append(
            {
                "query": "edge:seller_s2_zero_numerator",
                "error": "Independent edge expectation missing",
            }
        )
    for result in results:
        query_id = result.get("id")
        if result.get("status") != "PASS_EXECUTED":
            mismatches.append(
                {
                    "query": query_id,
                    "error": result.get("error") or "Query did not execute successfully",
                }
            )
            continue
        if query_id not in required:
            continue
        observed = [normalize(row) for row in result["rows"]]
        wanted = [normalize(row) for row in required[query_id]]
        if query_id == "supplied:2_delivery_review_groups":
            observed.sort(key=lambda row: str(row.get("is_on_time")))
            wanted.sort(key=lambda row: str(row.get("is_on_time")))
        if len(observed) != len(wanted):
            mismatches.append(
                {"query": query_id, "actual_rows": len(observed), "expected_rows": len(wanted)}
            )
            continue
        for a, e in zip(observed, wanted, strict=True):
            for field, value in e.items():
                comparisons += 1
                if field not in a or not equal(field, a.get(field), value):
                    mismatches.append(
                        {
                            "query": query_id,
                            "field": field,
                            "actual": a.get(field),
                            "expected": value,
                        }
                    )
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "mode": mode,
        "engine": actual.get("server"),
        "catalog": actual.get("catalog"),
        "required_queries": len(required),
        "executed_queries": len(results),
        "query_ids": list(required),
        "comparisons": comparisons,
        "blank_comparison": "strict; null is never treated as numeric zero",
        "money_comparison": "sums exact; currency-derived averages within 0.00005 and identical cents",
        "other_numeric_absolute_tolerance": "1e-10",
        "imported_at_precision_seconds": "1/300; documented Power BI DateTime storage precision",
        "mismatches": mismatches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("real", "synthetic"), required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--proofs", type=Path, help="Independent SQL import/metadata/edge evidence")
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))["modes"][args.mode]
    proof_file = args.proofs or args.expected.with_name("runtime_sql_proofs.json")
    proofs = json.loads(proof_file.read_text(encoding="utf-8"))["modes"][args.mode]
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    report = compare(args.mode, expected, actual, proofs)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(report["status"] != "PASS")


if __name__ == "__main__":
    main()

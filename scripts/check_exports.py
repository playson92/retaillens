"""Reconcile actual CSV exports with SQL evidence and independent mart aggregates."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from retaillens.source import sha256, write_json


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    return str(value)


def check(directory):
    evidence = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
    files = {}
    query_counts = {Path(query["path"]).stem: query["rows"] for query in evidence["queries"]}
    for name, result_rows in evidence["results"].items():
        path = directory / f"{name}.csv"
        expected = [{key: csv_value(value) for key, value in row.items()} for row in result_rows]
        actual = rows(path)
        assert actual == expected, f"CSV/SQL JSON mismatch: {name}"
        if name in query_counts:
            assert len(actual) == query_counts[name], f"Row count mismatch: {name}"
        files[path.name] = {"rows": len(actual), "sha256": sha256(path)}

    orders = rows(directory / "marts/mart_orders.csv")
    items = rows(directory / "marts/mart_items.csv")
    cohorts = rows(directory / "marts/mart_cohorts.csv")
    assert len({row["order_id"] for row in orders}) == len(orders)
    assert len({(row["order_id"], row["order_item_id"]) for row in items}) == len(items)
    assert len({row["customer_unique_id"] for row in cohorts}) == len(cohorts)
    start, end = evidence["parameters"]["start"], evidence["parameters"]["end"]
    assert start < end
    orders = [row for row in orders if start <= row["purchase_date"] < end]
    items = [row for row in items if start <= row["purchase_date"] < end]
    cohorts = [row for row in cohorts if start <= row["first_purchase_date"] < end]
    eligible = [row for row in orders if row["gmv_eligible"] == "t"]
    gmv = sum((Decimal(row["item_value"]) for row in eligible), Decimal(0))
    item_gmv = sum(
        (Decimal(row["price"]) for row in items if row["gmv_eligible"] == "t"), Decimal(0)
    )
    overview = evidence["results"]["03_overview"][0]
    repeat = evidence["results"]["08_repeat"][0]
    assert len(orders) == overview["orders"]
    assert gmv == item_gmv
    assert (gmv if eligible else None) == (
        Decimal(overview["delivered_gmv_brl"])
        if overview["delivered_gmv_brl"] is not None
        else None
    )
    assert len(eligible) == overview["delivered_orders"]
    assert (
        sum(row["delivery_eligible"] == "t" for row in orders)
        == overview["delivery_eligible_orders"]
    )
    assert (
        sum(row["delivery_eligible"] == "t" and row["is_on_time"] == "t" for row in orders)
        == overview["on_time_orders"]
    )
    assert (
        sum(
            row["order_status"] == "delivered" and row["delivery_eligible"] != "t" for row in orders
        )
        == overview["delivered_delivery_exclusions"]
    )
    assert len(cohorts) == repeat["first_observed_people"]
    assert sum(row["eligible_90d"] == "t" for row in cohorts) == repeat["eligible_people"]
    assert (
        sum(row["eligible_90d"] == "t" and row["repeated_90d"] == "t" for row in cohorts)
        == repeat["repeat_people"]
    )
    statuses = Counter(
        row["reconciliation_status"] for row in orders if row["order_status"] == "delivered"
    )
    reconciliation = defaultdict(list)
    for row in orders:
        reconciliation[(row["order_status"], row["reconciliation_status"])].append(row)
    expected_groups = {
        (row["order_status"], row["reconciliation_status"]): row
        for row in evidence["results"]["07_reconciliation"]
    }
    assert reconciliation.keys() == expected_groups.keys(), "Reconciliation groups differ"
    for group, group_rows in reconciliation.items():
        expected = expected_groups[group]
        assert len(group_rows) == expected["orders"], f"Reconciliation count differs: {group}"
        for field, metric in (
            ("expected_amount", "expected_brl"),
            ("paid_amount", "paid_brl"),
            ("payment_delta", "delta_brl"),
        ):
            values = [Decimal(row[field]) for row in group_rows if row[field]]
            actual = sum(values, Decimal(0)) if values else None
            sql_value = Decimal(expected[metric]) if expected[metric] is not None else None
            assert actual == sql_value, f"Reconciliation sum differs: {group}/{metric}"
    for name in ("mart_orders", "mart_items", "mart_cohorts"):
        path = directory / "marts" / f"{name}.csv"
        files[f"marts/{path.name}"] = {"sha256": sha256(path)}
    return {
        "status": "PASS",
        "mode": evidence["data_mode"],
        "source_manifest_sha256": evidence["source_manifest_sha256"],
        "observation_end": evidence["observation_end"],
        "parameters": evidence["parameters"],
        "checks": "All analytical CSV rows equal SQL JSON; unique full mart grains; selected-window order/item GMV, delivery/cohort counts and reconciliation group counts/Decimal sums independently agree",
        "gmv_brl": str(gmv) if eligible else None,
        "delivered_reconciliation": dict(statuses),
        "files": files,
    }


def main():
    cli = argparse.ArgumentParser()
    targets = cli.add_mutually_exclusive_group(required=True)
    targets.add_argument(
        "--evidence", type=Path, help="Root containing real and synthetic evidence"
    )
    targets.add_argument("--directory", type=Path, help="One analysis directory containing marts")
    args = cli.parse_args()
    directories = (
        [args.directory]
        if args.directory
        else [args.evidence / mode for mode in ("real", "synthetic")]
    )
    for directory in directories:
        result = check(directory)
        write_json(directory / "export_check.json", result)
        print(json.dumps({key: result[key] for key in ("status", "mode", "gmv_brl")}))


if __name__ == "__main__":
    main()

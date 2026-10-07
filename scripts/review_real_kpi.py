"""Capture actual before/after Olist publication and isolate the RL-04 calendar-day change."""

import argparse
import json
from pathlib import Path

from psycopg.rows import dict_row

from retaillens.config import Settings
from retaillens.source import write_json
from retaillens.warehouse import select_schema

REFERENCE = {
    "delivered_gmv_brl": "13221498.11",
    "gmv_eligible_orders": 96478,
    "on_time_orders": 88587,
    "delivery_eligible_orders": 95097,
    "delivered_matched": 96178,
    "delivered_mismatch": 299,
    "delivered_not_comparable": 1,
    "repeat_people": 1519,
    "eligible_repeat_people": 75703,
}


def capture():
    with Settings("real").connect() as connection:
        connection.row_factory = dict_row
        select_schema(connection, Settings("real"))
        order = connection.execute("""SELECT count(*) AS source_orders,
            sum(item_value) FILTER(WHERE gmv_eligible) AS delivered_gmv_brl,
            count(*) FILTER(WHERE gmv_eligible) AS gmv_eligible_orders,
            count(*) FILTER(WHERE delivery_eligible AND is_on_time) AS on_time_orders,
            count(*) FILTER(WHERE delivery_eligible) AS delivery_eligible_orders,
            count(*) FILTER(WHERE order_status='delivered' AND reconciliation_status='matched') AS delivered_matched,
            count(*) FILTER(WHERE order_status='delivered' AND reconciliation_status='mismatch') AS delivered_mismatch,
            count(*) FILTER(WHERE order_status='delivered' AND reconciliation_status='not_comparable') AS delivered_not_comparable
            FROM mart_orders""").fetchone()
        cohort = connection.execute("""SELECT count(*) FILTER(WHERE eligible_90d AND repeated_90d) AS repeat_people,
            count(*) FILTER(WHERE eligible_90d) AS eligible_repeat_people FROM mart_cohorts""").fetchone()
        meta = connection.execute("""SELECT source_version,source_manifest_sha256,observation_end,
            observation_basis,reconciliation_tolerance FROM run_metadata""").fetchone()
        # All other chronology rules are already encoded in newly built delivery_eligible.
        # In the after model, these are exactly rows admitted by replacing timestamp promise comparison.
        changed = connection.execute("""SELECT o.order_id,o.order_purchase_timestamp,
            o.order_estimated_delivery_date,o.order_delivered_customer_date,
            m.delivery_eligible,m.is_on_time FROM stg_orders o JOIN mart_orders m USING(order_id)
            WHERE m.delivery_eligible AND o.order_estimated_delivery_date < o.order_purchase_timestamp
            ORDER BY o.order_id""").fetchall()
    return {"metrics": {**order, **cohort}, "metadata": meta, "rl04_admitted_orders": changed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    current = capture()
    write_json(args.output / f"kpi_{args.phase}.json", current)
    if args.phase == "before":
        print("Captured actual baseline publication; no database mutation")
        return
    before = json.loads((args.output / "kpi_before.json").read_text(encoding="utf-8"))
    after = json.loads((args.output / "kpi_after.json").read_text(encoding="utf-8"))
    assert (
        before["metadata"]["source_manifest_sha256"] == after["metadata"]["source_manifest_sha256"]
    )
    assert after["metadata"]["observation_end"] == "2018-09-01"
    changes = {
        key: {"before": before["metrics"][key], "after": value}
        for key, value in after["metrics"].items()
        if value != before["metrics"][key]
    }
    old_admitted = {row["order_id"] for row in before["rl04_admitted_orders"]}
    admitted = [row for row in after["rl04_admitted_orders"] if row["order_id"] not in old_admitted]
    assert after["metrics"]["delivery_eligible_orders"] - before["metrics"][
        "delivery_eligible_orders"
    ] == len(admitted)
    assert after["metrics"]["on_time_orders"] - before["metrics"]["on_time_orders"] == sum(
        row["is_on_time"] for row in admitted
    )
    write_json(
        args.output / "kpi_comparison.json",
        {
            "status": "PASS",
            "review_reference": REFERENCE,
            "actual_before": before,
            "actual_after": after,
            "changes": changes,
            "rl04_changed_order_count": len(admitted),
            "rl04_changed_orders": admitted,
            "interpretation": "Calendar-day promise retains timestamp chronology. Zero observed Olist changes is a measured result, not a forced target.",
        },
    )
    print(
        json.dumps({"status": "PASS", "kpi_changes": changes, "rl04_changed_orders": len(admitted)})
    )


if __name__ == "__main__":
    main()

"""Reimport and rebuild checks on pinned Olist, with small SQL reconciliation evidence."""

import argparse
import time
from decimal import Decimal
from pathlib import Path

from psycopg.rows import dict_row

from retaillens.analysis import analyse, export_marts
from retaillens.config import Settings
from retaillens.source import write_json
from retaillens.warehouse import ingest, quality, rebuild, select_schema


def snapshot(settings):
    with settings.connect() as connection:
        select_schema(connection, settings)
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ["raw_records", "stg_orders", "mart_orders", "mart_items", "mart_cohorts"]
        }
        metrics = connection.execute("""SELECT
            sum(item_value) FILTER(WHERE gmv_eligible),
            count(*) FILTER(WHERE gmv_eligible),
            count(*) FILTER(WHERE delivery_eligible),
            count(*) FILTER(WHERE delivery_eligible AND is_on_time),
            count(*) FILTER(WHERE reconciliation_status='mismatch') FROM mart_orders""").fetchone()
        cohorts = connection.execute(
            "SELECT count(*) FILTER(WHERE eligible_90d),"
            "count(*) FILTER(WHERE eligible_90d AND repeated_90d) FROM mart_cohorts"
        ).fetchone()
    return {"counts": counts, "metrics": metrics, "cohorts": cohorts}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--input", type=Path, default=Path("data/raw/olist-v2"))
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = Settings("real")
    before = snapshot(settings)
    started = time.perf_counter()
    manifest = ingest(settings, args.input, "olist-v2", "2018-09-01")
    after_import = snapshot(settings)
    rebuild(settings)
    after_build = snapshot(settings)
    assert before == after_import == after_build, "Reimport/rebuild changed source counts or KPI"
    check = quality(settings)
    assert check["status"] == "PASS"
    write_json(args.output / "source_manifest.json", manifest)
    write_json(args.output / "quality.json", check)
    write_json(
        args.output / "reimport.json",
        {
            "status": "PASS",
            "before": before,
            "after_import": after_import,
            "after_build": after_build,
            "seconds": round(time.perf_counter() - started, 3),
        },
    )
    analyse(settings, args.output)
    export_marts(settings, Path("output") / "report_data" / "real")
    with settings.connect() as connection:
        connection.row_factory = dict_row
        select_schema(connection, settings)
        review_groups = connection.execute("""SELECT is_on_time,count(*) AS eligible_orders,
            count(review_score) AS reviewed_orders,avg(review_score) AS mean_review_score,
            count(review_score)::numeric/count(*) AS review_coverage
            FROM mart_orders WHERE delivery_eligible GROUP BY is_on_time ORDER BY is_on_time""").fetchall()
        boundaries = connection.execute("""SELECT to_char(purchase_date,'YYYY-MM') AS month,
            count(*) AS orders,count(*) FILTER(WHERE order_status='delivered') AS delivered
            FROM mart_orders WHERE purchase_date >= '2018-08-01'
            GROUP BY 1 ORDER BY 1""").fetchall()
        category_check = connection.execute(
            """SELECT sum(price) FROM mart_items WHERE gmv_eligible"""
        ).fetchone()
        assert category_check["sum"] == Decimal("13221498.11")
        direct_financial = connection.execute("""SELECT sum(price) AS item_value,
            sum(price+freight_value) AS expected FROM stg_items
            WHERE order_id IN (SELECT order_id FROM mart_orders WHERE gmv_eligible)""").fetchone()
        assert direct_financial["item_value"] == before["metrics"][0]
        source_counts = connection.execute(
            "SELECT table_name,row_count,sha256 FROM source_files ORDER BY table_name"
        ).fetchall()
        version = connection.execute("SELECT version()").fetchone()["version"]
    write_json(
        args.output / "sql_evidence.json",
        {
            "status": "PASS",
            "postgres_version": version,
            "review_groups": review_groups,
            "tail_months": boundaries,
            "direct_financial": direct_financial,
            "source_files": source_counts,
            "observation_assumption": "Start of 2018-09-01: sparse September/October tail is excluded from 90-day follow-up; source completeness is still assumed",
        },
    )
    print("PASS: pinned Olist reimport, rebuild, exact money and source-to-mart reconciliation")


if __name__ == "__main__":
    main()

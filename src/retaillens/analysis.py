"""Execute versioned SQL, export answers and preserve the exact analytical window."""

import csv
from datetime import date
from pathlib import Path

from psycopg.rows import dict_row

from retaillens.source import sha256, write_json
from retaillens.warehouse import select_schema, sql_dir


def write_csv(path, rows, columns):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def analyse(settings, output, start=None, end=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with settings.connect() as connection:
        connection.row_factory = dict_row
        select_schema(connection, settings)
        metadata = connection.execute("SELECT * FROM run_metadata").fetchone()
        params = {
            "start": date.fromisoformat(start) if start else metadata["analysis_start"],
            "end": date.fromisoformat(end) if end else metadata["analysis_end_exclusive"],
        }
        if params["start"] >= params["end"]:
            raise ValueError("Analysis start must precede exclusive end")
        results, queries = {}, []
        for path in sorted(sql_dir().glob("0[3-9]_*.sql")):
            cursor = connection.execute(path.read_text(encoding="utf-8"), params)
            rows = cursor.fetchall()
            columns = [d.name for d in cursor.description]
            results[path.stem] = rows
            write_csv(output / f"{path.stem}.csv", rows, columns)
            queries.append({"path": f"sql/{path.name}", "sha256": sha256(path), "rows": len(rows)})
        for table in ["quality_summary", "run_metadata"]:
            columns = (
                "*"
                if table != "run_metadata"
                else (
                    "data_mode,source_version,source_manifest_sha256,analysis_start,"
                    "analysis_end_exclusive,observation_end,observation_basis,"
                    "imported_at,reconciliation_tolerance"
                )
            )
            cursor = connection.execute(f"SELECT {columns} FROM {table}")
            rows = cursor.fetchall()
            results[table] = rows
            write_csv(output / f"{table}.csv", rows, [d.name for d in cursor.description])
        cursor = connection.execute("""SELECT order_id,order_status,reconciliation_status,
            expected_amount,paid_amount,payment_delta FROM mart_orders
            WHERE reconciliation_status<>'matched' ORDER BY order_id""")
        write_csv(
            output / "reconciliation_diagnostics.csv",
            cursor.fetchall(),
            [d.name for d in cursor.description],
        )
    evidence = {
        "data_mode": settings.mode,
        "source_version": metadata["source_version"],
        "source_manifest_sha256": metadata["source_manifest_sha256"],
        "parameters": params,
        "observation_end": metadata["observation_end"],
        "observation_basis": metadata["observation_basis"],
        "reconciliation_tolerance": metadata["reconciliation_tolerance"],
        "queries": queries,
        "results": results,
    }
    write_json(output / "analysis.json", evidence)
    return evidence


def export_marts(settings, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with settings.connect() as connection:
        select_schema(connection, settings)
        for table in [
            "mart_orders",
            "mart_items",
            "mart_cohorts",
            "dim_date",
            "dim_product",
            "dim_seller",
            "quality_summary",
        ]:
            with (output / f"{table}.csv").open("wb") as stream:
                with connection.cursor().copy(
                    f"COPY (SELECT * FROM {table}) TO STDOUT WITH (FORMAT CSV, HEADER true)"
                ) as copy:
                    for data in copy:
                        stream.write(data)
    return {"data_mode": settings.mode, "output": str(output)}

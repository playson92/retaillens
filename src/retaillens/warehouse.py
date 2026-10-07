"""Transactional, lineage-preserving PostgreSQL ingestion and atomic model publication."""

import json
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from psycopg import sql
from psycopg.types.json import Jsonb

from retaillens.config import ROOT
from retaillens.source import KEYS, SCHEMAS, parse_row, profile, read_rows, sha256


def sql_dir():
    local = ROOT / "sql"
    return local if local.exists() else Path(sys.prefix) / "share" / "retaillens" / "sql"


def select_schema(connection, settings):
    connection.execute(
        sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(settings.schema))
    )


def build(connection):
    connection.execute((sql_dir() / "02_marts.sql").read_text(encoding="utf-8"))


def init_tables(connection, settings):
    connection.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(settings.schema))
    )
    select_schema(connection, settings)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS raw_records (
            table_name text, file_sha256 text, source_row_number bigint, payload jsonb NOT NULL,
            PRIMARY KEY(table_name,file_sha256,source_row_number));
        CREATE TABLE IF NOT EXISTS import_issues (
            table_name text, file_sha256 text, source_row_number bigint, issue text,
            severity text, order_id text,
            PRIMARY KEY(table_name,file_sha256,source_row_number,issue));
        CREATE TABLE IF NOT EXISTS source_files (
            table_name text PRIMARY KEY, filename text, sha256 text, row_count bigint);
        CREATE TABLE IF NOT EXISTS run_metadata (
            data_mode text, source_version text, source_manifest_sha256 text,
            analysis_start date, analysis_end_exclusive date, observation_end date,
            observation_basis text, imported_at timestamp, reconciliation_tolerance numeric,
            source_manifest jsonb);
    """)
    for table, fields in SCHEMAS.items():
        columns = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(field), sql.SQL(kind))
            for field, kind in fields.items()
        )
        connection.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} ({}, file_sha256 text, source_row_number bigint)"
            ).format(sql.Identifier(f"stg_{table}"), columns)
        )
    connection.execute(
        "ALTER TABLE run_metadata ALTER COLUMN reconciliation_tolerance TYPE numeric"
    )
    # Explicit table ownership; never DROP SCHEMA or touch unrelated tables/volumes.
    owned = ["raw_records", "import_issues", "source_files", "run_metadata"] + [
        f"stg_{t}" for t in SCHEMAS
    ]
    connection.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(",").join(map(sql.Identifier, owned))))


def prepare_rows(table, path, checksum):
    accepted, issues, raw = [], [], []
    groups = {}
    for number, original in read_rows(path, table):
        raw.append((table, checksum, number, Jsonb(original)))
        parsed, errors = parse_row(table, original)
        for error in errors:
            issues.append((table, checksum, number, error, "WARNING", original.get("order_id")))
        required = KEYS.get(table, ("order_id",))
        key = tuple(parsed[k] for k in required)
        if any(v is None for v in key):
            issues.append(
                (
                    table,
                    checksum,
                    number,
                    "missing_or_invalid_key",
                    "REJECTED",
                    original.get("order_id"),
                )
            )
            continue
        row = tuple(parsed.values()) + (checksum, number)
        if table == "reviews":
            accepted.append(row)  # review_id/order_id is deliberately NOT a unique key.
        else:
            groups.setdefault(key, []).append(row)
    for candidates in groups.values():
        if len({row[:-2] for row in candidates}) > 1:
            for row in candidates:
                order_id = (
                    row[list(SCHEMAS[table]).index("order_id")]
                    if "order_id" in SCHEMAS[table]
                    else None
                )
                issues.append((table, checksum, row[-1], "conflicting_key", "REJECTED", order_id))
        else:
            accepted.append(candidates[0])
            for row in candidates[1:]:
                order_id = row[0] if "order_id" in SCHEMAS[table] else None
                issues.append(
                    (table, checksum, row[-1], "identical_duplicate", "DEDUPLICATED", order_id)
                )
    return raw, accepted, issues


def copy_rows(connection, table, rows):
    with connection.cursor().copy(
        sql.SQL("COPY {} FROM STDIN").format(sql.Identifier(table))
    ) as copy:
        for row in rows:
            copy.write_row(row)


def orphan_issues(connection):
    for child, field, parent, parent_field in [
        ("items", "order_id", "orders", "order_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
        ("orders", "customer_id", "customers", "customer_id"),
        ("items", "product_id", "products", "product_id"),
        ("items", "seller_id", "sellers", "seller_id"),
    ]:
        query = sql.SQL("""INSERT INTO import_issues
            SELECT %s,c.file_sha256,c.source_row_number,%s,'WARNING',c.order_id
            FROM {} c LEFT JOIN {} p ON c.{}=p.{}
            WHERE p.{} IS NULL ON CONFLICT DO NOTHING""").format(
            sql.Identifier(f"stg_{child}"),
            sql.Identifier(f"stg_{parent}"),
            sql.Identifier(field),
            sql.Identifier(parent_field),
            sql.Identifier(parent_field),
        )
        connection.execute(query, (child, f"orphan_{field}"))


def ingest(settings, directory, version, observation_end=None):
    directory = Path(directory)
    source_path = directory / "SOURCE.json"
    source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
    if source.get("data_mode") != settings.mode or source.get("source_version") != version:
        raise ValueError("SOURCE.json mode/version must match the explicitly selected import")
    if settings.mode == "real" and source.get("official_url") != (
        "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
    ):
        raise ValueError("Real inputs require official Olist provenance in SOURCE.json")
    manifest = profile(directory, settings.mode, version)
    if settings.mode == "real":
        for info in manifest["files"]:
            if source.get("file_sha256", {}).get(info["filename"]) != info["sha256"]:
                raise ValueError(
                    f"Real input does not match pinned SOURCE.json checksum: {info['filename']}"
                )
    manifest["source"] = source
    order_file = next(f for f in manifest["files"] if f["table"] == "orders")
    if not order_file["date_min"]:
        raise ValueError("No valid purchase dates in input")
    start = datetime.fromisoformat(order_file["date_min"]).date()
    last = datetime.fromisoformat(order_file["date_max"]).date()
    observation = date.fromisoformat(observation_end) if observation_end else last
    if observation < start or observation > last + timedelta(days=1):
        raise ValueError("Observation boundary must be inside the declared source date range")
    basis = (
        "Explicit user-supplied historical observation boundary; completeness assumed"
        if observation_end
        else "Assumed observation through start of maximum valid source purchase day; "
        "maximum timestamp is not evidence of complete coverage"
    )
    started = datetime.now(UTC)
    # Audit history survives a rejected import; publication remains one transaction.
    with settings.connect() as audit:
        audit.execute("CREATE SCHEMA IF NOT EXISTS rl_audit")
        audit.execute("""CREATE TABLE IF NOT EXISTS rl_audit.ingestion_runs (
            run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            data_mode text, source_version text, manifest_sha256 text, started_at timestamptz,
            finished_at timestamptz, status text, error_type text)""")
        run_id = audit.execute(
            """INSERT INTO rl_audit.ingestion_runs
            (data_mode,source_version,manifest_sha256,started_at,status)
            VALUES(%s,%s,%s,%s,'RUNNING') RETURNING run_id""",
            (settings.mode, version, manifest["source_manifest_sha256"], started),
        ).fetchone()[0]
    try:
        with settings.connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (settings.schema,))
            init_tables(connection, settings)
            for info in manifest["files"]:
                table = info["table"]
                connection.execute(
                    "INSERT INTO source_files VALUES (%s,%s,%s,%s)",
                    (table, info["filename"], info["sha256"], info["rows"]),
                )
                if table not in SCHEMAS:
                    continue
                raw, accepted, issues = prepare_rows(
                    table, directory / info["filename"], info["sha256"]
                )
                if (
                    len(raw) != info["rows"]
                    or sha256(directory / info["filename"]) != info["sha256"]
                ):
                    raise ValueError(f"Input changed during import: {info['filename']}")
                copy_rows(connection, "raw_records", raw)
                copy_rows(connection, f"stg_{table}", accepted)
                copy_rows(connection, "import_issues", issues)
            orphan_issues(connection)
            connection.execute(
                "INSERT INTO run_metadata VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    settings.mode,
                    version,
                    manifest["source_manifest_sha256"],
                    start,
                    last + timedelta(days=1),
                    observation,
                    basis,
                    started.replace(tzinfo=None),
                    settings.tolerance,
                    Jsonb(manifest),
                ),
            )
            build(connection)
            finalized = connection.execute(
                """UPDATE rl_audit.ingestion_runs SET status='SUCCESS',finished_at=clock_timestamp()
                WHERE run_id=%s AND status='RUNNING'""",
                (run_id,),
            )
            if finalized.rowcount != 1:
                raise RuntimeError("Audit finalization did not update the RUNNING attempt")
    except Exception as exc:
        try:
            with settings.connect() as audit:
                audit.execute(
                    """UPDATE rl_audit.ingestion_runs SET status='FAILED',finished_at=clock_timestamp(),
                    error_type=%s WHERE run_id=%s AND status='RUNNING'""",
                    (type(exc).__name__, run_id),
                )
        except Exception as audit_error:
            logging.getLogger(__name__).warning(
                "FAILED audit update unavailable for run %s (%s); preserving original %s",
                run_id,
                type(audit_error).__name__,
                type(exc).__name__,
            )
        raise
    return manifest


def rebuild(settings):
    with settings.connect() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (settings.schema,))
        select_schema(connection, settings)
        connection.execute(
            "UPDATE run_metadata SET reconciliation_tolerance=%s", (settings.tolerance,)
        )
        build(connection)


def quality(settings):
    with settings.connect() as connection:
        select_schema(connection, settings)
        checks = {
            "order_grain": "SELECT count(*)=count(DISTINCT order_id) FROM mart_orders",
            "item_grain": "SELECT count(*)=count(DISTINCT (order_id,order_item_id)) FROM mart_items",
            "gmv_complete": "SELECT NOT EXISTS(SELECT 1 FROM mart_orders WHERE gmv_eligible AND "
            "(item_value IS NULL OR missing_price_count>0 OR item_count=0))",
            "reconciliation_complete": "SELECT NOT EXISTS(SELECT 1 FROM mart_orders WHERE "
            "reconciliation_status<>'not_comparable' AND "
            "(expected_amount IS NULL OR paid_amount IS NULL))",
            "date_coverage": "SELECT NOT EXISTS(SELECT 1 FROM mart_orders o LEFT JOIN dim_date d "
            "ON o.purchase_date=d.date WHERE o.purchase_date IS NOT NULL AND d.date IS NULL)",
            "review_ambiguity": "SELECT NOT EXISTS(SELECT 1 FROM mart_orders WHERE "
            "review_ambiguous AND review_score IS NOT NULL)",
        }
        results = {
            name: bool(connection.execute(query).fetchone()[0]) for name, query in checks.items()
        }
        return {
            "data_mode": settings.mode,
            "status": "PASS" if all(results.values()) else "FAIL",
            "checks": results,
        }

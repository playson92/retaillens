"""Compare complete Docker demo SQL evidence with fresh read-only Portable evidence."""

import argparse
import copy
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from retaillens.analysis import analyse
from retaillens.config import Settings, resolve_connection
from retaillens.source import sha256, write_json
from retaillens.warehouse import select_schema

COLUMNS = {
    "03_overview": "orders delivered_orders delivered_gmv_brl delivered_aov_brl "
    "delivery_eligible_orders on_time_orders on_time_rate delivered_delivery_exclusions",
    "04_trend": "year_month is_boundary_month source_orders delivered_orders "
    "delivered_gmv_brl delivered_aov_brl",
    "05_deliveries_reviews": "customer_state is_on_time eligible_orders mean_delay_days "
    "reviewed_orders review_coverage mean_review_score score_1 score_2 score_3 score_4 score_5 "
    "ambiguous_reviews",
    "06_segments": "category seller_id seller_state segment_orders "
    "delivered_segment_item_value_brl segment_item_value_per_order_brl item_value_share",
    "07_reconciliation": "order_status reconciliation_status orders expected_brl paid_brl delta_brl",
    "08_repeat": "first_observed_people eligible_people repeat_people incomplete_window_people "
    "observed_repeat_90d_rate simultaneous_orders_excluded_as_repeat",
    "09_seller_delivery": "seller_id eligible_orders on_time_rate reviewed_orders mean_review_score",
    "quality_summary": "check_name severity affected_rows details",
    "run_metadata": "data_mode source_version source_manifest_sha256 analysis_start "
    "analysis_end_exclusive observation_end observation_basis imported_at reconciliation_tolerance",
}
COLUMNS = {name: set(columns.split()) for name, columns in COLUMNS.items()}
TEXT_COLUMNS = {
    "year_month",
    "customer_state",
    "category",
    "seller_id",
    "seller_state",
    "order_status",
    "reconciliation_status",
    "check_name",
    "severity",
    "details",
    "data_mode",
    "source_version",
    "source_manifest_sha256",
    "analysis_start",
    "analysis_end_exclusive",
    "observation_end",
    "observation_basis",
    "imported_at",
    "is_boundary_month",
    "is_on_time",
}
QUERY_NAMES = tuple(name for name in COLUMNS if name[:2].isdigit())
COUNT_COLUMNS = {
    "orders",
    "delivered_orders",
    "delivery_eligible_orders",
    "on_time_orders",
    "delivered_delivery_exclusions",
    "source_orders",
    "eligible_orders",
    "reviewed_orders",
    "score_1",
    "score_2",
    "score_3",
    "score_4",
    "score_5",
    "ambiguous_reviews",
    "segment_orders",
    "first_observed_people",
    "eligible_people",
    "repeat_people",
    "incomplete_window_people",
    "simultaneous_orders_excluded_as_repeat",
    "affected_rows",
}
REQUIRED = {
    "data_mode",
    "source_version",
    "source_manifest_sha256",
    "parameters",
    "observation_end",
    "observation_basis",
    "reconciliation_tolerance",
    "queries",
    "results",
}
FACTS = {
    "synthetic": {
        "source_version": "fixture-v1",
        "observation_end": "2018-06-01",
        "03_overview": {
            "orders": 8,
            "delivered_orders": 6,
            "delivered_gmv_brl": "340.00",
            "delivery_eligible_orders": 5,
            "on_time_orders": 3,
        },
        "08_repeat": {"eligible_people": 4, "repeat_people": 1},
        "reconciliation": {"matched": 5, "mismatch": 1, "not_comparable": 1},
    },
    "real": {
        "source_version": "olist-v2",
        "observation_end": "2018-09-01",
        "03_overview": {
            "orders": 99441,
            "delivered_orders": 96478,
            "delivered_gmv_brl": "13221498.11",
            "delivery_eligible_orders": 95097,
            "on_time_orders": 88587,
        },
        "08_repeat": {"eligible_people": 75703, "repeat_people": 1519},
        "reconciliation": {"matched": 96178, "mismatch": 299, "not_comparable": 1},
    },
}


def numeric(value):
    """Never merge SQL NULL with zero, booleans with counts, or floats with Decimal."""
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Expected exact numeric value, not bool or binary float")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Invalid numeric value") from error
    if not result.is_finite():
        raise ValueError("Numeric value must be finite")
    return result


def canonical(value):
    if isinstance(value, dict):
        return ("object", tuple((key, canonical(item)) for key, item in sorted(value.items())))
    if isinstance(value, list):
        return ("multiset", tuple(sorted((canonical(item) for item in value), key=repr)))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, Decimal)):
        number = numeric(value)
        text = "0" if number == 0 else format(number, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return ("number", text)
    if isinstance(value, (date, datetime)):
        return ("string", value.isoformat())
    if value is None:
        return ("null",)
    if isinstance(value, str):
        return ("string", value)
    raise ValueError(f"Unsupported analysis value type: {type(value).__name__}")


def validate(document, label):
    errors = []
    if not isinstance(document, dict):
        return [f"{label}: analysis must be an object"]
    if missing := REQUIRED - document.keys():
        errors.append(f"{label}: missing analysis fields {sorted(missing)}")
    if errors:
        return errors
    mode = document["data_mode"]
    if not isinstance(mode, str) or mode not in FACTS:
        errors.append(f"{label}: invalid data mode")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", str(document["source_manifest_sha256"])):
        errors.append(f"{label}: missing or invalid source manifest SHA256")
    if not document["source_version"] or not document["observation_basis"]:
        errors.append(f"{label}: source version and observation basis are required")
    parameters = document["parameters"]
    if not isinstance(parameters, dict) or set(parameters) != {"start", "end"}:
        errors.append(f"{label}: parameters must contain start and exclusive end")
    else:
        try:
            if date.fromisoformat(str(parameters["start"])) >= date.fromisoformat(
                str(parameters["end"])
            ):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{label}: invalid analysis date interval")
    results = document["results"]
    if not isinstance(results, dict) or set(results) != set(COLUMNS):
        errors.append(f"{label}: all nine result sets are required")
        return errors
    for name, columns in COLUMNS.items():
        rows = results[name]
        if not isinstance(rows, list) or not rows:
            errors.append(
                f"{label}.results.{name}: nonempty rows are required for full-source demo"
            )
            continue
        if name in {"03_overview", "08_repeat", "run_metadata"} and len(rows) != 1:
            errors.append(f"{label}.results.{name}: exactly one summary row is required")
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != columns:
                errors.append(f"{label}.results.{name}[{index}]: incomplete or unexpected columns")
                continue
            for field in columns - TEXT_COLUMNS:
                try:
                    number = numeric(row[field])
                    if field in COUNT_COLUMNS and (
                        number is None or number < 0 or number != number.to_integral_value()
                    ):
                        raise ValueError("Count must be a nonnegative integer, including zero")
                except ValueError as error:
                    errors.append(f"{label}.results.{name}[{index}].{field}: {error}")
    queries = document["queries"]
    if not isinstance(queries, list) or len(queries) != len(QUERY_NAMES):
        errors.append(f"{label}: exactly seven query provenance records are required")
    else:
        seen = set()
        for query in queries:
            if not isinstance(query, dict) or set(query) != {"path", "sha256", "rows"}:
                errors.append(f"{label}: malformed query provenance")
                continue
            path = query["path"]
            name = Path(path).stem if isinstance(path, str) else ""
            if name not in QUERY_NAMES or path != f"sql/{name}.sql" or name in seen:
                errors.append(f"{label}: missing, unexpected or duplicate SQL query path")
            seen.add(name)
            if not re.fullmatch(r"[a-fA-F0-9]{64}", str(query["sha256"])):
                errors.append(f"{label}: invalid query SHA256")
            if (
                isinstance(query["rows"], bool)
                or not isinstance(query["rows"], int)
                or name in results
                and isinstance(results[name], list)
                and query["rows"] != len(results[name])
            ):
                errors.append(f"{label}: query row count differs from result rows")
    try:
        numeric(document["reconciliation_tolerance"])
        canonical(document)
    except ValueError as error:
        errors.append(f"{label}: {error}")
    return errors


def normalized(document):
    result = copy.deepcopy(document)
    result["reconciliation_tolerance"] = numeric(result["reconciliation_tolerance"])
    for name, rows in result["results"].items():
        for row in rows:
            for field in COLUMNS[name] - TEXT_COLUMNS:
                row[field] = numeric(row[field])
            if name == "run_metadata":
                row.pop("imported_at", None)
    return result


def known_fact_errors(document, label):
    mode = document["data_mode"]
    expected = FACTS[mode]
    errors = []
    for field in ("source_version", "observation_end"):
        if canonical(document[field]) != canonical(expected[field]):
            errors.append(f"{label}.{field}: differs from pinned {mode} demo")
    for name in ("03_overview", "08_repeat"):
        for field, value in expected[name].items():
            if numeric(document["results"][name][0][field]) != numeric(value):
                errors.append(f"{label}.results.{name}.{field}: differs from pinned {mode} demo")
    delivered = {
        row["reconciliation_status"]: numeric(row["orders"])
        for row in document["results"]["07_reconciliation"]
        if row["order_status"] == "delivered"
    }
    if delivered != {key: numeric(value) for key, value in expected["reconciliation"].items()}:
        errors.append(f"{label}.results.07_reconciliation: delivered populations differ")
    metadata = document["results"]["run_metadata"][0]
    for field in (
        "data_mode",
        "source_version",
        "source_manifest_sha256",
        "observation_end",
        "observation_basis",
        "reconciliation_tolerance",
    ):
        if canonical(metadata[field]) != canonical(document[field]):
            errors.append(f"{label}.results.run_metadata.{field}: contradicts analysis provenance")
    for parameter, field in (("start", "analysis_start"), ("end", "analysis_end_exclusive")):
        if canonical(document["parameters"][parameter]) != canonical(metadata[field]):
            errors.append(f"{label}.parameters.{parameter}: does not cover full imported source")
    return errors


def compare_analysis(actual: dict, reference: dict) -> dict:
    """Exact evidence equality; row order may differ, row multiplicity may not."""
    validation = validate(actual, "actual") + validate(reference, "reference")
    if validation:
        return {"status": "FAIL", "mismatches": validation, "known_facts": "NOT_RUN"}
    actual, reference = normalized(actual), normalized(reference)
    mismatches = known_fact_errors(actual, "actual") + known_fact_errors(reference, "reference")
    facts_pass = not mismatches
    for name in sorted(actual.keys() | reference.keys()):
        if name not in actual or name not in reference:
            mismatches.append(f"{name}: analysis field missing from one document")
        elif name == "results":
            for table in COLUMNS:
                if canonical(actual[name][table]) != canonical(reference[name][table]):
                    mismatches.append(f"results.{table}: row multiset differs")
        elif canonical(actual[name]) != canonical(reference[name]):
            mismatches.append(f"{name}: exact value differs")
    return {
        "status": "FAIL" if mismatches else "PASS",
        "mode": actual["data_mode"],
        "mismatches": mismatches,
        "known_facts": "PASS" if facts_pass else "FAIL",
        "compared_result_sets": len(COLUMNS),
        "compared_queries": len(QUERY_NAMES),
        "ignored_fields": ["results.run_metadata[*].imported_at"],
    }


def capture_portable(directory):
    """Fresh analysis of the preserved Portable database; never import, build or reset."""
    directory = Path(directory)
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError(
            "Portable capture directory must be new or empty; previous results are preserved"
        )
    observations = []

    class ReadOnlyPortable(Settings):
        def connect(self):
            parameters = resolve_connection()
            parameters.update(host="127.0.0.1", port="5433")
            connection = psycopg.connect(
                **parameters,
                options="-c default_transaction_read_only=on",
                connect_timeout=10,
                application_name="retaillens-docker-reference",
            )
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            version, read_only = connection.execute(
                "SELECT version(),current_setting('transaction_read_only')"
            ).fetchone()
            if read_only != "on":
                connection.close()
                raise RuntimeError("Portable reference connection is not read-only")
            observations.append({"mode": self.mode, "postgres_version": version, "read_only": True})
            return connection

    def snapshot(configured):
        with configured.connect() as connection:
            connection.row_factory = dict_row
            select_schema(connection, configured)
            return {
                "metadata": connection.execute("SELECT * FROM run_metadata").fetchall(),
                "counts": {
                    table: connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                    for table in ("raw_records", "mart_orders", "mart_items", "mart_cohorts")
                },
            }

    summaries = {}
    for mode in ("synthetic", "real"):
        configured = ReadOnlyPortable(mode=mode)
        before = snapshot(configured)
        result = analyse(configured, directory / mode)
        after = snapshot(configured)
        if canonical(before) != canonical(after):
            raise RuntimeError(
                f"Preserved Portable snapshot changed during {mode} reference capture"
            )
        check = compare_analysis(result, result)
        if check["status"] != "PASS":
            raise ValueError(
                f"Portable {mode} canonical analysis is invalid: {check['mismatches']}"
            )
        summaries[mode] = {
            "status": "PASS",
            "known_facts": check["known_facts"],
            "analysis_path": str(directory / mode / "analysis.json"),
            "analysis_sha256": sha256(directory / mode / "analysis.json"),
            "source_manifest_sha256": result["source_manifest_sha256"],
            "observation_end": result["observation_end"],
            "overview": result["results"]["03_overview"][0],
            "repeat": result["results"]["08_repeat"][0],
            "preserved_snapshot": before,
        }
    proof = {
        "status": "PASS",
        "host": "127.0.0.1",
        "port": 5433,
        "read_only": True,
        "connections": observations,
        "modes": summaries,
    }
    write_json(directory / "capture.json", proof)
    return proof


def load_analysis(path):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON numeric constant: {value}")

    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        parse_float=Decimal,
        parse_constant=invalid_constant,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("real", "synthetic"))
    parser.add_argument("--actual", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture-portable", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.capture_portable:
            if any((args.mode, args.actual, args.reference)):
                parser.error("--capture-portable accepts only --output DIRECTORY")
            result = capture_portable(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "modes": list(result["modes"]),
                        "read_only": True,
                        "output": str(args.output),
                    }
                )
            )
            return 0
        if not all((args.mode, args.actual, args.reference)):
            parser.error("Comparison requires --mode, --actual and --reference")
        actual, reference = load_analysis(args.actual), load_analysis(args.reference)
        result = compare_analysis(actual, reference)
        if any(
            not isinstance(document, dict) or document.get("data_mode") != args.mode
            for document in (actual, reference)
        ):
            result["status"] = "FAIL"
            result["mismatches"].append("--mode differs from actual or reference data_mode")
        result.update(actual=str(args.actual), reference=str(args.reference))
        write_json(args.output, result)
        print(json.dumps(result))
        return 0 if result["status"] == "PASS" else 1
    except psycopg.Error as error:
        print(
            json.dumps(
                {"status": "FAIL", "error": type(error).__name__, "sqlstate": error.sqlstate}
            ),
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

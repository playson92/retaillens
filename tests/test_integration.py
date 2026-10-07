"""Business contract checks against PostgreSQL, never a SQLite substitute.

Set RETAILLENS_TEST_POSTGRES=1 to enable. These tests replace only rl_synthetic
with temporary artificial CSV inputs; run them sequentially, outside a demo run.
The application-owned audit trail is retained, and rl_real is never written.
"""

import csv
import os
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import errors, sql
from psycopg.rows import dict_row

from retaillens import warehouse
from retaillens.analysis import analyse
from retaillens.config import Settings
from retaillens.fixture import make_fixture
from retaillens.source import FILES
from retaillens.warehouse import ingest, quality, rebuild, select_schema

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RETAILLENS_TEST_POSTGRES") != "1",
        reason="Set RETAILLENS_TEST_POSTGRES=1 for the real PostgreSQL business tests",
    ),
]


@pytest.fixture
def settings():
    configured = Settings(mode="synthetic")
    # Explicit opt-in makes an unavailable database a failure, not a silent skip.
    with configured.connect() as connection:
        assert connection.execute("SELECT version()").fetchone()[0].startswith("PostgreSQL")
    return configured


@pytest.fixture
def source(tmp_path):
    return make_fixture(tmp_path / "synthetic-input")


def read_input(source, table):
    with (source / FILES[table]).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames), list(reader)


def write_input(source, table, columns, rows):
    with (source / FILES[table]).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def query(settings, statement, parameters=None):
    with settings.connect() as connection:
        connection.row_factory = dict_row
        select_schema(connection, settings)
        return connection.execute(statement, parameters).fetchall()


def order(settings, order_id):
    return query(settings, "SELECT * FROM mart_orders WHERE order_id=%s", (order_id,))[0]


def snapshot(settings):
    """Published facts and lineage, excluding the expected changing import clock."""
    tables = [
        "raw_records",
        "import_issues",
        "source_files",
        "stg_orders",
        "stg_items",
        "stg_payments",
        "stg_reviews",
        "stg_customers",
        "stg_products",
        "stg_sellers",
        "stg_translations",
        "mart_orders",
        "mart_items",
        "mart_cohorts",
        "dim_date",
        "dim_product",
        "dim_seller",
        "quality_summary",
    ]
    result = {}
    with settings.connect() as connection:
        select_schema(connection, settings)
        for table in tables:
            statement = sql.SQL("SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text").format(
                sql.Identifier(table)
            )
            result[table] = connection.execute(statement).fetchall()
        result["metadata"] = connection.execute(
            "SELECT to_jsonb(m)-'imported_at' FROM run_metadata m"
        ).fetchall()
    return result


def test_financial_examples_preserve_order_grain(settings, source, tmp_path):
    ingest(settings, source, "fixture-v1")
    result = analyse(settings, tmp_path / "analysis", "2018-01-01", "2018-01-11")
    overview = result["results"]["03_overview"][0]
    assert overview["delivered_orders"] == 2
    assert overview["delivered_gmv_brl"] == Decimal("150.00")
    assert overview["delivered_aov_brl"] == Decimal("75.00")

    first = order(settings, "o1")
    assert first["item_count"] == 2
    assert first["item_value"] == Decimal("100.00")
    assert first["expected_amount"] == Decimal("110.00")
    assert first["paid_amount"] == Decimal("110.00")
    assert first["payment_delta"] == Decimal("0.00")
    assert first["reconciliation_status"] == "matched"
    assert first["review_count"] == 2
    assert first["review_score"] == 4
    assert order(settings, "o3")["item_value"] == Decimal("80.00")
    assert query(settings, "SELECT count(*) AS n FROM mart_orders")[0]["n"] == 8
    assert quality(settings)["status"] == "PASS"


def test_delivery_dates_reviews_and_missing_money_have_separate_populations(settings, source):
    ingest(settings, source, "fixture-v1")
    assert order(settings, "o1")["is_on_time"] is True  # 18:00 on the promised day.
    assert order(settings, "o2")["is_on_time"] is False
    assert order(settings, "o2")["delay_days"] == 1
    assert order(settings, "o5")["delivery_eligible"] is False  # Missing actual delivery.
    assert order(settings, "o5")["is_on_time"] is None
    assert order(settings, "o7")["delivery_eligible"] is False  # Delivered before purchase.
    assert order(settings, "o7")["is_on_time"] is None

    missing_money = order(settings, "o4")
    assert missing_money["gmv_eligible"] is False
    assert missing_money["item_value"] is None
    assert missing_money["delivery_eligible"] is True
    assert missing_money["reconciliation_status"] == "not_comparable"
    tied_reviews = order(settings, "o3")
    assert tied_reviews["review_count"] == 2
    assert tied_reviews["review_ambiguous"] is True
    assert tied_reviews["review_score"] is None
    assert tied_reviews["reviewed_eligible"] is False
    assert tied_reviews["single_seller_id"] is None


def test_invalid_monetary_cells_exclude_complete_amounts_without_losing_raw(settings, source):
    columns, rows = read_input(source, "items")
    next(row for row in rows if row["order_id"] == "o1")["price"] = "NaN"
    next(row for row in rows if row["order_id"] == "o2")["freight_value"] = ""
    write_input(source, "items", columns, rows)
    columns, rows = read_input(source, "payments")
    next(row for row in rows if row["order_id"] == "o3")["payment_value"] = "-1"
    write_input(source, "payments", columns, rows)
    ingest(settings, source, "fixture-v1")

    assert order(settings, "o1")["gmv_eligible"] is False
    assert order(settings, "o1")["item_value"] is None
    assert order(settings, "o1")["delivery_eligible"] is True
    assert order(settings, "o2")["gmv_eligible"] is True
    assert order(settings, "o2")["expected_amount"] is None
    assert order(settings, "o3")["gmv_eligible"] is True
    assert order(settings, "o3")["paid_amount"] is None
    for identifier in ["o1", "o2", "o3"]:
        assert order(settings, identifier)["reconciliation_status"] == "not_comparable"
    issues = query(settings, "SELECT issue FROM import_issues")
    assert {row["issue"] for row in issues} >= {"invalid_price", "invalid_payment_value"}
    assert (
        query(
            settings,
            "SELECT payload->>'price' AS original FROM raw_records "
            "WHERE table_name='items' AND payload->>'order_id'='o1' AND source_row_number=1",
        )[0]["original"]
        == "NaN"
    )


@pytest.mark.parametrize(
    ("table", "field"),
    [("items", "price"), ("items", "freight_value"), ("payments", "payment_value")],
)
def test_missing_monetary_columns_reject_input_and_preserve_publication(
    settings, source, table, field
):
    ingest(settings, source, "fixture-v1")
    before = snapshot(settings)
    columns, rows = read_input(source, table)
    columns.remove(field)
    for row in rows:
        del row[field]
    write_input(source, table, columns, rows)
    with pytest.raises(ValueError, match="Missing required columns"):
        ingest(settings, source, "fixture-v1")
    assert snapshot(settings) == before


def test_duplicates_conflicts_invalid_keys_and_orphans_remain_auditable(settings, source):
    columns, rows = read_input(source, "items")
    original_count = len(rows)
    rows.append(dict(rows[0]))  # Exact duplicate, not a second economic item.
    conflicting = dict(next(row for row in rows if row["order_id"] == "o2"))
    conflicting["price"] = "51.00"
    rows.append(conflicting)  # Both candidates rejected, never arbitrary selection.
    invalid_key = dict(rows[0], order_item_id="0", seller_id="s2")
    rows.append(invalid_key)
    rows.append(dict(rows[0], order_id="orphan-order"))
    write_input(source, "items", columns, rows)

    columns, rows = read_input(source, "payments")
    payment_conflict = dict(next(row for row in rows if row["order_id"] == "o3"))
    payment_conflict["payment_value"] = "85.00"
    rows.append(payment_conflict)
    write_input(source, "payments", columns, rows)
    ingest(settings, source, "fixture-v1")

    assert (
        query(settings, "SELECT count(*) AS n FROM raw_records WHERE table_name='items'")[0]["n"]
        == original_count + 4
    )
    assert query(settings, "SELECT count(*) AS n FROM stg_items WHERE order_id='o1'")[0]["n"] == 2
    assert order(settings, "o1")["gmv_eligible"] is False  # Rejected additional item exists.
    assert order(settings, "o1")["single_seller_id"] is None  # Seller set is uncertain.
    assert order(settings, "o2")["item_count"] == 0
    assert order(settings, "o2")["expected_amount"] is None
    assert order(settings, "o3")["paid_amount"] is None
    assert (
        query(settings, "SELECT count(*) AS n FROM mart_items WHERE order_id='orphan-order'")[0][
            "n"
        ]
        == 0
    )
    issues = query(settings, "SELECT issue,severity,count(*) AS n FROM import_issues GROUP BY 1,2")
    counts = {(row["issue"], row["severity"]): row["n"] for row in issues}
    assert counts[("identical_duplicate", "DEDUPLICATED")] == 1
    assert counts[("conflicting_key", "REJECTED")] == 4
    assert counts[("missing_or_invalid_key", "REJECTED")] == 1
    assert counts[("orphan_order_id", "WARNING")] == 1


def test_reimport_rebuild_are_idempotent_and_preserve_unrelated_table(settings, source):
    ingest(settings, source, "fixture-v1")
    before = snapshot(settings)
    sentinel = "pytest_sentinel_" + uuid4().hex
    with settings.connect() as connection:
        select_schema(connection, settings)
        connection.execute(
            sql.SQL("CREATE TABLE {} (value integer)").format(sql.Identifier(sentinel))
        )
        connection.execute(sql.SQL("INSERT INTO {} VALUES (17)").format(sql.Identifier(sentinel)))
    try:
        rebuild(settings)
        assert snapshot(settings) == before
        ingest(settings, source, "fixture-v1")
        assert snapshot(settings) == before
        with settings.connect() as connection:
            select_schema(connection, settings)
            assert connection.execute(
                sql.SQL("SELECT value FROM {}").format(sql.Identifier(sentinel))
            ).fetchone() == (17,)
    finally:
        with settings.connect() as connection:
            select_schema(connection, settings)
            connection.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(sentinel)))


def test_failed_model_build_rolls_back_import_and_keeps_failed_audit(settings, source, monkeypatch):
    ingest(settings, source, "fixture-v1")
    before = snapshot(settings)
    columns, rows = read_input(source, "items")
    rows[0]["price"] = "999.00"
    write_input(source, "items", columns, rows)
    original_build = warehouse.build

    def fail_after_staging(connection):
        # PostgreSQL must roll back the real DROP/CREATE mart DDL as well as COPY.
        original_build(connection)
        connection.execute("UPDATE stg_orders SET order_status='canceled'")
        raise RuntimeError("Deliberate integration-test model failure")

    monkeypatch.setattr(warehouse, "build", fail_after_staging)
    with pytest.raises(RuntimeError, match="Deliberate integration-test"):
        ingest(settings, source, "fixture-v1")
    assert snapshot(settings) == before
    audit = query(
        settings,
        "SELECT status,error_type FROM rl_audit.ingestion_runs "
        "WHERE data_mode='synthetic' ORDER BY run_id DESC LIMIT 1",
    )[0]
    assert audit == {"status": "FAILED", "error_type": "RuntimeError"}


def add_person_orders(source, person, prefix, purchases):
    customer_columns, customers = read_input(source, "customers")
    order_columns, orders = read_input(source, "orders")
    item_columns, items = read_input(source, "items")
    payment_columns, payments = read_input(source, "payments")
    customer_template = dict(customers[0])
    order_template = dict(orders[0])
    item_template = dict(items[0])
    payment_template = dict(payments[0])
    for index, purchase in enumerate(purchases, 1):
        customer_id, order_id = f"{prefix}-c{index}", f"{prefix}-o{index}"
        customers.append(
            dict(customer_template, customer_id=customer_id, customer_unique_id=person)
        )
        orders.append(
            dict(
                order_template,
                order_id=order_id,
                customer_id=customer_id,
                order_purchase_timestamp=str(purchase),
                order_approved_at=str(purchase + timedelta(hours=1)),
                order_delivered_customer_date=str(purchase + timedelta(days=2)),
                order_estimated_delivery_date=str(purchase + timedelta(days=3)),
            )
        )
        items.append(dict(item_template, order_id=order_id))
        payments.append(dict(payment_template, order_id=order_id, payment_value="45.00"))
    for table, columns, rows in [
        ("customers", customer_columns, customers),
        ("orders", order_columns, orders),
        ("items", item_columns, items),
        ("payments", payment_columns, payments),
    ]:
        write_input(source, table, columns, rows)


def test_repeat_full_windows_exact_boundary_simultaneous_orders_and_first_date_filter(
    settings, source, tmp_path
):
    first = datetime(2018, 1, 1, 10)
    add_person_orders(source, "tie-only", "tie", [first, first])
    add_person_orders(source, "exact-90-days", "exact", [first, first + timedelta(days=90)])
    add_person_orders(
        source, "after-90-days", "after", [first, first + timedelta(days=90, seconds=1)]
    )
    ingest(settings, source, "fixture-v1")
    cohorts = {
        row["customer_unique_id"]: row for row in query(settings, "SELECT * FROM mart_cohorts")
    }
    assert cohorts["u1"]["repeated_90d"] is True  # Distinct customer_id, same person.
    assert cohorts["u1"]["eligible_90d"] is True
    assert cohorts["u4"]["eligible_90d"] is False
    assert "u7" not in cohorts  # Canceled order never forms a delivered cohort.
    assert cohorts["tie-only"]["same_timestamp_orders"] == 1
    assert cohorts["tie-only"]["repeated_90d"] is False
    assert cohorts["exact-90-days"]["repeated_90d"] is True
    assert cohorts["after-90-days"]["repeated_90d"] is False

    later = analyse(settings, tmp_path / "later", "2018-02-01", "2018-06-02")
    repeat = later["results"]["08_repeat"][0]
    assert repeat["first_observed_people"] == 3  # u4, u5, u6; first date, not repeat date.
    assert repeat["eligible_people"] == 1
    assert repeat["repeat_people"] == 0
    assert repeat["incomplete_window_people"] == 2
    assert later["observation_end"].isoformat() == "2018-06-01"


def test_reconciliation_tolerance_is_exact_and_analysis_records_built_tolerance(
    settings, source, tmp_path
):
    ingest(settings, source, "fixture-v1")
    assert order(settings, "o8")["payment_delta"] == Decimal("0.01")
    assert order(settings, "o8")["reconciliation_status"] == "matched"
    assert order(settings, "o7")["reconciliation_status"] == "mismatch"

    zero_tolerance = Settings(mode="synthetic", tolerance=Decimal("0.00"))
    rebuild(zero_tolerance)
    assert order(settings, "o8")["reconciliation_status"] == "mismatch"
    # A fresh process can have a different CLI default from the built model.
    evidence = analyse(settings, tmp_path / "different-default")
    assert evidence["reconciliation_tolerance"] == Decimal("0.00")

    finer_tolerance = Settings(mode="synthetic", tolerance=Decimal("0.005"))
    rebuild(finer_tolerance)
    assert order(settings, "o8")["reconciliation_status"] == "mismatch"
    assert query(settings, "SELECT reconciliation_tolerance FROM run_metadata")[0][
        "reconciliation_tolerance"
    ] == Decimal("0.005")


def test_fixture_provenance_cannot_be_imported_as_real(settings, source):
    ingest(settings, source, "fixture-v1")
    before = snapshot(settings)
    with pytest.raises(ValueError, match="mode/version"):
        ingest(Settings(mode="real"), source, "fixture-v1")
    with pytest.raises(ValueError, match="mode/version"):
        ingest(settings, source, "different-version")
    assert snapshot(settings) == before


def test_missing_schema_never_falls_back_to_unrelated_public_tables(settings, source):
    ingest(settings, source, "fixture-v1")
    before = snapshot(settings)
    suffix = uuid4().hex
    sentinel = "pytest_public_sentinel_" + suffix

    class MissingSchemaSettings(Settings):
        @property
        def schema(self):
            return "rl_missing_test_" + suffix

    absent = MissingSchemaSettings(mode="synthetic")
    with settings.connect() as connection:
        select_schema(connection, settings)
        assert connection.execute("SELECT current_schemas(false)").fetchone()[0] == ["rl_synthetic"]
        assert connection.execute("SELECT current_schemas(true)").fetchone()[0] == [
            "pg_catalog",
            "rl_synthetic",
        ]
        # A unique public table is created only inside this rolled-back transaction.
        # No pre-existing public relation is inspected or changed.
        connection.execute(
            sql.SQL("CREATE TABLE public.{} (marker integer)").format(sql.Identifier(sentinel))
        )
        connection.execute(
            sql.SQL("INSERT INTO public.{} VALUES (17)").format(sql.Identifier(sentinel))
        )
        select_schema(connection, absent)
        assert connection.execute("SELECT current_schemas(false)").fetchone()[0] == []
        with pytest.raises(errors.UndefinedTable):
            connection.execute(sql.SQL("SELECT marker FROM {}").format(sql.Identifier(sentinel)))
        connection.rollback()  # Removes our uncommitted sentinel, including on successful test.

    with settings.connect() as connection:
        assert (
            connection.execute("SELECT to_regclass(%s)", ("public." + sentinel,)).fetchone()[0]
            is None
        )
    with pytest.raises(errors.UndefinedTable):
        rebuild(absent)
    assert snapshot(settings) == before


def test_unresolved_seller_is_unknown_in_items_and_excluded_from_seller_outcomes(
    settings, source, tmp_path
):
    columns, rows = read_input(source, "items")
    for row in rows:
        if row["order_id"] == "o1":
            row["seller_id"] = "seller-not-in-dimension"
            row["product_id"] = "product-not-in-dimension"
    write_input(source, "items", columns, rows)
    ingest(settings, source, "fixture-v1")

    first = order(settings, "o1")
    assert first["gmv_eligible"] is True
    assert first["item_value"] == Decimal("100.00")
    assert first["delivery_eligible"] is True
    assert first["single_seller_id"] is None
    items = query(settings, "SELECT product_id,seller_id FROM mart_items WHERE order_id='o1'")
    assert items == [
        {"product_id": "__unknown__", "seller_id": "__unknown__"},
        {"product_id": "__unknown__", "seller_id": "__unknown__"},
    ]
    assert (
        query(settings, "SELECT count(*) AS n FROM import_issues WHERE issue='orphan_seller_id'")[
            0
        ]["n"]
        == 2
    )
    assert (
        query(settings, "SELECT count(*) AS n FROM import_issues WHERE issue='orphan_product_id'")[
            0
        ]["n"]
        == 2
    )
    evidence = analyse(settings, tmp_path / "unknown-seller")
    sellers = evidence["results"]["09_seller_delivery"]
    assert {row["seller_id"] for row in sellers} == {"s1", "s2"}
    assert sum(row["eligible_orders"] for row in sellers) == 3
    assert not query(settings, "SELECT 1 FROM mart_orders WHERE reviewed_eligible IS NULL")

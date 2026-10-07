"""Explicit Olist schemas, strict conversion and reproducible source profiling."""

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "translations": "product_category_name_translation.csv",
}
SCHEMAS = {
    "orders": {
        "order_id": "text",
        "customer_id": "text",
        "order_status": "text",
        "order_purchase_timestamp": "timestamp",
        "order_approved_at": "timestamp",
        "order_delivered_carrier_date": "timestamp",
        "order_delivered_customer_date": "timestamp",
        "order_estimated_delivery_date": "timestamp",
    },
    "customers": {
        "customer_id": "text",
        "customer_unique_id": "text",
        "customer_zip_code_prefix": "text",
        "customer_city": "text",
        "customer_state": "text",
    },
    "items": {
        "order_id": "text",
        "order_item_id": "integer",
        "product_id": "text",
        "seller_id": "text",
        "shipping_limit_date": "timestamp",
        "price": "numeric(18,2)",
        "freight_value": "numeric(18,2)",
    },
    "payments": {
        "order_id": "text",
        "payment_sequential": "integer",
        "payment_type": "text",
        "payment_installments": "integer",
        "payment_value": "numeric(18,2)",
    },
    "reviews": {
        "review_id": "text",
        "order_id": "text",
        "review_score": "integer",
        "review_comment_title": "text",
        "review_comment_message": "text",
        "review_creation_date": "timestamp",
        "review_answer_timestamp": "timestamp",
    },
    "products": {
        "product_id": "text",
        "product_category_name": "text",
        "product_name_lenght": "integer",
        "product_description_lenght": "integer",
        "product_photos_qty": "integer",
        "product_weight_g": "integer",
        "product_length_cm": "integer",
        "product_height_cm": "integer",
        "product_width_cm": "integer",
    },
    "sellers": {
        "seller_id": "text",
        "seller_zip_code_prefix": "text",
        "seller_city": "text",
        "seller_state": "text",
    },
    "translations": {"product_category_name": "text", "product_category_name_english": "text"},
}
KEYS = {
    "orders": ("order_id",),
    "customers": ("customer_id",),
    "items": ("order_id", "order_item_id"),
    "payments": ("order_id", "payment_sequential"),
    "products": ("product_id",),
    "sellers": ("seller_id",),
    "translations": ("product_category_name",),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path, table=None):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        normalized = [name.strip() for name in headers]
        if not headers or any(not name for name in normalized):
            raise ValueError(f"Empty CSV column header in {Path(path).name}")
        duplicate_headers = [name for name, count in Counter(normalized).items() if count > 1]
        if duplicate_headers:
            raise ValueError(
                f"Duplicate CSV column headers in {Path(path).name}: {', '.join(duplicate_headers)}"
            )
        if table and not set(SCHEMAS[table]).issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required columns in {Path(path).name}")
        for number, row in enumerate(reader, 1):
            if None in row or None in row.values():
                raise ValueError(f"Malformed CSV record {number} in {Path(path).name}")
            yield number, row


def convert(value, kind, field):
    if value is None or value.strip() == "":
        return None
    if kind == "text":
        return value
    if kind == "timestamp":
        result = datetime.fromisoformat(value)
        if result.tzinfo:
            raise ValueError("Source timestamps must be naive; no timezone assumption")
        return result
    if kind == "integer":
        result = int(value)
        if not -2147483648 <= result <= 2147483647:
            raise ValueError("Outside PostgreSQL integer range")
        if field == "review_score" and not 1 <= result <= 5:
            raise ValueError("Review score outside 1..5")
        if field in {"order_item_id", "payment_sequential"} and result < 1:
            raise ValueError("Sequence must be positive")
        return result
    result = Decimal(value)
    if not result.is_finite() or result < 0 or result >= Decimal("1e16"):
        raise ValueError("Invalid nonnegative money")
    if result != result.quantize(Decimal("0.01")):
        raise ValueError("Money has more than two decimal places")
    return result


def parse_row(table, row):
    parsed, issues = {}, []
    for field, kind in SCHEMAS[table].items():
        try:
            parsed[field] = convert(row.get(field), kind, field)
        except (ValueError, InvalidOperation, OverflowError):
            parsed[field] = None
            issues.append(f"invalid_{field}")
    return parsed, issues


def profile(directory, mode, version):
    directory = Path(directory)
    manifest = {"data_mode": mode, "source_version": version, "files": []}
    for table, filename in FILES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {filename}")
        count = 0
        missing, invalid, keys, statuses, months = (
            Counter(),
            Counter(),
            Counter(),
            Counter(),
            Counter(),
        )
        date_min = date_max = None
        for _, row in read_rows(path, table):
            count += 1
            parsed, issues = parse_row(table, row)
            missing.update(k for k, v in parsed.items() if v is None)
            invalid.update(issues)
            if table in KEYS:
                keys[tuple(parsed[k] for k in KEYS[table])] += 1
            if table == "orders":
                statuses[parsed["order_status"]] += 1
                dt = parsed["order_purchase_timestamp"]
                if dt:
                    date_min = min(date_min or dt, dt)
                    date_max = max(date_max or dt, dt)
                    months[dt.strftime("%Y-%m")] += 1
        manifest["files"].append(
            {
                "table": table,
                "filename": filename,
                "sha256": sha256(path),
                "rows": count,
                "missing": dict(missing),
                "invalid": dict(invalid),
                "duplicate_key_rows": sum(n - 1 for n in keys.values() if n > 1),
                "date_min": str(date_min) if date_min else None,
                "date_max": str(date_max) if date_max else None,
                "statuses": dict(statuses),
                "months": dict(sorted(months.items())),
            }
        )
    # The optional million-row geolocation input is retained/profiled but not joined into marts.
    geo = directory / "olist_geolocation_dataset.csv"
    if geo.exists():
        manifest["files"].append(
            {
                "table": "geolocation",
                "filename": geo.name,
                "sha256": sha256(geo),
                "rows": sum(1 for _ in read_rows(geo)),
                "usage": "source only; excluded from MVP marts",
            }
        )
    manifest["source_manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    return manifest


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )

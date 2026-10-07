"""Small deterministic artificial inputs; never represented as Olist observations."""

import csv
import json
from pathlib import Path

from retaillens.source import FILES, SCHEMAS, write_json


def make_fixture(directory):
    directory = Path(directory)
    if directory.exists():
        existing = {p.name for p in directory.iterdir()}
        if existing - {".gitkeep", "EXPECTED.json"}:
            provenance = directory / "SOURCE.json"
            source = (
                json.loads(provenance.read_text(encoding="utf-8")) if provenance.is_file() else {}
            )
            if (
                source.get("data_mode") != "synthetic"
                or source.get("source_version") != "fixture-v1"
            ):
                raise ValueError(
                    "Fixture generation refuses to overwrite real or unrecognized inputs"
                )
    directory.mkdir(parents=True, exist_ok=True)
    rows = {table: [] for table in FILES}
    dates = ["01-01", "01-10", "01-15", "02-01", "04-30", "06-01", "03-01", "03-05"]
    deliveries = [
        "01-10 18:00:00",
        "01-21 10:00:00",
        "01-25 18:00:00",
        "02-12 10:00:00",
        "",
        "",
        "02-28 10:00:00",
        "03-10 18:00:00",
    ]
    estimated = ["01-10", "01-20", "01-25", "02-10", "05-10", "06-10", "03-10", "03-10"]
    people = ["u1", "u2", "u3", "u1", "u4", "u7", "u5", "u6"]
    for i in range(1, 9):
        rows["orders"].append(
            {
                "order_id": f"o{i}",
                "customer_id": f"c{i}",
                "order_status": "canceled" if i == 6 else "delivered",
                "order_purchase_timestamp": f"2018-{dates[i - 1]} 10:00:00",
                "order_approved_at": f"2018-{dates[i - 1]} 11:00:00",
                "order_delivered_carrier_date": "",
                "order_delivered_customer_date": f"2018-{deliveries[i - 1]}"
                if deliveries[i - 1]
                else "",
                "order_estimated_delivery_date": f"2018-{estimated[i - 1]} 00:00:00",
            }
        )
        rows["customers"].append(
            {
                "customer_id": f"c{i}",
                "customer_unique_id": people[i - 1],
                "customer_zip_code_prefix": "01000",
                "customer_city": "synthetic city",
                "customer_state": "SP" if i % 2 else "RJ",
            }
        )
    for order, prices, freights, sellers in [
        (1, ["40", "60"], ["5", "5"], ["s1", "s1"]),
        (2, ["50"], ["5"], ["s2"]),
        (3, ["40", "40"], ["2", "2"], ["s1", "s2"]),
        (4, [""], ["3"], ["s1"]),
        (5, ["30"], ["5"], ["s2"]),
        (6, ["20"], ["5"], ["s1"]),
        (7, ["70"], ["5"], ["s1"]),
        (8, ["10"], ["0"], ["s2"]),
    ]:
        for j, (price, freight, seller) in enumerate(
            zip(prices, freights, sellers, strict=True), 1
        ):
            rows["items"].append(
                {
                    "order_id": f"o{order}",
                    "order_item_id": j,
                    "product_id": f"p{j}",
                    "seller_id": seller,
                    "shipping_limit_date": "2018-06-05 00:00:00",
                    "price": price,
                    "freight_value": freight,
                }
            )
    for order, values in [
        (1, ["70", "40"]),
        (2, ["55"]),
        (3, ["84"]),
        (4, ["13"]),
        (5, ["35"]),
        (6, ["25"]),
        (7, ["74.98"]),
        (8, ["10.01"]),
    ]:
        for j, value in enumerate(values, 1):
            rows["payments"].append(
                {
                    "order_id": f"o{order}",
                    "payment_sequential": j,
                    "payment_type": "credit_card",
                    "payment_installments": 4,
                    "payment_value": value,
                }
            )
    for order, score, answer in [
        (1, 5, "01-11"),
        (1, 4, "01-12"),
        (2, 1, "01-22"),
        (3, 5, "01-26"),
        (3, 1, "01-26"),
        (4, 2, "02-13"),
        (5, 5, "05-11"),
        (7, 4, "03-11"),
    ]:
        rows["reviews"].append(
            {
                "review_id": f"r{order}",
                "order_id": f"o{order}",
                "review_score": score,
                "review_comment_title": "",
                "review_comment_message": "synthetic",
                "review_creation_date": f"2018-{answer} 00:00:00",
                "review_answer_timestamp": f"2018-{answer} 12:00:00",
            }
        )
    for j, category in [(1, "books"), (2, "toys")]:
        rows["products"].append({"product_id": f"p{j}", "product_category_name": category})
        rows["translations"].append(
            {"product_category_name": category, "product_category_name_english": category}
        )
        rows["sellers"].append(
            {
                "seller_id": f"s{j}",
                "seller_zip_code_prefix": "01000",
                "seller_city": "synthetic city",
                "seller_state": "SP",
            }
        )
    for table, data in rows.items():
        with (directory / FILES[table]).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(SCHEMAS[table]), restval="")
            writer.writeheader()
            writer.writerows(data)
    write_json(
        directory / "SOURCE.json",
        {
            "data_mode": "synthetic",
            "source_version": "fixture-v1",
            "license": "MIT",
            "description": "Artificial edge cases generated by RetailLens; not real Olist data",
        },
    )
    return directory

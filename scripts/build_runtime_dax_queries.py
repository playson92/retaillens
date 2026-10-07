"""Prepare read-only runtime queries from the independently computed SQL cases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def dax_string(value: str) -> str:
    """DAX doubles embedded quotes; Unicode and backslashes stay literal."""
    return '"' + value.replace('"', '""') + '"'


def date_literal(value: str) -> str:
    year, month, day = map(int, value.split("-"))
    return f"DATE({year},{month},{day})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("real", "synthetic"), required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    cases = expected["modes"][args.mode]["cases"]
    measures = list(cases["full_source"]["measures"])
    row = "ROW(" + ",\n".join(f"{dax_string(name)},[{name}]" for name in measures) + ")"
    queries: list[dict[str, str]] = []
    for name, case in cases.items():
        filters = case["filters"]
        predicates = []
        if filters["empty"]:
            predicates.append("FILTER(ALL('Date'),FALSE())")
        elif filters["start"]:
            predicates.append(
                "FILTER(ALL('Date'),'Date'[date]>="
                + date_literal(filters["start"])
                + "&&'Date'[date]<"
                + date_literal(filters["end"])
                + ")"
            )
        for field, table, column in (
            ("category", "Product", "category"),
            ("seller", "Seller", "seller_id"),
        ):
            if filters[field]:
                literal = dax_string(filters[field])
                predicates.append(f"TREATAS({{{literal}}},'{table}'[{column}])")
        dax = "EVALUATE " + row
        if predicates:
            dax = "EVALUATE CALCULATETABLE(" + row + "," + ",".join(predicates) + ")"
        queries.append({"id": "case:" + name, "dax": dax})
    supplied = (
        project / "powerbi/RetailLens.SemanticModel/DAXQueries/Reconciliation.dax"
    ).read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^EVALUATE\s*$", supplied)[1:]
    supplied_ids = [
        name
        for name in expected["modes"][args.mode]["supplied_evaluate_queries"]
        if name != "2_suppressed_all_blank_groups"
    ]
    for name, block in zip(supplied_ids, blocks, strict=True):
        queries.append({"id": "supplied:" + name, "dax": "EVALUATE\n" + block})
    queries.append(
        {
            "id": "proof:import_counts",
            "dax": "EVALUATE ROW("
            + ",".join(
                f"\"{name}\",COUNTROWS('{name}')"
                for name in (
                    "Orders",
                    "Items",
                    "Date",
                    "Product",
                    "Seller",
                    "Cohorts",
                    "Quality",
                    "Run",
                )
            )
            + ")",
        }
    )
    queries.append({"id": "proof:run_metadata", "dax": "EVALUATE 'Run'"})
    if args.mode == "synthetic":
        queries.append(
            {
                "id": "edge:seller_s2_zero_numerator",
                "dax": 'EVALUATE CALCULATETABLE(ROW("Eligible",[Single Seller Delivery Orders],'
                '"OnTime",[Single Seller On Time Orders],"Rate",[Single Seller On Time Rate]),'
                "TREATAS({\"s2\"},'Seller'[seller_id]),"
                "FILTER(ALL('Date'),'Date'[date]>=DATE(2018,1,1)&&'Date'[date]<DATE(2018,2,1)))",
            }
        )
    args.output.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

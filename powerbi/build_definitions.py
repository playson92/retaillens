"""Deterministically author the RetailLens TMDL model and native PBIR report."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "RetailLens.SemanticModel"
REPORT = ROOT / "RetailLens.Report"
BASE = "https://developer.microsoft.com/json-schemas/"
SCHEMAS = {
    "pbip": BASE + "fabric/pbip/pbipProperties/1.0.0/schema.json",
    "pbir": BASE + "fabric/item/report/definitionProperties/2.0.0/schema.json",
    "pbism": BASE + "fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "report": BASE + "fabric/item/report/definition/report/3.3.0/schema.json",
    "page": BASE + "fabric/item/report/definition/page/2.1.0/schema.json",
    "visual": BASE + "fabric/item/report/definition/visualContainer/2.9.0/schema.json",
    "pages": BASE + "fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "version": BASE + "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
}

# SQL source columns are preserved, making warehouse-to-model comparisons direct.
# Decimal is TOM's fixed decimal currency storage; Double is deliberately unused.
TABLES = {
    "Orders": (
        "mart_orders",
        {
            "order_id": "string",
            "purchase_date": "dateTime",
            "order_status": "string",
            "customer_unique_id": "string",
            "customer_state": "string",
            "item_value": "decimal",
            "expected_amount": "decimal",
            "paid_amount": "decimal",
            "payment_delta": "decimal",
            "gmv_eligible": "boolean",
            "delivery_eligible": "boolean",
            "is_on_time": "boolean",
            "delay_days": "int64",
            "review_score": "int64",
            "review_ambiguous": "boolean",
            "item_count": "int64",
            "seller_count": "int64",
            "single_seller_id": "string",
            "reconciliation_status": "string",
            "purchase_timestamp": "dateTime",
            "missing_price_count": "int64",
            "missing_freight_count": "int64",
            "missing_payment_count": "int64",
            "review_count": "int64",
            "reviewed_eligible": "boolean",
        },
    ),
    "Items": (
        "mart_items",
        {
            "order_id": "string",
            "order_item_id": "int64",
            "purchase_date": "dateTime",
            "product_id": "string",
            "seller_id": "string",
            "price": "decimal",
            "freight_value": "decimal",
            "gmv_eligible": "boolean",
        },
    ),
    "Date": (
        "dim_date",
        {
            "date": "dateTime",
            "year": "int64",
            "month": "int64",
            "year_month": "string",
            "is_boundary_month": "boolean",
        },
    ),
    "Product": ("dim_product", {"product_id": "string", "category": "string"}),
    "Seller": ("dim_seller", {"seller_id": "string", "seller_state": "string"}),
    "Cohorts": (
        "mart_cohorts",
        {
            "customer_unique_id": "string",
            "first_purchase_date": "dateTime",
            "eligible_90d": "boolean",
            "repeated_90d": "boolean",
            "first_purchase_timestamp": "dateTime",
            "same_timestamp_orders": "int64",
        },
    ),
    "Quality": (
        "quality_summary",
        {
            "check_name": "string",
            "severity": "string",
            "affected_rows": "int64",
            "details": "string",
        },
    ),
    "Run": (
        "run_metadata",
        {
            "data_mode": "string",
            "source_version": "string",
            "analysis_start": "dateTime",
            "analysis_end_exclusive": "dateTime",
            "observation_end": "dateTime",
            "observation_basis": "string",
            "imported_at": "dateTime",
            "reconciliation_tolerance": "string",
            "source_manifest_sha256": "string",
        },
    ),
}

MONEY = '"BRL "#,0.00;("BRL "#,0.00);"BRL "0.00'
COUNT = "#,0"
PCT = "0.0%;-0.0%;0.0%"
MEASURES = {}


def measure(name, dax, format_string=COUNT, folder="Population", description=""):
    MEASURES[name] = (dax, format_string, folder, description)


measure("Order Count", "COUNTROWS('Orders')", description="One row per order, all statuses.")
measure(
    "Delivered Order Count",
    "CALCULATE([Order Count], KEEPFILTERS('Orders'[order_status] = \"delivered\"))",
)
measure("Nondelivered Orders", "[Order Count] - [Delivered Order Count]")
measure(
    "GMV Eligible Orders", "CALCULATE([Order Count], KEEPFILTERS('Orders'[gmv_eligible] = TRUE()))"
)
measure(
    "Delivered GMV",
    "CALCULATE(SUM('Orders'[item_value]), KEEPFILTERS('Orders'[gmv_eligible] = TRUE()))",
    MONEY,
    "Value",
    "M1. Delivered orders, valid purchase date, nonempty items, every price valid. Excludes freight; purchase date filter. Product/seller filters do not change this order-grain measure.",
)
measure(
    "Delivered AOV",
    "DIVIDE([Delivered GMV], [GMV Eligible Orders])",
    MONEY,
    "Value",
    "M2. Exactly the M1 population. BLANK on zero denominator.",
)
measure("GMV Excluded Delivered Orders", "[Delivered Order Count] - [GMV Eligible Orders]")
measure(
    "Delivery Eligible Orders",
    "CALCULATE([Order Count], KEEPFILTERS('Orders'[delivery_eligible] = TRUE()))",
    folder="Delivery",
)
measure(
    "On Time Orders",
    "CALCULATE([Delivery Eligible Orders], KEEPFILTERS('Orders'[is_on_time] = TRUE()))",
    folder="Delivery",
)
measure(
    "Late Orders",
    "CALCULATE([Delivery Eligible Orders], KEEPFILTERS('Orders'[is_on_time] = FALSE()))",
    folder="Delivery",
)
measure(
    "On Time Rate",
    "DIVIDE([On Time Orders], [Delivery Eligible Orders])",
    PCT,
    "Delivery",
    "M3. Delivered with valid purchase, promised and actual dates, consistent chronology; compares source calendar days. Missing amount does not exclude delivery.",
)
measure(
    "Delivery Excluded Orders",
    "[Delivered Order Count] - [Delivery Eligible Orders]",
    folder="Delivery",
)
measure(
    "Mean Late Days",
    "CALCULATE(AVERAGE('Orders'[delay_days]), KEEPFILTERS('Orders'[delivery_eligible] = TRUE()), KEEPFILTERS('Orders'[is_on_time] = FALSE()))",
    "0.0",
    "Delivery",
    "Days after promised date, late eligible orders only.",
)
measure(
    "Reviewed Delivery Orders",
    "CALCULATE([Delivery Eligible Orders], KEEPFILTERS('Orders'[reviewed_eligible] = TRUE()))",
    folder="Reviews",
)
measure(
    "Review Coverage",
    "DIVIDE([Reviewed Delivery Orders], [Delivery Eligible Orders])",
    PCT,
    "Reviews",
    "One selected valid latest review per eligible delivery order; tied conflicting latest scores excluded.",
)
measure(
    "Mean Review Score",
    "CALCULATE(AVERAGE('Orders'[review_score]), KEEPFILTERS('Orders'[delivery_eligible] = TRUE()), KEEPFILTERS('Orders'[reviewed_eligible] = TRUE()))",
    "0.00",
    "Reviews",
)
measure(
    "Ambiguous Review Orders",
    "CALCULATE([Order Count], KEEPFILTERS('Orders'[review_ambiguous] = TRUE()))",
    folder="Reviews",
)
measure(
    "Unreviewed Delivery Orders",
    "[Delivery Eligible Orders] - [Reviewed Delivery Orders]",
    folder="Reviews",
)
measure(
    "Delivered Segment Item Value",
    "CALCULATE(SUM('Items'[price]), KEEPFILTERS('Items'[gmv_eligible] = TRUE()))",
    MONEY,
    "Segments",
    "Eligible delivered items filtered by seller/category. Not whole-order GMV under segment filters.",
)
measure(
    "Segment Eligible Orders",
    "CALCULATE(DISTINCTCOUNT('Items'[order_id]), KEEPFILTERS('Items'[gmv_eligible] = TRUE()))",
    folder="Segments",
)
measure(
    "Segment Item Value Per Order",
    "DIVIDE([Delivered Segment Item Value], [Segment Eligible Orders])",
    MONEY,
    "Segments",
    "Sum of selected segment's eligible items divided by orders containing them; not whole-order AOV.",
)
measure(
    "Segment Value Share",
    "DIVIDE([Delivered Segment Item Value], CALCULATE([Delivered Segment Item Value], REMOVEFILTERS('Product'), REMOVEFILTERS('Seller')))",
    PCT,
    "Segments",
    "Share of all eligible item value in current date/order filters; removes seller and product filters only in denominator.",
)
measure(
    "Single Seller Delivery Orders",
    "CALCULATE([Delivery Eligible Orders], KEEPFILTERS('Orders'[seller_count] = 1), KEEPFILTERS(TREATAS(VALUES('Seller'[seller_id]), 'Orders'[single_seller_id])))",
    folder="Segments",
)
measure(
    "Single Seller On Time Orders",
    "CALCULATE([Single Seller Delivery Orders], KEEPFILTERS('Orders'[is_on_time] = TRUE()))",
    folder="Segments",
)
measure(
    "Single Seller On Time Rate",
    "DIVIDE([Single Seller On Time Orders], [Single Seller Delivery Orders])",
    PCT,
    "Segments",
    "Seller timing restricted to orders with exactly one seller. Product/category filters ignored. No causal attribution.",
)
measure(
    "Single Seller Reviewed Orders",
    "CALCULATE([Single Seller Delivery Orders], KEEPFILTERS('Orders'[reviewed_eligible] = TRUE()))",
    folder="Segments",
)
measure(
    "Single Seller Review Coverage",
    "DIVIDE([Single Seller Reviewed Orders], [Single Seller Delivery Orders])",
    PCT,
    "Segments",
)
measure(
    "Single Seller Mean Review",
    "CALCULATE(AVERAGE('Orders'[review_score]), KEEPFILTERS('Orders'[delivery_eligible] = TRUE()), KEEPFILTERS('Orders'[reviewed_eligible] = TRUE()), KEEPFILTERS('Orders'[seller_count] = 1), KEEPFILTERS(TREATAS(VALUES('Seller'[seller_id]), 'Orders'[single_seller_id])))",
    "0.00",
    "Segments",
)
measure(
    "Multi Seller Delivery Exclusions",
    "CALCULATE([Delivery Eligible Orders], KEEPFILTERS('Orders'[seller_count] > 1))",
    folder="Segments",
    description="Overall eligible multi-seller orders excluded from seller timing. Does not allocate to sellers; ignores seller/category filters.",
)
measure(
    "Matched Delivered Orders",
    "CALCULATE([Delivered Order Count], KEEPFILTERS('Orders'[reconciliation_status] = \"matched\"))",
    folder="Payments",
)
measure(
    "Mismatch Delivered Orders",
    "CALCULATE([Delivered Order Count], KEEPFILTERS('Orders'[reconciliation_status] = \"mismatch\"))",
    folder="Payments",
)
measure(
    "Comparable Delivered Orders",
    "[Matched Delivered Orders] + [Mismatch Delivered Orders]",
    folder="Payments",
)
measure(
    "Payment Matched Rate",
    "DIVIDE([Matched Delivered Orders], [Comparable Delivered Orders])",
    PCT,
    "Payments",
    "M4. Matched/(matched+mismatch), delivered only. Completeness and configured tolerance enforced in SQL; not accounting completeness.",
)
measure(
    "Not Comparable Delivered Orders",
    "CALCULATE([Delivered Order Count], KEEPFILTERS('Orders'[reconciliation_status] = \"not_comparable\"))",
    folder="Payments",
)
measure(
    "Not Comparable Delivered Share",
    "DIVIDE([Not Comparable Delivered Orders], [Delivered Order Count])",
    PCT,
    "Payments",
)
measure("Expected Amount BRL", "SUM('Orders'[expected_amount])", MONEY, "Payments")
measure("Paid Amount BRL", "SUM('Orders'[paid_amount])", MONEY, "Payments")
measure(
    "Payment Delta BRL",
    "SUM('Orders'[payment_delta])",
    MONEY,
    "Payments",
    "Order-grain paid minus expected; a discrepancy is not automatically loss/refund.",
)
measure(
    "Eligible Cohort Customers",
    "CALCULATE(COUNTROWS('Cohorts'), KEEPFILTERS('Cohorts'[eligible_90d] = TRUE()))",
    folder="Repeat",
)
measure(
    "Repeat 90d Customers",
    "CALCULATE([Eligible Cohort Customers], KEEPFILTERS('Cohorts'[repeated_90d] = TRUE()))",
    folder="Repeat",
)
measure(
    "Observed Repeat 90d Rate",
    "DIVIDE([Repeat 90d Customers], [Eligible Cohort Customers])",
    PCT,
    "Repeat",
    "M5. First observed delivered purchase set before report filters; date filters first purchase. Full assumed 90-day observation window required. Seller/category/status/customer-state filters do not change this measure. Equal timestamps do not count as later purchases.",
)
measure(
    "Incomplete Cohort Windows",
    "CALCULATE(COUNTROWS('Cohorts'), KEEPFILTERS('Cohorts'[eligible_90d] = FALSE()))",
    folder="Repeat",
)
measure(
    "Same Timestamp Additional Orders", "SUM('Cohorts'[same_timestamp_orders])", folder="Repeat"
)
measure(
    "Reported Quality Rule Occurrences",
    "SUM('Quality'[affected_rows])",
    folder="Quality",
    description="Global snapshot across rules, not distinct bad orders. Rule counts may overlap. Date filters do not change snapshot.",
)
measure(
    "Orders Missing Price",
    "CALCULATE([Order Count], KEEPFILTERS('Orders'[missing_price_count] > 0))",
    folder="Quality",
    description="Orders containing at least one item with a missing/invalid price; zero-item orders are separate quality exclusions.",
)
measure(
    "Orders Missing Freight",
    "CALCULATE([Order Count], KEEPFILTERS('Orders'[missing_freight_count] > 0))",
    folder="Quality",
    description="Orders containing at least one item with a missing/invalid freight value; zero-item orders are separate quality exclusions.",
)
measure(
    "Orders Missing Payment",
    "CALCULATE([Order Count], KEEPFILTERS(ISBLANK('Orders'[paid_amount])))",
    folder="Quality",
    description="Missing or incomplete payment side, including orders with no payment rows. ISBLANK preserves legitimate zero paid amounts.",
)
measure(
    "Selected Data Mode",
    'SELECTEDVALUE(\'Run\'[data_mode], "Unknown mode") & " / " & SELECTEDVALUE(\'Run\'[source_version], "Unknown source")',
    "",
    "Provenance",
)
measure(
    "Scope Note",
    '"BRL; purchase dates. Source coverage is assumed, not certified. Mode: " & [Selected Data Mode]',
    "",
    "Provenance",
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(value, encoding="utf-8", newline="\n")


def model():
    write(
        MODEL / "definition.pbism",
        {"$schema": SCHEMAS["pbism"], "version": "4.0", "settings": {"qnaEnabled": False}},
    )
    write(MODEL / "definition/database.tmdl", "database RetailLens\n\tcompatibilityLevel: 1600\n")
    content = "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\n"
    content += "\n\tannotation PBI_TimeIntelligenceEnabled = 0\n"
    content += "\n" + "".join(f"ref table '{table}'\n" for table in TABLES)
    write(MODEL / "definition/model.tmdl", content)
    expressions = []
    for name, default in [
        ("ServerHost", "localhost"),
        ("ServerPort", "5433"),
        ("DatabaseName", "retaillens"),
        ("DataMode", "real"),
    ]:
        expressions.append(
            f'expression {name} = "{default}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\tkind: m\n'
        )
    expressions.append(
        """expression WarehouseTable =
        (tableName as text) as table =>
        let
            SchemaName = if DataMode = "real" then "rl_real" else if DataMode = "synthetic" then "rl_synthetic" else error "DataMode must be real or synthetic",
            Source = PostgreSQL.Database(ServerHost & ":" & ServerPort, DatabaseName, [CreateNavigationProperties=false]),
            Data = if tableName = "run_metadata" then
                Value.NativeQuery(Source, "SELECT data_mode,source_version,analysis_start,analysis_end_exclusive,observation_end,observation_basis,imported_at,reconciliation_tolerance::text AS reconciliation_tolerance,source_manifest_sha256 FROM " & SchemaName & ".run_metadata", null, [EnableFolding=true])
                else Source{[Schema=SchemaName, Item=tableName]}[Data]
        in
            Data
    kind: m
""".replace("    ", "\t")
    )
    write(MODEL / "definition/expressions.tmdl", "\n".join(expressions))
    for table, (source, columns) in TABLES.items():
        lines = [f"table '{table}'", ""]
        for column, datatype in columns.items():
            lines.extend(
                [
                    f"\tcolumn '{column}'",
                    f"\t\tdataType: {datatype}",
                    f"\t\tsourceColumn: {column}",
                    "\t\tsummarizeBy: none",
                ]
            )
            if datatype == "decimal":
                lines.append(
                    f"\t\tformatString: {MONEY if column != 'reconciliation_tolerance' else '0.00'}"
                )
            if datatype == "dateTime":
                lines.append(
                    "\t\tformatString: yyyy-MM-dd HH:mm:ss"
                    if "timestamp" in column or column == "imported_at"
                    else "\t\tformatString: yyyy-MM-dd"
                )
            lines.append("")
        if table == "Orders":
            for name, (dax, fmt, folder, description) in MEASURES.items():
                if description:
                    lines.append(f"\t/// {description}")
                lines.extend([f"\tmeasure '{name}' = {dax}", f"\t\tdisplayFolder: {folder}"])
                if fmt:
                    lines.append(f"\t\tformatString: {fmt}")
                lines.append("")
        lines.extend(
            [
                f"\tpartition '{table}' = m",
                "\t\tmode: import",
                "\t\tsource =",
                "\t\t\tlet",
                f'\t\t\t\tSource = WarehouseTable("{source}"),',
            ]
        )
        mtypes = {
            "decimal": "Currency.Type",
            "int64": "Int64.Type",
            "string": "type text",
            "boolean": "type logical",
            "dateTime": "type datetime",
        }
        types = ", ".join(
            f'{{"{column}", {mtypes[datatype]}}}' for column, datatype in columns.items()
        )
        lines.extend(
            [
                f"\t\t\t\tTyped = Table.TransformColumnTypes(Source, {{{types}}})",
                "\t\t\tin",
                "\t\t\t\tTyped",
                "",
            ]
        )
        write(MODEL / f"definition/tables/{table}.tmdl", "\n".join(lines))
    endpoints = [
        ("date_orders", "Orders", "purchase_date", "Date", "date"),
        ("date_cohorts", "Cohorts", "first_purchase_date", "Date", "date"),
        ("orders_items", "Items", "order_id", "Orders", "order_id"),
        ("product_items", "Items", "product_id", "Product", "product_id"),
        ("seller_items", "Items", "seller_id", "Seller", "seller_id"),
    ]
    relations = [
        {
            "name": name,
            "fromTable": from_table,
            "fromColumn": from_column,
            "toTable": to_table,
            "toColumn": to_column,
            "isActive": True,
            "fromCardinality": "many",
            "toCardinality": "one",
            "crossFilteringBehavior": "oneDirection",
        }
        for name, from_table, from_column, to_table, to_column in endpoints
    ]
    lines = []
    for relation in relations:
        lines.extend(
            [
                f"relationship {relation['name']}",
                f"\tfromColumn: '{relation['fromTable']}'.'{relation['fromColumn']}'",
                f"\ttoColumn: '{relation['toTable']}'.'{relation['toColumn']}'",
                f"\tfromCardinality: {relation['fromCardinality']}",
                f"\ttoCardinality: {relation['toCardinality']}",
                f"\tcrossFilteringBehavior: {relation['crossFilteringBehavior']}",
                "",
            ]
        )
    write(MODEL / "definition/relationships.tmdl", "\n".join(lines))
    write(
        ROOT / "model_contract.json",
        {
            "tables": {
                name: {"source": source, "columns": columns}
                for name, (source, columns) in TABLES.items()
            },
            "measures": list(MEASURES),
            "money_storage": "TOM Decimal / M Currency.Type (fixed decimal)",
            "relations": relations,
        },
    )


def field(table, name, is_measure=False):
    return {
        "Measure" if is_measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": name,
        }
    }


def col(table, name):
    return table, name, False


def met(name):
    return "Orders", name, True


def literal(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = str(value) + "D"
    return {"expr": {"Literal": {"Value": value}}}


def formatting(title):
    return {
        "title": [
            {
                "properties": {
                    "show": literal(True),
                    "text": literal(title),
                    "fontSize": literal(12),
                    "fontColor": {"solid": {"color": literal("#19324A")}},
                }
            }
        ],
        "background": [
            {
                "properties": {
                    "show": literal(True),
                    "color": {"solid": {"color": literal("#FFFFFF")}},
                    "transparency": literal(0),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": literal(True),
                    "color": {"solid": {"color": literal("#E1E7ED")}},
                    "radius": literal(6),
                }
            }
        ],
    }


def visual(page, name, kind, title, roles, position, note=""):
    query_state = {}
    for role, refs in roles.items():
        query_state[role] = {
            "projections": [
                {"field": field(*ref), "queryRef": f"{ref[0]}.{ref[1]}", "nativeQueryRef": ref[1]}
                for ref in refs
            ]
        }
    config = {
        "visualType": kind,
        "visualContainerObjects": formatting(title),
        "drillFilterOtherVisuals": False,
    }
    if roles:
        config["query"] = {"queryState": query_state}
    if kind == "slicer":
        config["objects"] = {
            "data": [
                {
                    "properties": {
                        "mode": literal(
                            "Between"
                            if roles.get("Values") == [col("Date", "date")]
                            else "Dropdown"
                        )
                    }
                }
            ],
            "selection": [{"properties": {"singleSelect": literal(False)}}],
        }
    if kind in {"lineChart", "clusteredColumnChart", "clusteredBarChart"}:
        config["objects"] = {
            "legend": [{"properties": {"show": literal(True)}}],
            "valueAxis": [{"properties": {"show": literal(True)}}],
            "categoryAxis": [{"properties": {"show": literal(True)}}],
        }
        if "Category" in roles:
            config["query"]["sortDefinition"] = {
                "sort": [{"field": field(*roles["Category"][0]), "direction": "Ascending"}],
                "isDefaultSort": False,
            }
    if kind == "textbox":
        config["objects"] = {
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": title,
                                        "textStyle": {
                                            "fontFamily": "Segoe UI",
                                            "fontSize": "12pt" if name == "scope" else "14pt",
                                            "color": "#19324A",
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        config["visualContainerObjects"]["title"] = [{"properties": {"show": literal(False)}}]
    if kind == "card":
        config["objects"] = {
            "labels": [
                {
                    "properties": {
                        "fontSize": literal(13 if name == "mode" else 24),
                        "labelDisplayUnits": literal(0),
                    }
                }
            ],
            "categoryLabels": [{"properties": {"show": literal(False)}}],
        }
    payload = {
        "$schema": SCHEMAS["visual"],
        "name": name,
        "position": {
            "x": position[0],
            "y": position[1],
            "z": position[4] if len(position) > 4 else 0,
            "width": position[2],
            "height": position[3],
            "tabOrder": len(page["visuals"]),
        },
        "visual": config,
        "annotations": [{"name": "RetailLensScope", "value": note or title}],
        "howCreated": "Default",
    }
    write(REPORT / f"definition/pages/{page['name']}/visuals/{name}/visual.json", payload)
    page["visuals"].append((name, kind))
    return name


def page(name, title, subtitle):
    p = {"name": name, "title": title, "visuals": []}
    visual(p, "heading", "textbox", f"RetailLens / {title}", {}, (20, 12, 1240, 45))
    visual(
        p,
        "scope",
        "textbox",
        subtitle + " Blank ratio/AOV = no eligible denominator.",
        {},
        (20, 64, 1240, 62),
    )
    visual(
        p,
        "month",
        "slicer",
        "Purchase / first purchase date",
        {"Values": [col("Date", "date")]},
        (20, 138, 300, 65),
    )
    visual(
        p,
        "mode",
        "card",
        "Data mode / source version",
        {"Values": [met("Selected Data Mode")]},
        (1040, 138, 220, 65),
    )
    return p


def cards(p, names):
    for i, name in enumerate(names):
        visual(p, f"kpi_{i}", "card", name, {"Values": [met(name)]}, (20 + i * 315, 220, 295, 112))


def table(p, name, title, refs, position, note=""):
    return visual(p, name, "tableEx", title, {"Values": refs}, position, note)


def finish(p, nofilter_targets=(), special_sources=()):
    interactions = []
    interactive = [
        name
        for name, kind in p["visuals"]
        if kind in {"slicer", "lineChart", "clusteredColumnChart", "clusteredBarChart", "tableEx"}
    ]
    for source in interactive:
        for target, kind in p["visuals"]:
            if target == source or kind == "textbox":
                continue
            # Provenance and quality snapshots are global. Cohort date selection is
            # allowed; order/status/segment selections must not alter repeat KPI.
            action = "DataFilter"
            if (
                target in nofilter_targets
                or target == "mode"
                or (source in special_sources and target == "seller_delivery")
            ):
                action = "NoFilter"
            if target.startswith("cohort_") or target == "kpi_3" and p["name"] == "overview":
                action = "DataFilter" if source in {"month", "cohort_table"} else "NoFilter"
            interactions.append({"source": source, "target": target, "type": action})
    filters = [
        {
            "name": p["name"] + "_date",
            "field": field("Date", "date"),
            "type": "Range",
            "howCreated": "User",
        }
    ]
    if p["name"] == "quality":
        filters += [
            {
                "name": "quality_order_lookup",
                "field": field("Orders", "order_id"),
                "type": "Categorical",
                "howCreated": "User",
            },
            {
                "name": "quality_status",
                "field": field("Orders", "order_status"),
                "type": "Categorical",
                "howCreated": "User",
            },
        ]
    write(
        REPORT / f"definition/pages/{p['name']}/page.json",
        {
            "$schema": SCHEMAS["page"],
            "name": p["name"],
            "displayName": p["title"],
            "displayOption": "FitToPage",
            "height": 1000,
            "width": 1280,
            "visualInteractions": interactions,
            "filterConfig": {"filters": filters},
            "objects": {
                "background": [
                    {
                        "properties": {
                            "color": {"solid": {"color": literal("#F3F6F9")}},
                            "transparency": literal(0),
                        }
                    }
                ]
            },
            "annotations": [
                {
                    "name": "FilterContract",
                    "value": "Date filters purchase and first-purchase dates. Single-direction relationships. Explicit interactions; see powerbi/README.md.",
                }
            ],
        },
    )


def report():
    write(
        ROOT / "RetailLens.pbip",
        {
            "$schema": SCHEMAS["pbip"],
            "version": "1.0",
            "artifacts": [{"report": {"path": "RetailLens.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write(
        REPORT / "definition.pbir",
        {
            "$schema": SCHEMAS["pbir"],
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../RetailLens.SemanticModel"}},
        },
    )
    write(REPORT / "definition/version.json", {"$schema": SCHEMAS["version"], "version": "2.0.0"})
    write(
        REPORT / "definition/report.json",
        {
            "$schema": SCHEMAS["report"],
            "themeCollection": {
                "baseTheme": {
                    "name": "CY26SU02",
                    "reportVersionAtImport": {
                        "visual": "2.9.0",
                        "page": "2.1.0",
                        "report": "3.3.0",
                    },
                    "type": "SharedResources",
                }
            },
            "annotations": [
                {
                    "name": "RetailLens",
                    "value": "BRL. Import model. Mode is selected by DataMode parameter; credentials remain local.",
                }
            ],
        },
    )
    p = page(
        "overview",
        "Overview",
        "Delivered merchandise value in BRL; excludes freight. Repeat = first observed delivered purchase, full assumed 90-day window. Seller/category filters do not affect repeat. Boundary months are descriptive, excluded from period comparisons.",
    )
    cards(p, ["Delivered GMV", "Delivered AOV", "GMV Eligible Orders", "Observed Repeat 90d Rate"])
    visual(
        p,
        "gmv_trend",
        "lineChart",
        "Delivered GMV / purchase month (BRL)",
        {"Category": [col("Date", "year_month")], "Y": [met("Delivered GMV")]},
        (20, 348, 610, 240),
    )
    visual(
        p,
        "orders_trend",
        "clusteredColumnChart",
        "Eligible delivered orders / purchase month",
        {"Category": [col("Date", "year_month")], "Y": [met("GMV Eligible Orders")]},
        (650, 348, 610, 240),
    )
    table(
        p,
        "cohort_table",
        "Repeat cohorts: denominator, successes and excluded windows",
        [
            col("Date", "year_month"),
            met("Eligible Cohort Customers"),
            met("Repeat 90d Customers"),
            met("Observed Repeat 90d Rate"),
            met("Incomplete Cohort Windows"),
            met("Same Timestamp Additional Orders"),
        ],
        (20, 604, 790, 200),
    )
    table(
        p,
        "populations",
        "Order populations (selected purchase dates)",
        [
            met("Order Count"),
            met("Delivered Order Count"),
            met("Nondelivered Orders"),
            met("GMV Excluded Delivered Orders"),
            met("Delivery Excluded Orders"),
        ],
        (830, 604, 430, 200),
    )
    table(
        p,
        "provenance",
        "Pinned input and assumed observation boundary (global snapshot)",
        [
            col("Run", "data_mode"),
            col("Run", "source_version"),
            col("Run", "analysis_start"),
            col("Run", "analysis_end_exclusive"),
            col("Run", "observation_end"),
            col("Run", "observation_basis"),
        ],
        (20, 820, 1240, 160),
    )
    finish(p, {"provenance"})
    p = page(
        "deliveries",
        "Deliveries and reviews",
        "On time compares source calendar days; missing or inconsistent dates are excluded, never treated as late. Review analysis uses one latest valid answer per order; tied conflicting answers are excluded. Group sizes and coverage accompany scores; associations do not establish causality.",
    )
    visual(
        p,
        "state",
        "slicer",
        "Customer state (order location)",
        {"Values": [col("Orders", "customer_state")]},
        (340, 138, 310, 65),
    )
    visual(
        p,
        "timing",
        "slicer",
        "On time flag (eligible orders only in KPIs)",
        {"Values": [col("Orders", "is_on_time")]},
        (670, 138, 350, 65),
    )
    cards(p, ["On Time Rate", "Delivery Eligible Orders", "Mean Late Days", "Review Coverage"])
    visual(
        p,
        "timing_state",
        "clusteredBarChart",
        "On-time rate by customer state",
        {"Category": [col("Orders", "customer_state")], "Y": [met("On Time Rate")]},
        (20, 348, 610, 240),
    )
    visual(
        p,
        "review_distribution",
        "clusteredColumnChart",
        "Selected review score distribution (order count)",
        {"Category": [col("Orders", "review_score")], "Y": [met("Reviewed Delivery Orders")]},
        (650, 348, 610, 240),
    )
    table(
        p,
        "review_groups",
        "Timing groups: eligible n, reviewed n, coverage and score",
        [
            col("Orders", "is_on_time"),
            met("Delivery Eligible Orders"),
            met("Reviewed Delivery Orders"),
            met("Review Coverage"),
            met("Mean Review Score"),
        ],
        (20, 604, 1240, 190),
    )
    table(
        p,
        "excluded",
        "Separately reported exclusions and missing observations",
        [
            met("Delivery Excluded Orders"),
            met("Nondelivered Orders"),
            met("Ambiguous Review Orders"),
            met("Unreviewed Delivery Orders"),
        ],
        (20, 812, 1240, 168),
    )
    finish(p)
    p = page(
        "segments",
        "Sellers and categories",
        "Segment value sums eligible items, not whole-order AOV or allocated payments. Seller delivery/review metrics use single-seller orders only and ignore product/category selection; the global multi-seller exclusion is shown. Product and seller filters change segment value; repeat is absent here.",
    )
    visual(
        p,
        "category",
        "slicer",
        "Product category",
        {"Values": [col("Product", "category")]},
        (340, 138, 310, 65),
    )
    visual(
        p,
        "seller",
        "slicer",
        "Seller ID",
        {"Values": [col("Seller", "seller_id")]},
        (670, 138, 350, 65),
    )
    cards(
        p,
        [
            "Delivered Segment Item Value",
            "Segment Item Value Per Order",
            "Segment Eligible Orders",
            "Multi Seller Delivery Exclusions",
        ],
    )
    visual(
        p,
        "category_value",
        "clusteredBarChart",
        "Delivered item value by category (BRL)",
        {"Category": [col("Product", "category")], "Y": [met("Delivered Segment Item Value")]},
        (20, 348, 610, 240),
    )
    table(
        p,
        "category_share",
        "Category share and segment value per order",
        [
            col("Product", "category"),
            met("Delivered Segment Item Value"),
            met("Segment Value Share"),
            met("Segment Eligible Orders"),
            met("Segment Item Value Per Order"),
        ],
        (650, 348, 610, 240),
    )
    table(
        p,
        "seller_value",
        "Seller item value (seller grain)",
        [
            col("Seller", "seller_id"),
            col("Seller", "seller_state"),
            met("Delivered Segment Item Value"),
            met("Segment Value Share"),
            met("Segment Eligible Orders"),
        ],
        (20, 604, 1240, 165),
    )
    table(
        p,
        "seller_delivery",
        "Single-seller orders only: eligible n, on-time rate and review coverage",
        [
            col("Seller", "seller_id"),
            met("Single Seller Delivery Orders"),
            met("Single Seller On Time Rate"),
            met("Single Seller Reviewed Orders"),
            met("Single Seller Review Coverage"),
            met("Single Seller Mean Review"),
        ],
        (20, 786, 1240, 194),
    )
    finish(p, {"kpi_3"}, {"category", "category_value", "category_share"})
    p = page(
        "quality",
        "Data quality",
        "Global quality counts may overlap across rules. Date/status/order filters apply to order diagnostics, not the global import snapshot. Expected = items + freight; paid = payments summed before joins. Delta is not automatically loss/refund. All statuses remain available for diagnosis.",
    )
    visual(
        p,
        "reconciliation",
        "slicer",
        "Reconciliation status",
        {"Values": [col("Orders", "reconciliation_status")]},
        (340, 138, 310, 65),
    )
    visual(
        p,
        "order_lookup",
        "slicer",
        "Find order ID (enable Search in slicer menu)",
        {"Values": [col("Orders", "order_id")]},
        (670, 138, 350, 65),
    )
    cards(
        p,
        [
            "Payment Matched Rate",
            "Mismatch Delivered Orders",
            "Not Comparable Delivered Share",
            "Reported Quality Rule Occurrences",
        ],
    )
    table(
        p,
        "quality_rules",
        "Global snapshot: rejected / missing / ambiguous rows, by rule",
        [
            col("Quality", "check_name"),
            col("Quality", "severity"),
            col("Quality", "affected_rows"),
            col("Quality", "details"),
        ],
        (20, 348, 1240, 230),
    )
    table(
        p,
        "payment_groups",
        "Delivered reconciliation populations (selected dates)",
        [
            met("Matched Delivered Orders"),
            met("Mismatch Delivered Orders"),
            met("Not Comparable Delivered Orders"),
            met("Not Comparable Delivered Share"),
        ],
        (20, 595, 1240, 112),
    )
    table(
        p,
        "order_diagnostics",
        "Order diagnostics: select a status / order above or use Filters pane",
        [
            col("Orders", "order_id"),
            col("Orders", "order_status"),
            col("Orders", "reconciliation_status"),
            col("Orders", "expected_amount"),
            col("Orders", "paid_amount"),
            col("Orders", "payment_delta"),
            col("Orders", "missing_price_count"),
            col("Orders", "missing_freight_count"),
            col("Orders", "missing_payment_count"),
            col("Orders", "review_ambiguous"),
        ],
        (20, 724, 1240, 164),
    )
    table(
        p,
        "quality_provenance",
        "Global import: tolerance BRL, timestamp and source manifest SHA256",
        [
            col("Run", "reconciliation_tolerance"),
            col("Run", "imported_at"),
            col("Run", "source_manifest_sha256"),
        ],
        (20, 905, 1240, 75),
    )
    finish(p, {"kpi_3", "quality_rules", "quality_provenance"})
    write(
        REPORT / "definition/pages/pages.json",
        {
            "$schema": SCHEMAS["pages"],
            "pageOrder": ["overview", "deliveries", "segments", "quality"],
            "activePageName": "overview",
        },
    )


def main():
    model()
    report()
    print(f"Authored {len(TABLES)} tables, {len(MEASURES)} measures, four pages")


if __name__ == "__main__":
    main()

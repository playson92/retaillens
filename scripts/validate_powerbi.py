"""Offline Microsoft JSON-schema and semantic-reference checks for RetailLens.

This intentionally does not execute DAX, refresh Power Query or inspect rendered UI.
The official TOM TMDL parser is a separate gate: scripts/parse_tmdl.ps1.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PB = ROOT / "powerbi"


def walk(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def validate(check_postgres=False, mode="real"):
    errors = []
    manifest = json.loads((PB / "schemas/manifest.json").read_text(encoding="utf-8"))
    registry = Registry()
    schemas = {}
    for url, entry in manifest["files"].items():
        payload = (PB / "schemas" / entry["file"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            errors.append(f"Pinned schema checksum mismatch: {entry['file']}")
        schema = json.loads(payload)
        schemas[url] = schema
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(url, resource)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
    contract = json.loads((PB / "model_contract.json").read_text(encoding="utf-8"))
    tables = contract["tables"]
    measures = set()
    actual_columns = {}
    dax = []
    for path in sorted((PB / "RetailLens.SemanticModel/definition/tables").glob("*.tmdl")):
        if path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append(f"UTF-8 BOM is forbidden: {path.relative_to(PB)}")
        source = path.read_text(encoding="utf-8")
        name = re.search(r"^table '([^']+)'", source).group(1)
        actual_columns[name] = set(re.findall(r"^\tcolumn '([^']+)'", source, re.M))
        found = re.findall(r"^\tmeasure '([^']+)' = (.*)$", source, re.M)
        measures.update(name for name, _ in found)
        dax.extend(found)
        if name not in tables or actual_columns[name] != set(tables[name]["columns"]):
            errors.append(f"TMDL column inventory differs from contract: {name}")
        actual_types = dict(
            re.findall(r"^\tcolumn '([^']+)'\n\t\tdataType: ([^\n]+)$", source, re.M)
        )
        if actual_types != tables[name]["columns"]:
            errors.append(f"TMDL data types differ from contract: {name}")
        if f'WarehouseTable("{tables[name]["source"]}")' not in source:
            errors.append(f"Incorrect Power Query source: {name}")
        if "mode: import" not in source:
            errors.append(f"Expected Import partition: {name}")
    if measures != set(contract["measures"]):
        errors.append("TMDL measure inventory differs from model contract")
    for name, expression in dax:
        for table, column in re.findall(r"'([^']+)'\[([^]]+)\]", expression):
            if column not in actual_columns.get(table, set()):
                errors.append(f"DAX column reference {table}[{column}] missing in {name}")
        without_columns = re.sub(r"'([^']+)'\[([^]]+)\]", "", expression)
        for dependency in re.findall(r"\[([^]]+)\]", without_columns):
            if dependency not in measures:
                errors.append(f"DAX measure dependency [{dependency}] missing in {name}")
    paths = [
        PB / "RetailLens.pbip",
        PB / "RetailLens.Report/definition.pbir",
        PB / "RetailLens.SemanticModel/definition.pbism",
    ]
    paths += sorted((PB / "RetailLens.Report/definition").rglob("*.json"))
    documents = {}
    refs_count = 0
    for path in paths:
        relative = path.relative_to(PB).as_posix()
        payload = path.read_bytes()
        if payload.startswith(b"\xef\xbb\xbf"):
            errors.append(f"UTF-8 BOM is forbidden: {relative}")
        document = json.loads(payload)
        documents[relative] = document
        schema_url = document.get("$schema")
        if schema_url not in schemas:
            errors.append(f"Missing pinned official schema: {relative} {schema_url}")
            continue
        validator = Draft7Validator(schemas[schema_url], registry=registry)
        for error in validator.iter_errors(document):
            errors.append(f"{relative}:{'/'.join(map(str, error.absolute_path))}: {error.message}")
        for node in walk(document):
            if not isinstance(node, dict):
                continue
            for kind in ("Column", "Measure"):
                reference = node.get(kind)
                if not isinstance(reference, dict) or "Property" not in reference:
                    continue
                source = reference.get("Expression", {}).get("SourceRef", {}).get("Entity")
                prop = reference["Property"]
                refs_count += 1
                if kind == "Column" and prop not in actual_columns.get(source, set()):
                    errors.append(f"Unresolved visual column: {relative}: {source}[{prop}]")
                if kind == "Measure" and (source != "Orders" or prop not in measures):
                    errors.append(f"Unresolved visual measure: {relative}: {source}[{prop}]")
    project = documents["RetailLens.pbip"]
    if project["artifacts"][0]["report"]["path"] != "RetailLens.Report":
        errors.append("PBIP report path mismatch")
    bypath = documents["RetailLens.Report/definition.pbir"]["datasetReference"]["byPath"]["path"]
    if (PB / "RetailLens.Report" / bypath).resolve() != (PB / "RetailLens.SemanticModel").resolve():
        errors.append("PBIR model path does not resolve to local semantic model")
    pages = documents["RetailLens.Report/definition/pages/pages.json"]
    if pages["pageOrder"] != ["overview", "deliveries", "segments", "quality"]:
        errors.append("Expected four ordered MVP pages")
    if pages["activePageName"] not in pages["pageOrder"]:
        errors.append("Active page missing")
    visual_count = 0
    roles_by_type = {
        "card": {"Values"},
        "slicer": {"Values"},
        "tableEx": {"Values"},
        "lineChart": {"Category", "Y"},
        "clusteredColumnChart": {"Category", "Y"},
        "clusteredBarChart": {"Category", "Y"},
    }
    for page_name in pages["pageOrder"]:
        prefix = f"RetailLens.Report/definition/pages/{page_name}/"
        page = documents[prefix + "page.json"]
        if page["name"] != page_name:
            errors.append(f"Page identifier mismatch: {page_name}")
        visuals = {}
        for relative, doc in documents.items():
            if relative.startswith(prefix + "visuals/") and relative.endswith("/visual.json"):
                visual_count += 1
                name = doc["name"]
                if name in visuals or name != Path(relative).parent.name:
                    errors.append(f"Invalid/duplicate visual identifier: {relative}")
                visuals[name] = doc
                position = doc["position"]
                if (
                    min(position["x"], position["y"], position["width"], position["height"]) < 0
                    or position["x"] + position["width"] > page["width"]
                    or position["y"] + position["height"] > page["height"]
                ):
                    errors.append(f"Visual outside page: {relative}")
                config = doc["visual"]
                kind = config["visualType"]
                state = config.get("query", {}).get("queryState", {})
                if kind != "textbox" and not roles_by_type.get(kind, set()).issubset(state):
                    errors.append(f"Missing native visual roles: {relative}")
                refs = [item["queryRef"] for role in state.values() for item in role["projections"]]
                if len(refs) != len(set(refs)):
                    errors.append(f"Duplicate queryRef: {relative}")
        interactions = page["visualInteractions"]
        pairs = {(i["source"], i["target"]) for i in interactions}
        if len(pairs) != len(interactions):
            errors.append(f"Duplicate interactions: {page_name}")
        for source, target in pairs:
            if source not in visuals or target not in visuals:
                errors.append(f"Unknown interaction target/source: {page_name}:{source}->{target}")
        for source, doc in visuals.items():
            if doc["visual"]["visualType"] in {
                "slicer",
                "lineChart",
                "clusteredColumnChart",
                "clusteredBarChart",
                "tableEx",
            }:
                for target, target_doc in visuals.items():
                    if (
                        source != target
                        and target_doc["visual"]["visualType"] != "textbox"
                        and (source, target) not in pairs
                    ):
                        errors.append(f"Undefined interaction: {page_name}:{source}->{target}")
        date_field = visuals["month"]["visual"]["query"]["queryState"]["Values"]["projections"][0][
            "field"
        ]
        if (
            date_field["Column"]["Property"] != "date"
            or date_field["Column"]["Expression"]["SourceRef"]["Entity"] != "Date"
        ):
            errors.append(f"Date slicer must bind Date[date]: {page_name}")
    for _, from_table, from_column, to_table, to_column in contract["relations"]:
        if (
            from_column not in actual_columns[from_table]
            or to_column not in actual_columns[to_table]
        ):
            errors.append("Invalid relationship reference")
    postgres = {
        "status": "NOT_RUN",
        "reason": "Use --postgres to compare imported SQL columns and dimension keys.",
    }
    if check_postgres:
        from psycopg import sql

        from retaillens.config import Settings

        with Settings(mode=mode).connect() as connection:
            with connection.cursor() as cursor:
                for name, spec in tables.items():
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s",
                        (f"rl_{mode}", spec["source"]),
                    )
                    columns = {row[0] for row in cursor.fetchall()}
                    missing = set(spec["columns"]) - columns
                    if missing:
                        errors.append(f"SQL columns missing for {name}: {sorted(missing)}")
                for name, key in [
                    ("Orders", "order_id"),
                    ("Date", "date"),
                    ("Product", "product_id"),
                    ("Seller", "seller_id"),
                ]:
                    cursor.execute(
                        sql.SQL(
                            "SELECT count(*),count({key}),count(DISTINCT {key}) FROM {schema}.{table}"
                        ).format(
                            key=sql.Identifier(key),
                            schema=sql.Identifier(f"rl_{mode}"),
                            table=sql.Identifier(tables[name]["source"]),
                        )
                    )
                    total, present, distinct = cursor.fetchone()
                    if total != present or total != distinct:
                        errors.append(f"One-side relationship key not unique/non-null: {name}")
        postgres = {"status": "PASS" if not errors else "FAIL", "mode": mode}
    return {
        "check": "PBIP_SCHEMA",
        "status": "FAIL" if errors else "PASS",
        "official_schema_commit": manifest["commit"],
        "json_files": len(paths),
        "pinned_schemas": len(schemas),
        "tables": len(tables),
        "measures": len(measures),
        "pages": len(pages["pageOrder"]),
        "visuals": visual_count,
        "field_references": refs_count,
        "postgres_contract": postgres,
        "errors": errors,
        "runtime_checks": {
            name: "NOT_RUN"
            for name in ["DESKTOP_OPEN", "DATA_REFRESH", "DAX_RUNTIME_RECONCILIATION", "VISUAL_QA"]
        },
        "scope": "Official JSON schemas, UTF-8, paths, field references, native query roles, layout bounds, explicit interactions and static DAX dependencies; not runtime execution.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--mode", choices=["real", "synthetic"], default="real")
    args = parser.parse_args()
    result = validate(args.postgres, args.mode)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()

"""Regressions for actual model relationships and exact prepared-project checks."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from powerbi import build_definitions
from scripts import validate_powerbi

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "powerbi"
RELATIONSHIPS = Path("RetailLens.SemanticModel/definition/relationships.tmdl")
TOM_LIBRARY = (
    ROOT / "output/tools/tom-19.117.0/package/lib/net472/Microsoft.AnalysisServices.Tabular.dll"
)


@pytest.fixture
def project_copy(tmp_path):
    project = tmp_path / "prepared"
    project.mkdir()
    for folder in ("RetailLens.Report", "RetailLens.SemanticModel"):
        shutil.copytree(SOURCE / folder, project / folder, ignore=shutil.ignore_patterns(".pbi"))
    shutil.copy2(SOURCE / "RetailLens.pbip", project / "RetailLens.pbip")
    return project


def mutate_relationship(project, mutation):
    path = project / RELATIONSHIPS
    text = path.read_text(encoding="utf-8")
    if mutation == "missing_file":
        path.unlink()
        return
    if mutation == "inactive":
        text = text.replace(
            "relationship date_orders\n", "relationship date_orders\n\tisActive: false\n", 1
        )
    elif mutation == "timestamp_endpoint":
        text = text.replace("'Orders'.'purchase_date'", "'Orders'.'purchase_timestamp'", 1)
    elif mutation == "wrong_from_table":
        text = text.replace("'Orders'.'purchase_date'", "'Items'.'purchase_date'", 1)
    elif mutation == "wrong_to_column":
        text = text.replace("'Date'.'date'", "'Date'.'year'", 1)
    elif mutation == "from_cardinality":
        text = text.replace("fromCardinality: many", "fromCardinality: one", 1)
    elif mutation == "to_cardinality":
        text = text.replace("toCardinality: one", "toCardinality: many", 1)
    elif mutation == "both_directions":
        text = text.replace(
            "crossFilteringBehavior: oneDirection", "crossFilteringBehavior: bothDirections", 1
        )
    elif mutation == "automatic_direction":
        text = text.replace(
            "crossFilteringBehavior: oneDirection", "crossFilteringBehavior: automatic", 1
        )
    elif mutation == "missing_relationship":
        text = text.partition("\n\n")[2]
    elif mutation in {"extra_relationship", "duplicate_relationship"}:
        first = text.partition("\n\n")[0]
        if mutation == "extra_relationship":
            first = first.replace("date_orders", "unexpected_date_orders", 1)
        text += "\n\n" + first + "\n"
    else:
        raise ValueError(mutation)
    path.write_text(text, encoding="utf-8")


NEGATIVE_CASES = [
    ("missing_file", "Missing actual relationships.tmdl"),
    ("inactive", "date_orders.isActive"),
    ("timestamp_endpoint", "date_orders.fromColumn"),
    ("wrong_from_table", "date_orders.fromTable"),
    ("wrong_to_column", "date_orders.toColumn"),
    ("from_cardinality", "date_orders.fromCardinality"),
    ("to_cardinality", "date_orders.toCardinality"),
    ("both_directions", "date_orders.crossFilteringBehavior"),
    ("automatic_direction", "date_orders.crossFilteringBehavior"),
    ("missing_relationship", "Missing actual relationship: date_orders"),
    ("extra_relationship", "Unexpected actual relationship: unexpected_date_orders"),
    ("duplicate_relationship", "Duplicate actual relationship: date_orders"),
]


@pytest.mark.parametrize("as_file", [False, True])
def test_exact_prepared_project_is_valid(project_copy, as_file):
    argument = project_copy / "RetailLens.pbip" if as_file else project_copy
    result = validate_powerbi.validate(project=argument)
    assert result["status"] == "PASS", result["errors"]
    assert result["project"] == str(project_copy.resolve())
    assert result["relationship_contract"]["actual_count"] == 5
    assert result["relationship_contract"]["status"] == "PASS"
    assert not (project_copy / "schemas").exists()  # Canonical pinned validation resources.


def test_explicit_pbip_argument_validates_that_file_not_a_sibling(project_copy):
    original = project_copy / "RetailLens.pbip"
    selected = project_copy / "Reviewed.pbip"
    shutil.copy2(original, selected)
    document = json.loads(original.read_text(encoding="utf-8"))
    document["artifacts"][0]["report"]["path"] = "Unrelated.Report"
    original.write_text(json.dumps(document), encoding="utf-8")
    result = validate_powerbi.validate(project=selected)
    assert result["status"] == "PASS", result["errors"]
    assert result["project_file"] == str(selected.resolve())
    assert validate_powerbi.validate(project=original)["status"] == "FAIL"


@pytest.mark.parametrize(("mutation", "error_fragment"), NEGATIVE_CASES)
def test_actual_relationship_corruptions_fail(project_copy, mutation, error_fragment):
    original = (SOURCE / RELATIONSHIPS).read_bytes()
    mutate_relationship(project_copy, mutation)
    result = validate_powerbi.validate(project=project_copy)
    assert result["status"] == "FAIL"
    assert result["relationship_contract"]["status"] == "FAIL"
    assert any(error_fragment in error for error in result["errors"]), result["errors"]
    assert (SOURCE / RELATIONSHIPS).read_bytes() == original


def omit_defaults(project):
    path = project / RELATIONSHIPS
    text = path.read_text(encoding="utf-8")
    for property_line in (
        "\tfromCardinality: many\n",
        "\ttoCardinality: one\n",
        "\tcrossFilteringBehavior: oneDirection\n",
    ):
        text = text.replace(property_line, "")
    path.write_text(text, encoding="utf-8")


def test_omitted_tmdl_properties_use_official_defaults(project_copy):
    omit_defaults(project_copy)
    result = validate_powerbi.validate(project=project_copy)
    assert result["status"] == "PASS", result["errors"]
    for actual in result["relationship_contract"]["actual"]:
        assert actual["isActive"] is True
        assert actual["fromCardinality"] == "many"
        assert actual["toCardinality"] == "one"
        assert actual["crossFilteringBehavior"] == "oneDirection"


def test_incomplete_expected_relationship_contract_cannot_disable_checks(project_copy):
    contract = json.loads((SOURCE / "model_contract.json").read_text(encoding="utf-8"))
    del contract["relations"][0]["isActive"]
    columns = {name: set(spec["columns"]) for name, spec in contract["tables"].items()}
    errors = []
    result = validate_powerbi.compare_relationships(project_copy, contract, columns, errors)
    assert result["status"] == "FAIL"
    assert any("Incomplete or unsupported relationship contract" in error for error in errors)


@pytest.mark.parametrize("mutation", ["missing_file", "inactive", "timestamp_endpoint"])
def test_review_cases_cli_returns_failure(project_copy, mutation):
    mutate_relationship(project_copy, mutation)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_powerbi.py"), "--project", str(project_copy)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["status"] == "FAIL"


def test_generator_preserves_relationship_definitions_and_full_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(build_definitions, "ROOT", tmp_path)
    monkeypatch.setattr(build_definitions, "MODEL", tmp_path / "RetailLens.SemanticModel")
    build_definitions.model()
    generated = json.loads((tmp_path / "model_contract.json").read_text(encoding="utf-8"))
    canonical = json.loads((SOURCE / "model_contract.json").read_text(encoding="utf-8"))
    assert generated == canonical
    assert (tmp_path / RELATIONSHIPS).read_text(encoding="utf-8") == (
        SOURCE / RELATIONSHIPS
    ).read_text(encoding="utf-8")
    assert all(relation["isActive"] is True for relation in generated["relations"])


@pytest.mark.skipif(
    os.name != "nt" or not TOM_LIBRARY.is_file(),
    reason="Official TOM net472 parser needs Windows and local pinned NuGet assemblies",
)
@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "omitted_defaults",
        "missing_file",
        "inactive",
        "timestamp_endpoint",
        "from_cardinality",
        "to_cardinality",
        "both_directions",
    ],
)
def test_official_tom_checks_actual_relationship_contract(project_copy, mutation):
    if mutation == "omitted_defaults":
        omit_defaults(project_copy)
    elif mutation != "none":
        mutate_relationship(project_copy, mutation)
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/parse_tmdl.ps1"),
            "-ProjectPath",
            str(project_copy / "RetailLens.pbip"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    output = json.loads(result.stdout)
    if mutation in {"none", "omitted_defaults"}:
        assert result.returncode == 0, output
        assert output["status"] == "PASS"
        assert output["relationship_contract"]["status"] == "PASS"
    else:
        assert result.returncode == 1, output
        assert output["status"] == "FAIL"

import json
import shutil
from pathlib import Path

import pytest
from scripts.prepare_report import prepare_report

from retaillens.config import Settings, resolve_connection

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("use_environment", [True, False])
def test_pipeline_and_report_share_connection_precedence(tmp_path, monkeypatch, use_environment):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_HOST=file-host\nDATABASE_PORT=5433\nDATABASE_NAME=file-db\n"
        "DATABASE_USER=fixture-user\nDATABASE_PASSWORD=fixture-password\n",
        encoding="utf-8",
    )
    environment = (
        {"DATABASE_HOST": "process-host", "DATABASE_PORT": "6433", "DATABASE_NAME": 'process"db'}
        if use_environment
        else {}
    )
    expected = (
        {"host": "process-host", "port": "6433", "dbname": 'process"db'}
        if use_environment
        else {"host": "file-host", "port": "5433", "dbname": "file-db"}
    )
    resolved = resolve_connection(env_file=env_file, environ=environment)
    assert {key: resolved[key] for key in expected} == expected
    observed = {}
    monkeypatch.setattr("retaillens.config.resolve_connection", lambda: resolved)
    monkeypatch.setattr(
        "retaillens.config.psycopg.connect", lambda **kwargs: observed.update(kwargs)
    )
    Settings().connect()
    assert {key: observed[key] for key in expected} == expected
    project = prepare_report(
        "synthetic", output_root=tmp_path / "prepared", env_file=env_file, environ=environment
    )
    text = (project.parent / "RetailLens.SemanticModel/definition/expressions.tmdl").read_text()
    for param, key in [("ServerHost", "host"), ("ServerPort", "port"), ("DatabaseName", "dbname")]:
        literal = expected[key].replace('"', '""')
        assert f'expression {param} = "{literal}"' in text
    for path in project.parent.rglob("*"):
        if path.is_file():
            assert b"fixture-password" not in path.read_bytes()


def test_connection_defaults_do_not_mutate_environment(tmp_path):
    environment = {}
    resolved = resolve_connection(env_file=tmp_path / "missing.env", environ=environment)
    assert resolved == {
        "host": "127.0.0.1",
        "port": "5433",
        "dbname": "retaillens",
        "user": "retaillens_app",
        "password": "",
    }
    assert environment == {}


def test_report_copy_is_fresh_preserving_source_and_prior_desktop_edits(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ROOT / "powerbi", source)
    source_cache = source / "RetailLens.SemanticModel/.pbi/unappliedChanges.json"
    source_cache.parent.mkdir()
    source_cache.write_text('{"pending":"source editor state"}')
    output = tmp_path / "prepared"
    legacy = output / "real"
    orphan = legacy / "RetailLens.Report/definition/pages/overview/visuals/old/visual.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_text('{"user":"old visual edit"}')
    pending = legacy / "RetailLens.SemanticModel/.pbi/unappliedChanges.json"
    pending.parent.mkdir(parents=True)
    pending.write_text('{"user":"old pending query edit"}')
    before_source = {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    before_legacy = {
        p.relative_to(legacy): p.read_bytes() for p in legacy.rglob("*") if p.is_file()
    }
    first = prepare_report(
        "real", source=source, output_root=output, env_file=tmp_path / "no.env", environ={}
    )
    second = prepare_report(
        "real", source=source, output_root=output, env_file=tmp_path / "no.env", environ={}
    )
    assert first != second
    for project in [first, second]:
        assert project.is_file()
        assert not list(project.parent.rglob(".pbi"))
        assert not list(project.parent.rglob("old"))
        prep = json.loads((project.parent / "preparation.json").read_text())
        validation = json.loads((project.parent / "validation.json").read_text())
        assert prep["status"] == validation["status"] == "PASS"
        assert prep["project"] == str(project)
        assert prep["parameters"]["DataMode"] == "real"
    assert {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    } == before_source
    for relative, data in before_legacy.items():
        assert (legacy / relative).read_bytes() == data

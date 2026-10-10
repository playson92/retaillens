"""Regression coverage for configured Portable endpoints and exact Desktop sources."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scripts import check_docker_results as capture
from scripts import local_postgres
from scripts.prepare_report import prepare_report
from scripts.resolve_powerbi_connection import resolved_source

from retaillens.portable import assert_data_directory, inspect_portable, local_parameters

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = {
    "host": "127.0.0.1",
    "port": "5434",
    "dbname": "retaillens",
    "user": "fixture-user",
    "password": "fixture-password",
}


class Connection:
    def __init__(self, directory):
        self.directory = directory
        self.statements = []
        self.closed = False

    def execute(self, sql, *args):
        self.statements.append(sql)
        return self

    def fetchone(self):
        if self.statements[-1] == "SHOW data_directory":
            return (self.directory,)
        return ("PostgreSQL 17.6",)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_windows_data_directory_comparison_is_case_and_separator_aware():
    connection = Connection("c:/PROJECTS/RetailLens/output/postgres_data")
    assert assert_data_directory(connection, r"C:\projects\retaillens\output\postgres_data")
    with pytest.raises(ValueError, match="not the preserved"):
        assert_data_directory(connection, r"C:\projects\other\output\postgres_data")


@pytest.mark.parametrize("host", ["remote.example", "127.0.0.2", "127.0.0.1.evil"])
def test_portable_rejects_nonallowlisted_endpoint_before_connect(host):
    with pytest.raises(ValueError, match="explicitly local"):
        local_parameters({**PARAMETERS, "host": host})


def test_inspection_uses_configured_port_and_read_only_identity(monkeypatch):
    conn = Connection(r"C:\projects\retaillens\output\postgres_data")
    connect = Mock(return_value=conn)
    monkeypatch.setattr("retaillens.portable.psycopg.connect", connect)
    proof = inspect_portable(PARAMETERS, r"C:\projects\retaillens\output\postgres_data")
    assert connect.call_args.kwargs["port"] == "5434"
    assert connect.call_args.kwargs["options"] == "-c default_transaction_read_only=on"
    assert conn.statements[0].startswith("SET TRANSACTION")
    assert conn.statements[1] == "SHOW data_directory"
    assert proof["port"] == 5434 and proof["read_only"] and conn.closed


def test_foreign_authenticated_server_cannot_reach_database_creation(monkeypatch):
    conn = Connection(r"C:\foreign\postgres_data")
    monkeypatch.setattr(local_postgres.psycopg, "connect", Mock(return_value=conn))
    with pytest.raises(ValueError, match="not the preserved"):
        local_postgres.ensure_database(
            {
                "DATABASE_HOST": PARAMETERS["host"],
                "DATABASE_PORT": PARAMETERS["port"],
                "DATABASE_NAME": PARAMETERS["dbname"],
                "DATABASE_USER": PARAMETERS["user"],
                "DATABASE_PASSWORD": PARAMETERS["password"],
            }
        )
    assert conn.statements == ["SHOW data_directory"] and conn.closed


def test_standalone_capture_rejects_foreign_server_before_reading_marts(tmp_path, monkeypatch):
    conn = Connection(r"C:\foreign\postgres_data")
    connect = Mock(return_value=conn)
    monkeypatch.setattr(capture, "resolve_connection", lambda: PARAMETERS)
    monkeypatch.setattr(capture.psycopg, "connect", connect)
    with pytest.raises(ValueError, match="not the preserved"):
        capture.capture_portable(tmp_path / "new")
    assert connect.call_args.kwargs["port"] == "5434"
    assert conn.statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        "SHOW data_directory",
    ]
    assert conn.closed


def test_running_owned_cluster_on_configured_port_is_not_restarted(tmp_path, monkeypatch):
    binary = tmp_path / "output/tools/postgres17/pgsql/bin/pg_ctl.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("existing")
    cluster = tmp_path / "output/postgres_data"
    cluster.mkdir()
    (cluster / "postmaster.pid").write_text("123\nowned\n1\n5434\n")
    env = {
        "DATABASE_" + key: value
        for key, value in zip(
            ["HOST", "PORT", "NAME", "USER", "PASSWORD"], PARAMETERS.values(), strict=True
        )
    }
    calls = []
    monkeypatch.setattr(local_postgres, "ROOT", tmp_path)
    monkeypatch.setattr(local_postgres, "private_env", lambda: env)
    monkeypatch.setattr(local_postgres, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(sys, "argv", ["local_postgres.py", "start"])
    monkeypatch.setattr(
        local_postgres,
        "run",
        lambda args, **kwargs: calls.append(args) or subprocess.CompletedProcess(args, 0),
    )
    identity = Mock()
    database = Mock()
    monkeypatch.setattr(local_postgres, "inspect_portable", identity)
    monkeypatch.setattr(local_postgres, "ensure_database", database)
    local_postgres.main()
    assert len(calls) == 1 and calls[0][-1] == "status"
    assert identity.call_args.args[0]["port"] == "5434"
    database.assert_called_once_with(env)


def test_report_and_desktop_guard_resolve_same_settings_without_exposing_credentials(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_HOST=127.0.0.1\nDATABASE_PORT=5434\nDATABASE_NAME=retaillens\n"
        "DATABASE_USER=fixture-user\nDATABASE_PASSWORD=fixture-password\n"
    )
    endpoint = resolved_source(env_file, environ={})
    assert endpoint["resource_path"] == "127.0.0.1:5434;retaillens"
    assert "fixture-password" not in json.dumps(endpoint)
    project = prepare_report(
        "real", output_root=tmp_path / "reports", env_file=env_file, environ={}
    )
    prepared = json.loads((project.parent / "preparation.json").read_text())
    assert prepared["parameters"]["ServerPort"] == "5434"
    assert resolved_source(env_file, environ={"DATABASE_PORT": "5534"})["port"] == 5534


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows PowerShell guard regression")
def test_powershell_guards_accept_configured_source_and_reject_stale_or_modified_select(tmp_path):
    guard = str(ROOT / "scripts/powerbi_source_guard.ps1").replace("'", "''")
    program = (
        f". '{guard}'; $path='127.0.0.1:5434;retaillens'; "
        "$results=@("
        "(Test-RetailLensCredentialSource 'PostgreSQL' $path $path),"
        "(Test-RetailLensCredentialSource 'PostgreSQL' '127.0.0.1:5433;retaillens' $path),"
        "(Test-RetailLensCredentialSource 'SQLServer' $path $path),"
        "(Test-RetailLensQuerySource ($path+[Environment]::NewLine+'SELECT * FROM rl_real.mart_orders') 'rl_real' $path),"
        "(Test-RetailLensQuerySource ('127.0.0.1:5433;retaillens'+[Environment]::NewLine+'SELECT * FROM rl_real.mart_orders') 'rl_real' $path),"
        "(Test-RetailLensQuerySource ($path+[Environment]::NewLine+'SELECT * FROM rl_real.mart_orders; DROP TABLE x') 'rl_real' $path)"
        ");$results | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", program],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True, False, False, True, False, False]


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows PowerShell process guard")
@pytest.mark.parametrize(
    "script,extra",
    [
        ("authenticate_powerbi_local.ps1", ["-DialogHandle", "1"]),
        ("approve_powerbi_local_queries.ps1", ["-Schema", "rl_real"]),
    ],
)
def test_desktop_helpers_reject_non_desktop_process(script, extra):
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / script),
            "-ProcessId",
            str(__import__("os").getpid()),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "authorized" in result.stderr or "Credential control" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows PowerShell settings resolver")
def test_powershell_source_resolver_honors_settings_path_and_environment(tmp_path, monkeypatch):
    settings = tmp_path / "private settings.env"
    settings.write_text("DATABASE_HOST=127.0.0.1\nDATABASE_PORT=5434\nDATABASE_NAME=retaillens\n")
    guard = str(ROOT / "scripts/powerbi_source_guard.ps1").replace("'", "''")
    location = str(settings).replace("'", "''")
    monkeypatch.setenv("DATABASE_PORT", "5534")
    program = f". '{guard}'; Get-RetailLensPowerBIConnection -SettingsPath '{location}' | ConvertTo-Json -Compress"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", program],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    proof = json.loads(result.stdout)
    assert proof["resource_path"] == "127.0.0.1:5534;retaillens"
    assert "password" not in proof

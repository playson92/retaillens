"""Exercise failure/cleanup orchestration without claiming container runtime execution."""

import importlib.util
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "docker_verification", Path(__file__).resolve().parents[1] / "scripts/verify_docker.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeDocker:
    def __init__(
        self,
        *,
        fail=None,
        daemon=True,
        failure_output=None,
        leftovers=False,
        endpoint="npipe:////./pipe/dockerDesktopLinuxEngine",
        os_type="linux",
    ):
        self.fail, self.daemon = fail, daemon
        self.failure_output = failure_output
        self.leftovers = leftovers
        self.endpoint, self.os_type = endpoint, os_type
        self.calls = []
        self.verification = None

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        v = self.verification
        code, output = 0, ""
        if "config" in args and "json" in args:
            output = json.dumps(
                {
                    "name": v.project,
                    "services": {
                        "app": {
                            "image": v.image,
                            "environment": {"DATABASE_HOST": "db", "DATABASE_PORT": "5432"},
                            "volumes": [
                                {"target": "/app/data/raw", "read_only": True},
                                {"target": "/app/output", "source": str(v.output)},
                            ],
                        },
                        "db": {
                            "ports": [
                                {"published": str(v.port), "host_ip": "127.0.0.1", "target": 5432}
                            ],
                            "volumes": [{"source": "data"}],
                        },
                    },
                    "volumes": {"data": {"name": v.project + "_data"}},
                    "private": v.connection["password"],
                }
            )
        elif "context" in args and "inspect" in args:
            output = json.dumps(self.endpoint)
        elif "info" in args:
            code, output = (0, self.os_type) if self.daemon else (124, "TIMEOUT")
        elif "image" in args:
            output = "sha256:" + "a" * 64
        elif "ps" in args and self.leftovers:
            output = "0123456789ab"
        elif "stop" in args and "--time" in args:
            self.leftovers = False
        elif "-0.01" in args:
            code = 1
            output = (
                self.failure_output
                if self.failure_output is not None
                else json.dumps(
                    {"status": "FAIL", "error": "Tolerance must be a finite nonnegative Decimal"}
                )
            )
        if self.fail and all(part in args for part in self.fail):
            code, output = 17, "Native operation failed"
        return subprocess.CompletedProcess(args, code, output.encode())


@pytest.fixture
def make_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "free_port", lambda port: port)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        module,
        "resolve_connection",
        lambda: {
            "host": "127.0.0.1",
            "port": "5433",
            "dbname": "retaillens",
            "user": "app",
            "password": "private-test-value",
        },
    )

    def make(**kwargs):
        fake = FakeDocker(**kwargs)
        verification = module.Verification(
            tmp_path / "run", "docker.exe", "desktop-linux", 6433, executor=fake
        )
        fake.verification = verification
        monkeypatch.setattr(verification, "pinned_input", lambda: verification.gate("PINNED_INPUT"))
        monkeypatch.setattr(verification, "ensure_portable", lambda: None)
        return verification, fake

    return make


def test_child_configuration_does_not_change_parent(make_verification, monkeypatch):
    monkeypatch.setenv("DATABASE_PORT", "5433")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "another-project")
    monkeypatch.setenv("COMPOSE_FILE", "another-compose.yml")
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    before = os.environ.copy()
    v, _ = make_verification()
    assert os.environ == before
    assert v.env["DATABASE_PORT"] == "6433"
    assert v.env["COMPOSE_PROJECT_NAME"] != "another-project"
    assert "COMPOSE_FILE" not in v.env and "DOCKER_HOST" not in v.env
    assert v.compose[v.compose.index("--project-name") + 1] == v.project
    mounts = json.loads(v.override.read_text())["services"]["app"]["volumes"]
    assert mounts[0]["read_only"] and mounts[1]["source"] == str(v.output)


def test_full_scenario_uses_built_image_and_checks_both_cleanup_paths(make_verification):
    v, fake = make_verification()
    assert v.execute() == 0
    assert v.report["status"] == "PASS"
    assert v.report["image_id"] == "sha256:" + "a" * 64
    assert v.report["gates"]["CLEANUP_RUNTIME"]["status"] == "PASS"
    args = [call[0] for call in fake.calls]
    assert sum("stop" in command and "compose" in command for command in args) == 2
    runs = [command for command in args if "run" in command and "compose" in command]
    assert len(runs) == 3 and all("--pull" in command and "never" in command for command in runs)
    real = next(command for command in runs if "real" in command)
    assert "2018-09-01" in real and "/app/data/raw/olist-v2" in real
    assert not any("down" in command or "-v" in command for command in args)


@pytest.mark.parametrize(
    "fail", [("build", "app"), ("up", "db"), ("demo", "real"), ("--mode", "--reference", "real")]
)
def test_native_failure_is_not_masked_by_cleanup_success(make_verification, fail):
    v, fake = make_verification(fail=fail)
    assert v.execute() == 1
    assert v.report["status"] == "FAIL"
    assert any("exit17" in error for error in v.report["errors"])
    assert any("stop" in call[0] for call in fake.calls)
    assert v.report["commands"][-1]["actual_exit_code"] == 0
    assert v.report["gates"]["INTENTIONAL_FAILURE"]["status"] == "NOT_RUN"
    if "real" in fail:
        assert v.report["gates"]["COMPOSE_DEMO"]["status"] == "FAIL"
        expected = "FAIL" if "--reference" in fail else "PARTIAL"
        assert v.report["gates"]["RESULT_RECONCILIATION"]["status"] == expected


def test_cleanup_failure_is_not_masked_by_final_empty_listing(make_verification):
    v, _ = make_verification(fail=("compose", "stop"))
    assert v.execute() == 1
    assert v.report["gates"]["CLEANUP_SUCCESS"]["status"] == "FAIL"
    assert any("Compose stop exit17" in error for error in v.report["errors"])


def test_daemon_absence_does_not_claim_build_demo_or_cleanup(make_verification):
    v, fake = make_verification(daemon=False)
    assert v.execute() == 2
    assert v.report["status"] == "BLOCKED"
    for gate in ("DOCKER_BUILD", "COMPOSE_DEMO", "CLEANUP_RUNTIME"):
        assert v.report["gates"][gate]["status"] == "NOT_RUN"
    assert sum("info" in args for args, _ in fake.calls) == 3
    assert not any("build" in args or "up" in args or "stop" in args for args, _ in fake.calls)


def test_expected_failure_requires_application_signature(make_verification):
    v, _ = make_verification(
        failure_output="Error response from daemon: failed to create container"
    )
    assert v.execute() == 1
    assert v.report["gates"]["INTENTIONAL_FAILURE"]["status"] == "FAIL"
    assert v.report["gates"]["CLEANUP_FAILURE"]["status"] == "PASS"
    assert any("did not prove" in error for error in v.report["errors"])


@pytest.mark.parametrize(
    "settings", [{"endpoint": "tcp://remote.example:2375"}, {"os_type": "windows"}]
)
def test_executed_endpoint_or_platform_failure_is_not_labelled_not_run(make_verification, settings):
    v, fake = make_verification(**settings)
    assert v.execute() == 1
    assert v.report["gates"]["LINUX_DAEMON"]["status"] == "FAIL"
    assert v.report["gates"]["DOCKER_BUILD"]["status"] == "NOT_RUN"
    assert not any("build" in args or "up" in args for args, _ in fake.calls)


def test_cleanup_stops_only_project_filtered_leftovers(make_verification):
    v, fake = make_verification(leftovers=True)
    v.cleanup("SUCCESS")
    lists = [args for args, _ in fake.calls if "ps" in args]
    assert all(f"label=com.docker.compose.project={v.project}" in args for args in lists)
    stops = [args for args, _ in fake.calls if "--time" in args]
    assert stops == [[*v.cli, "stop", "--time", "20", "0123456789ab"]]


def test_raw_logs_redact_credentials_and_omit_config_output(make_verification):
    v, _ = make_verification()
    v.configure()
    v.command("REDACTION", ["safe"], private_output=False)
    for path in v.run.rglob("*.log"):
        assert v.connection["password"] not in path.read_text()
    assert "omitted" in (v.run / "logs/DOCKER_02_CONFIG_INSPECT.log").read_text()


def test_command_timeout_records_failure_and_original_exit(make_verification):
    v, _ = make_verification()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b"Partial output")

    v.executor = timeout
    code, output = v.command("TIMEOUT", ["docker", "info"], timeout=1)
    assert code == 124 and "Partial output" in output
    assert v.report["commands"][-1]["status"] == "FAIL"


def test_port_selection_preserves_portable_and_skips_occupied_port():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        available = module.free_port(port)
        assert available != port and available != 5433
    assert module.free_port(5433) != 5433


def test_portable_restart_requires_existing_cluster_and_binary(make_verification, monkeypatch):
    v, fake = make_verification()

    def refused(*args, **kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr(module.socket, "create_connection", refused)
    with pytest.raises(ValueError, match="no new database initialized"):
        module.Verification.ensure_portable(v)
    assert not fake.calls
    for relative in (
        "output/postgres_data/PG_VERSION",
        "output/tools/postgres17/pgsql/bin/postgres.exe",
    ):
        path = module.ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("existing")
    module.Verification.ensure_portable(v)
    command, options = fake.calls[-1]
    assert command[-1] == "start" and command[-2].endswith("local_postgres.py")
    assert options["env"] == v.original_env


def test_running_portable_is_not_restarted(make_verification, monkeypatch):
    v, fake = make_verification()
    from contextlib import nullcontext

    monkeypatch.setattr(module.socket, "create_connection", lambda *args, **kwargs: nullcontext())
    module.Verification.ensure_portable(v)
    assert not fake.calls

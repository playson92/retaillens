"""Run an isolated Docker acceptance scenario; retain volumes and every native exit code."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from retaillens.config import resolve_connection
from retaillens.source import FILES, sha256

ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "PORTABLE_REFERENCE",
    "PINNED_INPUT",
    "COMPOSE_CONFIG",
    "LINUX_DAEMON",
    "DOCKER_BUILD",
    "DATABASE_HEALTH",
    "SYNTHETIC_DEMO",
    "REAL_DEMO",
    "RESULT_RECONCILIATION",
    "CLEANUP_SUCCESS",
    "INTENTIONAL_FAILURE",
    "CLEANUP_FAILURE",
    "CLEANUP_RUNTIME",
    "COMPOSE_DEMO",
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def free_port(preferred):
    for port in range(preferred, min(preferred + 100, 65536)):
        if port == 5433:
            continue
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise ValueError("No free review port; Portable port5433 is excluded")


def command_text(raw):
    if raw.count(b"\x00") > len(raw) / 5:
        return raw.decode("utf-16le")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp852", errors="replace")


class Verification:
    def __init__(self, run, docker, context, port, *, executor=subprocess.run):
        self.run, self.docker, self.context = run, str(docker), context
        self.executor = executor
        self.port = free_port(port)
        self.project = f"retaillens-review-{run.name.lower()}-{uuid.uuid4().hex[:8]}"
        self.image = f"retaillens:{self.project}"
        self.connection = resolve_connection()
        if not self.connection["password"]:
            raise ValueError("Private DATABASE_PASSWORD is required")
        self.original_env = os.environ.copy()
        self.env = self.original_env.copy()
        for key in tuple(self.env):
            if key.startswith("COMPOSE_") or key in {"DOCKER_HOST", "DOCKER_CONTEXT"}:
                del self.env[key]
        self.env.update(
            DATABASE_HOST="127.0.0.1",
            DATABASE_PORT=str(self.port),
            DATABASE_NAME=self.connection["dbname"],
            DATABASE_USER=self.connection["user"],
            DATABASE_PASSWORD=self.connection["password"],
            COMPOSE_PROJECT_NAME=self.project,
        )
        self.override = run / "compose.review.json"
        self.output = run / "evidence" / "docker"
        self.reference = run / "evidence" / "docker_reference"
        self.output.mkdir(parents=True, exist_ok=True)
        write_json(
            self.override,
            {
                "services": {
                    "app": {
                        "image": self.image,
                        "volumes": [
                            {
                                "type": "bind",
                                "source": str(ROOT / "data/raw"),
                                "target": "/app/data/raw",
                                "read_only": True,
                            },
                            {"type": "bind", "source": str(self.output), "target": "/app/output"},
                        ],
                    }
                }
            },
        )
        self.cli = [self.docker, "--context", context]
        self.compose = [
            *self.cli,
            "compose",
            "--project-name",
            self.project,
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(ROOT / ".env"),
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(self.override),
        ]
        self.report = {
            "status": "IN_PROGRESS",
            "project": self.project,
            "host_port": self.port,
            "context": context,
            "image": self.image,
            "image_id": None,
            "portable_host": "127.0.0.1:5433",
            "volumes_preserved": True,
            "gates": {key: {"status": "NOT_RUN"} for key in GATES},
            "commands": [],
            "errors": [],
        }

    def redact(self, text):
        return text.replace(self.connection["password"], "[REDACTED]")

    def command(self, name, args, *, expected=0, timeout=30, env=None, private_output=False):
        started = time.monotonic()
        try:
            result = self.executor(
                args,
                cwd=ROOT,
                env=self.env if env is None else env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            code, raw = result.returncode, result.stdout
        except subprocess.TimeoutExpired as error:
            code, raw = 124, (error.stdout or b"") + b"\nTIMEOUT\n"
        except OSError as error:
            code, raw = 127, type(error).__name__.encode()
        output = self.redact(command_text(raw))
        entry = {
            "name": name,
            "command": args,
            "expected_exit_code": expected,
            "actual_exit_code": code,
            "status": "PASS" if code == expected else "FAIL",
            "seconds": round(time.monotonic() - started, 3),
            "checked_at_utc": datetime.now(UTC).isoformat(),
        }
        stem = f"DOCKER_{len(self.report['commands']) + 1:02d}_{name}"
        log = self.run / "logs" / f"{stem}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        entry["log"] = log.relative_to(self.run).as_posix()
        logged = (
            "Credential-bearing configuration output verified in memory; omitted.\n"
            if private_output
            else output
        )
        log.write_text(
            "COMMAND: "
            + json.dumps(args)
            + "\n"
            + logged
            + f"\nEXPECTED_EXIT_CODE: {expected}\nACTUAL_EXIT_CODE: {code}\n",
            encoding="utf-8",
        )
        write_json(log.with_suffix(".json"), entry)
        with (self.run / "verification.log").open("a", encoding="utf-8") as stream:
            stream.write(log.read_text(encoding="utf-8") + "\n")
        self.report["commands"].append(entry)
        print(f"{name}: {entry['status']} exit{code} (expected{expected})", flush=True)
        return code, output

    def checked(self, name, args, **kwargs):
        code, output = self.command(name, args, **kwargs)
        if code != kwargs.get("expected", 0):
            raise RuntimeError(f"{name} native exit{code}")
        return output

    def gate(self, name, status="PASS", **details):
        self.report["gates"][name] = {"status": status, **details}

    def configure(self):
        self.checked("COMPOSE_CONFIG", [*self.compose, "config", "--quiet"])
        data = json.loads(
            self.checked(
                "CONFIG_INSPECT", [*self.compose, "config", "--format", "json"], private_output=True
            )
        )
        app, db = data["services"]["app"], data["services"]["db"]
        mounts = {v["target"]: v for v in app["volumes"]}
        assert data["name"] == self.project and app["image"] == self.image
        assert mounts["/app/data/raw"].get("read_only") is True
        assert Path(mounts["/app/output"]["source"]).resolve() == self.output.resolve()
        assert len(db["ports"]) == 1 and str(db["ports"][0]["published"]) == str(self.port)
        assert db["ports"][0]["host_ip"] == "127.0.0.1" and db["ports"][0]["target"] == 5432
        assert app["environment"]["DATABASE_HOST"] == "db"
        assert str(app["environment"]["DATABASE_PORT"]) == "5432"
        volume = data["volumes"][db["volumes"][0]["source"]]
        assert volume["name"].startswith(self.project + "_") and not volume.get("external")
        self.gate(
            "COMPOSE_CONFIG",
            details="Actual quiet/JSON Compose parsing; isolated image, mounts, port and volume verified without credential output",
        )

    def pinned_input(self):
        directory = ROOT / "data/raw/olist-v2"
        source = json.loads((directory / "SOURCE.json").read_text(encoding="utf-8"))
        assert source["data_mode"] == "real" and source["source_version"] == "olist-v2"
        assert (
            source["official_url"] == "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
        )
        names = list(FILES.values())
        if (directory / "olist_geolocation_dataset.csv").exists():
            names.append("olist_geolocation_dataset.csv")
        files = []
        for name in names:
            checksum = sha256(directory / name)
            assert checksum == source["file_sha256"][name], f"Pinned input differs: {name}"
            files.append({"filename": name, "sha256": checksum})
        write_json(
            self.run / "evidence/docker_input.json",
            {"status": "PASS", "files": files, "read_only_mount": True},
        )
        self.gate("PINNED_INPUT", files=len(files))

    def daemon(self):
        self.gate("LINUX_DAEMON", "FAIL")
        endpoint = json.loads(
            self.checked(
                "CONTEXT_ENDPOINT",
                [
                    *self.cli,
                    "context",
                    "inspect",
                    self.context,
                    "--format",
                    "{{json .Endpoints.docker.Host}}",
                ],
                timeout=8,
            )
        )
        if not endpoint.startswith("npipe:////./pipe/"):
            raise ValueError("Only a local Windows Docker endpoint is authorized")
        for attempt in range(3):
            code, output = self.command(
                f"LINUX_DAEMON_{attempt + 1}",
                [*self.cli, "info", "--format", "{{.OSType}}"],
                timeout=8,
            )
            if code == 0:
                if output.strip() != "linux":
                    raise ValueError("The selected daemon is not Linux")
                self.gate("LINUX_DAEMON", endpoint=endpoint)
                return True
            if attempt < 2:
                time.sleep(2)
        self.gate(
            "LINUX_DAEMON",
            "FAIL",
            reason="Local Linux daemon unavailable after three bounded probes",
        )
        self.report["status"] = "BLOCKED"
        self.report["errors"].append(
            "Docker Linux daemon unavailable; inspect current WSL/Windows prerequisite evidence"
        )
        return False

    def cleanup(self, label):
        errors = []
        code, _ = self.command(
            f"STOP_{label}", [*self.compose, "stop", "--timeout", "20"], timeout=40
        )
        if code:
            errors.append(f"Compose stop exit{code}")
        selector = [
            *self.cli,
            "ps",
            "--filter",
            f"label=com.docker.compose.project={self.project}",
            "--format",
            "{{.ID}}",
        ]
        code, output = self.command(f"LEFTOVERS_{label}", selector, timeout=10)
        if code:
            errors.append(f"Owned container listing exit{code}")
        else:
            ids = output.split()
            if any(not re.fullmatch(r"[0-9a-f]{12,64}", value) for value in ids):
                errors.append("Invalid owned container identifier")
            elif ids:
                code, _ = self.command(
                    f"STOP_OWNED_{label}", [*self.cli, "stop", "--time", "20", *ids], timeout=45
                )
                if code:
                    errors.append(f"Owned container stop exit{code}")
        code, output = self.command(f"NO_RUNNING_{label}", selector, timeout=10)
        if code or output.strip():
            errors.append("Own project still running or final listing failed")
        self.gate(f"CLEANUP_{label}", "FAIL" if errors else "PASS", details=errors)
        if errors:
            raise RuntimeError("; ".join(errors))

    def phase(self, label, operation):
        try:
            operation()
        except Exception as error:
            self.report["errors"].append(self.redact(f"{type(error).__name__}: {error}"))
        finally:
            try:
                self.cleanup(label)
            except Exception as error:
                self.report["errors"].append(self.redact(f"{type(error).__name__}: {error}"))

    def demos(self):
        self.gate("DOCKER_BUILD", "FAIL")
        self.checked("BUILD", [*self.compose, "build", "app"], timeout=1200)
        image_id = self.checked(
            "IMAGE_ID",
            [*self.cli, "image", "inspect", self.image, "--format", "{{.Id}}"],
            timeout=10,
        ).strip()
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", image_id), "Missing built image identifier"
        self.report["image_id"] = image_id
        self.gate("DOCKER_BUILD", image_id=image_id)
        self.up()
        self.gate("COMPOSE_DEMO", "FAIL")
        for mode in ("synthetic", "real"):
            gate = mode.upper() + "_DEMO"
            self.gate(gate, "FAIL")
            args = [
                *self.compose,
                "run",
                "--rm",
                "--no-deps",
                "--pull",
                "never",
                "-T",
                "app",
                "demo",
                "--mode",
                mode,
                "--output",
                f"/app/output/{mode}",
            ]
            if mode == "real":
                args += ["--input", "/app/data/raw/olist-v2", "--observation-end", "2018-09-01"]
            self.checked(gate, args, timeout=1200)
            self.gate("RESULT_RECONCILIATION", "FAIL")
            self.checked(
                mode.upper() + "_RESULTS",
                [
                    sys.executable,
                    str(ROOT / "scripts/check_docker_results.py"),
                    "--mode",
                    mode,
                    "--actual",
                    str(self.output / mode / "analysis.json"),
                    "--reference",
                    str(self.reference / mode / "analysis.json"),
                    "--output",
                    str(self.output / f"{mode}_comparison.json"),
                ],
            )
            self.gate("RESULT_RECONCILIATION", "PARTIAL" if mode == "synthetic" else "PASS")
            self.gate(gate)
        self.gate("RESULT_RECONCILIATION")
        self.gate("COMPOSE_DEMO")

    def up(self):
        self.gate("DATABASE_HEALTH", "FAIL")
        self.checked(
            "DATABASE_HEALTH",
            [*self.compose, "up", "-d", "--wait", "--wait-timeout", "120", "--no-build", "db"],
            timeout=180,
        )
        self.gate("DATABASE_HEALTH")

    def ensure_portable(self):
        try:
            with socket.create_connection(("127.0.0.1", 5433), timeout=1):
                return
        except OSError:
            pass
        if self.connection["port"] != "5433":
            raise ValueError("Existing Portable startup must use configured port5433")
        cluster = ROOT / "output/postgres_data/PG_VERSION"
        binary = ROOT / "output/tools/postgres17/pgsql/bin/postgres.exe"
        if not cluster.is_file() or not binary.is_file():
            raise ValueError(
                "Preserved Portable cluster/binaries are unavailable; no new database initialized"
            )
        self.checked(
            "PORTABLE_START",
            [sys.executable, str(ROOT / "scripts/local_postgres.py"), "start"],
            env=self.original_env,
            timeout=60,
        )

    def expected_failure(self):
        self.up()
        self.gate("INTENTIONAL_FAILURE", "FAIL")
        output = self.checked(
            "INTENTIONAL_FAILURE",
            [
                *self.compose,
                "run",
                "--rm",
                "--no-deps",
                "--pull",
                "never",
                "-T",
                "app",
                "demo",
                "--mode",
                "synthetic",
                "--tolerance",
                "-0.01",
            ],
            expected=1,
            timeout=90,
        )
        application_errors = []
        for line in output.splitlines():
            try:
                application_errors.append(json.loads(line))
            except ValueError:
                continue
        expected = {"status": "FAIL", "error": "Tolerance must be a finite nonnegative Decimal"}
        if expected not in application_errors:
            raise ValueError("Exit1 did not prove the intended application tolerance rejection")
        self.gate(
            "INTENTIONAL_FAILURE",
            expected_exit_code=1,
            actual_exit_code=1,
            application_error=expected["error"],
        )

    def execute(self):
        try:
            self.gate("COMPOSE_CONFIG", "FAIL")
            self.configure()
            self.gate("PINNED_INPUT", "FAIL")
            self.pinned_input()
            self.gate("PORTABLE_REFERENCE", "FAIL")
            self.ensure_portable()
            self.checked(
                "PORTABLE_REFERENCE",
                [
                    sys.executable,
                    str(ROOT / "scripts/check_docker_results.py"),
                    "--capture-portable",
                    "--output",
                    str(self.reference),
                ],
                env=self.original_env,
                timeout=120,
            )
            self.gate("PORTABLE_REFERENCE")
            if self.daemon():
                self.phase("SUCCESS", self.demos)
                if not self.report["errors"]:
                    self.phase("FAILURE", self.expected_failure)
                cleanup = [
                    self.report["gates"]["CLEANUP_" + name]["status"]
                    for name in ("SUCCESS", "FAILURE")
                ]
                status = (
                    "FAIL"
                    if "FAIL" in cleanup
                    else "PASS"
                    if cleanup == ["PASS", "PASS"]
                    else "PARTIAL"
                )
                self.gate("CLEANUP_RUNTIME", status)
                self.report["status"] = "FAIL" if self.report["errors"] else "PASS"
        except Exception as error:
            self.report["errors"].append(self.redact(f"{type(error).__name__}: {error}"))
            self.report["status"] = "FAIL"
        finally:
            self.report["completed_at_utc"] = datetime.now(UTC).isoformat()
            for entry in self.report["gates"].values():
                if entry["status"] == "NOT_RUN":
                    entry["reason"] = (
                        "Earlier prerequisite did not complete; no runtime success claimed"
                    )
            write_json(self.run / "docker_verification.json", self.report)
        return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[self.report["status"]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--context", default="desktop-linux")
    parser.add_argument("--port", type=int, default=6433)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    run = (
        args.run or ROOT / "output/codex_runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    ).resolve()
    if not run.is_relative_to(ROOT / "output/codex_runs"):
        parser.error("Run directory must stay inside this project's output/codex_runs")
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged TCP port; Portable port5433 is always excluded")
    if (run / "docker_verification.json").exists() or (run / "compose.review.json").exists():
        parser.error(
            "This attempt already exists; omit --run to preserve it and create a fresh run"
        )
    run.mkdir(parents=True, exist_ok=True)
    if not (run / "manifest.json").exists():
        baseline = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        write_json(
            run / "manifest.json",
            {"run_id": run.name, "baseline_sha": baseline, "scope": "Docker runtime acceptance"},
        )
    try:
        verification = Verification(run, args.docker, args.context, args.port)
    except Exception as error:
        write_json(
            run / "docker_verification.json",
            {
                "status": "FAIL",
                "preflight_error_type": type(error).__name__,
                "gates": {
                    gate: {"status": "NOT_RUN", "reason": "Preflight failed before native commands"}
                    for gate in GATES
                },
            },
        )
        print(f"Docker preflight failed: {type(error).__name__}; evidence {run}")
        return 1
    code = verification.execute()
    print(f"Docker acceptance: {verification.report['status']}; evidence {run}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

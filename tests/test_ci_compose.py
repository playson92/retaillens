"""Use the real Compose parser to validate every CI step's inherited configuration.

These checks do not contact a daemon or claim container cleanup execution. The CI
Docker job separately exercises a deliberately failed demo and verifies stopped
services, with an always() cleanup step after any preceding job failure.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
DOCKER_JOB = WORKFLOW["jobs"]["docker"]
COMPOSE_STEPS = [step for step in DOCKER_JOB["steps"] if "docker compose " in step.get("run", "")]


def compose_command():
    executable = os.getenv("RETAILLENS_COMPOSE_BIN") or shutil.which("docker-compose")
    if executable:
        return [executable]
    if executable := shutil.which("docker"):
        return [executable, "compose"]
    pytest.skip("Real Compose CLI unavailable; set RETAILLENS_COMPOSE_BIN to run parser checks")


@pytest.mark.parametrize("step", COMPOSE_STEPS, ids=[step["name"] for step in COMPOSE_STEPS])
def test_compose_steps_resolve_config_with_only_inherited_ci_env(step, tmp_path):
    # Never fall back to the developer's private .env or process DATABASE_* values.
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("DATABASE_", "COMPOSE_"))
    }
    environment.update({name: str(value) for name, value in DOCKER_JOB.get("env", {}).items()})
    environment.update({name: str(value) for name, value in step.get("env", {}).items()})
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    result = subprocess.run(
        [
            *compose_command(),
            "--env-file",
            str(empty_env),
            "--file",
            str(ROOT / "docker-compose.yml"),
            "config",
            "--quiet",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cleanup_remains_unconditional_and_preserves_volumes():
    cleanup = next(
        step for step in COMPOSE_STEPS if step["name"] == "Stop services; preserve volumes"
    )
    assert cleanup["if"] == "always()"
    assert cleanup["run"].strip() == "docker compose stop"

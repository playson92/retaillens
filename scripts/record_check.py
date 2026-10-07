"""Record actual subprocess output and exit codes in the current implementation run."""

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Pass the command after --")
    run = (
        args.run
        or ROOT / "output/codex_runs" / (ROOT / "output/current_run.txt").read_text().strip()
    )
    if not run.resolve().is_relative_to((ROOT / "output/codex_runs").resolve()):
        raise ValueError("Evidence run must be inside this project's codex_runs")
    logs = run / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    safe_name = "".join(c for c in args.name if c.isalnum() or c in "_-")
    log = logs / f"{safe_name}_{stamp}.log"
    started = time.perf_counter()
    timed_out = False
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=args.timeout,
            check=False,
        )
        raw, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        raw, code, timed_out = error.stdout or b"", 124, True
    except OSError as error:
        raw, code = f"Cannot execute command: {type(error).__name__}".encode(), 127
    output = raw.decode(
        "utf-16le" if raw.count(b"\x00") > len(raw) / 5 else "utf-8", errors="replace"
    )
    secrets = [
        os.getenv("DATABASE_PASSWORD", ""),
        dotenv_values(ROOT / ".env").get("DATABASE_PASSWORD", ""),
    ]
    for private_value in secrets:
        if private_value:
            output = output.replace(private_value, "[REDACTED]")
    entry = {
        "name": args.name,
        "command": command,
        "started_at_utc": stamp,
        "exit_code": code,
        "timeout": timed_out,
        "seconds": round(time.perf_counter() - started, 3),
        "log": log.relative_to(run).as_posix(),
    }
    log.write_text(
        "COMMAND: " + json.dumps(command) + "\n" + output + f"\nEXIT_CODE: {code}\n",
        encoding="utf-8",
    )
    log.with_suffix(".json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    with (run / "verification.log").open("a", encoding="utf-8") as stream:
        stream.write(log.read_text(encoding="utf-8") + "\n")
    print(output, end="" if output.endswith("\n") else "\n")
    print(json.dumps(entry))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

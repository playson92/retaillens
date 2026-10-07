"""Prepare a private PBIP copy with host parameters, leaving authored definitions unchanged."""

import argparse
import re
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from retaillens.config import resolve_connection
from retaillens.source import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]


def prepare_report(mode="real", *, source=None, output_root=None, env_file=None, environ=None):
    """Return a newly validated PBIP, without merging or deleting any prior session."""
    if mode not in {"real", "synthetic"}:
        raise ValueError("Report mode must be real or synthetic")
    source = Path(source) if source else ROOT / "powerbi"
    parent = (Path(output_root) if output_root else ROOT / "output" / "powerbi") / mode
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=parent))
    for folder in ["RetailLens.Report", "RetailLens.SemanticModel"]:
        shutil.copytree(
            source / folder,
            target / folder,
            ignore=shutil.ignore_patterns(".pbi"),
        )
    shutil.copy2(source / "RetailLens.pbip", target / "RetailLens.pbip")
    env = resolve_connection(env_file=env_file, environ=environ)
    params = {
        "ServerHost": env["host"],
        "ServerPort": env["port"],
        "DatabaseName": env["dbname"],
        "DataMode": mode,
    }
    expressions = target / "RetailLens.SemanticModel" / "definition" / "expressions.tmdl"
    text = expressions.read_text(encoding="utf-8")
    for key, value in params.items():
        pattern = rf'(?m)^(expression {key} = )"(?:[^"\n]|"")*"( meta .*)$'
        literal = value.replace('"', '""')
        text, count = re.subn(
            pattern, lambda match, v=literal: match[1] + '"' + v + '"' + match[2], text
        )
        if count != 1:
            raise ValueError(f"Expected exactly one Power Query parameter {key}")
    expressions.write_text(text, encoding="utf-8")
    # The script entrypoint and importable helper share the same exact-project validator.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.validate_powerbi import validate

    validation = validate(mode=mode, project=target)
    write_json(target / "validation.json", validation)
    if validation["status"] != "PASS":
        raise ValueError(f"Prepared PBIP validation failed: {validation['errors']}")
    project = target / "RetailLens.pbip"
    files = {
        p.relative_to(target).as_posix(): sha256(p)
        for p in sorted(target.rglob("*"))
        if p.is_file()
    }
    write_json(
        target / "preparation.json",
        {
            "status": "PASS",
            "project": str(project.resolve()),
            "source": str(source.resolve()),
            "mode": mode,
            "parameters": params,
            "files_sha256": files,
            "previous_sessions": "preserved; no merge or cache reuse",
        },
    )
    return project.resolve()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--mode", choices=["real", "synthetic"], default="real")
    args = cli.parse_args()
    print(prepare_report(args.mode))


if __name__ == "__main__":
    main()

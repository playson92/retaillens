"""Prepare a private PBIP copy with host parameters, leaving authored definitions unchanged."""

import argparse
import re
import shutil
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--mode", choices=["real", "synthetic"], default="real")
    args = cli.parse_args()
    source = ROOT / "powerbi"
    target = ROOT / "output" / "powerbi" / args.mode
    target.mkdir(parents=True, exist_ok=True)
    for folder in ["RetailLens.Report", "RetailLens.SemanticModel"]:
        shutil.copytree(
            source / folder,
            target / folder,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".pbi"),
        )
    shutil.copy2(source / "RetailLens.pbip", target / "RetailLens.pbip")
    env = dotenv_values(ROOT / ".env")
    params = {
        "ServerHost": env.get("DATABASE_HOST", "127.0.0.1"),
        "ServerPort": env.get("DATABASE_PORT", "5433"),
        "DatabaseName": env.get("DATABASE_NAME", "retaillens"),
        "DataMode": args.mode,
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
    print(target / "RetailLens.pbip")


if __name__ == "__main__":
    main()

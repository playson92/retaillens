"""One reproducible command line from source files to report-ready warehouse."""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import psycopg

from retaillens.analysis import analyse, export_marts
from retaillens.config import Settings
from retaillens.download import download
from retaillens.fixture import make_fixture
from retaillens.source import profile, write_json
from retaillens.warehouse import ingest, quality, rebuild


def parser():
    cli = argparse.ArgumentParser(description="RetailLens: Olist -> PostgreSQL -> SQL/Power BI")
    cli.add_argument(
        "command",
        choices=[
            "fixture",
            "download",
            "profile",
            "import",
            "build",
            "quality",
            "analyse",
            "export",
            "demo",
        ],
    )
    cli.add_argument("--mode", choices=["real", "synthetic"], default="synthetic")
    cli.add_argument("--input", type=Path)
    cli.add_argument("--output", type=Path, default=Path("output/demo"))
    cli.add_argument("--version")
    cli.add_argument("--tolerance", type=Decimal, default=Decimal("0.01"))
    cli.add_argument("--start")
    cli.add_argument("--end", help="Exclusive analysis end date")
    cli.add_argument("--observation-end", help="Historical observation boundary, YYYY-MM-DD")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "fixture" and args.mode != "synthetic":
            raise ValueError("fixture requires --mode synthetic; real inputs are preserved")
        if args.command == "download" and args.mode != "real":
            raise ValueError("download requires --mode real")
        settings = Settings(args.mode, args.tolerance)
        version = args.version or ("fixture-v1" if args.mode == "synthetic" else "olist-v2")
        directory = args.input or Path(
            "data/sample" if args.mode == "synthetic" else "data/raw/olist-v2"
        )
        if args.command == "fixture":
            result = {"data_mode": "synthetic", "path": str(make_fixture(directory))}
        elif args.command == "download":
            result = {
                "data_mode": "real",
                "path": str(download(directory, int(version.removeprefix("olist-v")))),
            }
        elif args.command == "profile":
            result = profile(directory, args.mode, version)
            write_json(args.output / "profile.json", result)
        elif args.command == "import":
            result = ingest(settings, directory, version, args.observation_end)
            write_json(args.output / "source_manifest.json", result)
        elif args.command == "build":
            rebuild(settings)
            result = {"data_mode": args.mode, "models": "rebuilt"}
        elif args.command == "quality":
            result = quality(settings)
            write_json(args.output / "quality.json", result)
            if result["status"] != "PASS":
                print(json.dumps(result))
                return 1
        elif args.command == "analyse":
            result = analyse(settings, args.output, args.start, args.end)
        elif args.command == "export":
            result = export_marts(settings, args.output)
        else:
            if args.mode == "synthetic":
                make_fixture(directory)
            elif not (directory / "SOURCE.json").exists():
                download(directory, int(version.removeprefix("olist-v")))
            manifest = ingest(settings, directory, version, args.observation_end)
            write_json(args.output / "source_manifest.json", manifest)
            result = quality(settings)
            write_json(args.output / "quality.json", result)
            if result["status"] != "PASS":
                return 1
            evidence = analyse(settings, args.output, args.start, args.end)
            export_marts(settings, args.output / "marts")
            result = {
                "data_mode": args.mode,
                "source_version": version,
                "status": "PASS",
                "output": str(args.output),
                "overview": evidence["results"]["03_overview"],
            }
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 0
    except psycopg.Error as exc:
        # Exception strings may contain connection details; emit only type and SQLSTATE.
        print(
            json.dumps({"status": "FAIL", "error": type(exc).__name__, "sqlstate": exc.sqlstate}),
            file=sys.stderr,
        )
        return 1
    except (ValueError, FileNotFoundError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

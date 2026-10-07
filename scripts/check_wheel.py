"""Verify a normal wheel includes the CLI and the exact packaged SQL resources."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from retaillens.source import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("wheel", type=Path)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    with zipfile.ZipFile(args.wheel) as archive:
        assert archive.testzip() is None, "Wheel integrity failure"
        paths = archive.namelist()
        assert "retaillens/__main__.py" in paths, "CLI entrypoint missing"
        actual_sql = {
            Path(name).name: archive.read(name)
            for name in paths
            if ".data/data/share/retaillens/sql/" in name and name.endswith(".sql")
        }
        expected_sql = {path.name: path.read_bytes() for path in (ROOT / "sql").glob("*.sql")}
        assert actual_sql == expected_sql, "Wheel SQL differs from reviewed warehouse resources"
    result = {
        "status": "PASS",
        "wheel": str(args.wheel),
        "bytes": args.wheel.stat().st_size,
        "sha256": hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
        "cli": "retaillens/__main__.py",
        "sql_resources": sorted(actual_sql),
        "check": "ZIP CRC; CLI presence; packaged SQL bytes equal source SQL",
    }
    write_json(args.output, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

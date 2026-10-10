"""Resolve the private Desktop connection through the shared configuration resolver."""

import argparse
import json

from retaillens.config import resolve_connection
from retaillens.portable import local_parameters


def resolved_source(settings_path, *, environ=None, credentials=False):
    connection = local_parameters(resolve_connection(env_file=settings_path, environ=environ))
    result = {
        "resource_kind": "PostgreSQL",
        "resource_path": f"{connection['host']}:{connection['port']};{connection['dbname']}",
        "host": connection["host"],
        "port": int(connection["port"]),
        "database": connection["dbname"],
    }
    if credentials:
        result.update(user=connection["user"], password=connection["password"])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", required=True)
    parser.add_argument("--credentials", action="store_true")
    args = parser.parse_args()
    # Credential output is captured privately by the verified Desktop helper.
    # Never call this mode through a logging command runner.
    print(json.dumps(resolved_source(args.settings, credentials=args.credentials)))


if __name__ == "__main__":
    main()

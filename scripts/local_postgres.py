"""Optional isolated Windows PostgreSQL; no services, administrator install or volume deletion."""

import argparse
import hashlib
import os
import secrets
import socket
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import psycopg

from retaillens.config import resolve_connection
from retaillens.portable import assert_data_directory, inspect_portable, local_parameters

ROOT = Path(__file__).resolve().parents[1]
URL = "https://get.enterprisedb.com/postgresql/postgresql-17.6-1-windows-x64-binaries.zip"
DIGEST = "d378882abd001a186735acd6f6ba716bca6ccd192e800412d4fd15ed25376b3e"


def private_env():
    target = ROOT / ".env"
    if not target.exists():
        target.write_text(
            "DATABASE_HOST=127.0.0.1\nDATABASE_PORT=5433\nDATABASE_NAME=retaillens\n"
            "DATABASE_USER=retaillens_app\nDATABASE_PASSWORD=" + secrets.token_hex(32) + "\n",
            encoding="utf-8",
        )
    connection = local_parameters(resolve_connection(env_file=target))
    return {
        "DATABASE_" + name: connection[field]
        for name, field in [
            ("HOST", "host"),
            ("PORT", "port"),
            ("NAME", "dbname"),
            ("USER", "user"),
            ("PASSWORD", "password"),
        ]
    }


def run(command, *, check=True):
    # A detached Windows server can inherit pipes. Redirect to a file so pg_ctl can exit.
    with tempfile.TemporaryFile() as log:
        result = subprocess.run(
            command,
            stdout=log,
            stderr=log,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode and check:
            log.seek(0)
            raise RuntimeError(log.read().decode(errors="replace"))
        return result


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("command", choices=["start", "stop"])
    args = cli.parse_args()
    if os.name != "nt":
        raise SystemExit("Portable backend supports Windows; use Docker Compose on Linux")
    env = private_env()
    tools = ROOT / "output" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    binaries = tools / "postgres17" / "pgsql" / "bin"
    cluster = ROOT / "output" / "postgres_data"
    if args.command == "stop":
        run([str(binaries / "pg_ctl.exe"), "-D", str(cluster), "-m", "fast", "-w", "stop"])
        print("Stopped RetailLens portable PostgreSQL; cluster retained")
        return
    port = int(env["DATABASE_PORT"])
    if (binaries / "pg_ctl.exe").is_file():
        status = run([str(binaries / "pg_ctl.exe"), "-D", str(cluster), "status"], check=False)
        if status.returncode not in {0, 3}:
            raise ValueError("Unable to determine preserved Portable cluster status")
        if status.returncode == 0:
            actual_port = int((cluster / "postmaster.pid").read_text().splitlines()[3])
            actual = parameters(env, dbname="postgres", port=actual_port)
            inspect_portable(actual, cluster)
            if actual_port == port:
                ensure_database(env)
                print("RetailLens portable PostgreSQL already running; identity verified")
                return
            with socket.socket() as probe:
                if probe.connect_ex((env["DATABASE_HOST"], port)) == 0:
                    raise ValueError("Requested port occupied; preserved cluster was not stopped")
            run([str(binaries / "pg_ctl.exe"), "-D", str(cluster), "-m", "fast", "-w", "stop"])
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(
                f"Port {port} already occupied; preserve existing service and choose another port"
            )
    if not (binaries / "postgres.exe").exists():
        archive = tools / "postgresql-17.6.zip"
        if not archive.exists():
            urllib.request.urlretrieve(URL, archive)
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != DIGEST:
                raise SystemExit("PostgreSQL archive checksum mismatch")
        with zipfile.ZipFile(archive) as zipped:
            for name in zipped.namelist():
                path = PurePosixPath(name.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or ":" in name:
                    raise SystemExit("Unsafe PostgreSQL archive path")
            # Only the server/client binaries, shared data and libraries are necessary.
            for item in zipped.infolist():
                if item.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                    zipped.extract(item, tools / "postgres17")
    if not (cluster / "PG_VERSION").exists():
        password_file = tools / "initdb.password"
        password_file.write_text(env["DATABASE_PASSWORD"], encoding="utf-8")
        try:
            run(
                [
                    str(binaries / "initdb.exe"),
                    "-D",
                    str(cluster),
                    "-U",
                    env["DATABASE_USER"],
                    "--pwfile",
                    str(password_file),
                    "--auth-host=scram-sha-256",
                    "--auth-local=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
        finally:
            password_file.unlink(missing_ok=True)
    run(
        [
            str(binaries / "pg_ctl.exe"),
            "-D",
            str(cluster),
            "-l",
            str(ROOT / "output" / "postgres.log"),
            "-o",
            f"-h {env['DATABASE_HOST']} -p {port}",
            "-w",
            "start",
        ]
    )
    ensure_database(env)
    print(
        f"RetailLens PostgreSQL ready on {env['DATABASE_HOST']}:{port}; identity verified in output/postgres_data"
    )


def parameters(env, *, dbname=None, port=None):
    return {
        "host": env["DATABASE_HOST"],
        "port": str(port or env["DATABASE_PORT"]),
        "dbname": dbname or env["DATABASE_NAME"],
        "user": env["DATABASE_USER"],
        "password": env["DATABASE_PASSWORD"],
    }


def ensure_database(env):
    with psycopg.connect(
        host=env["DATABASE_HOST"],
        port=int(env["DATABASE_PORT"]),
        dbname="postgres",
        user=env["DATABASE_USER"],
        password=env["DATABASE_PASSWORD"],
        autocommit=True,
        connect_timeout=5,
    ) as connection:
        assert_data_directory(connection, ROOT / "output/postgres_data")
        from psycopg import sql

        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (env["DATABASE_NAME"],)
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(env["DATABASE_NAME"]))
            )


if __name__ == "__main__":
    main()

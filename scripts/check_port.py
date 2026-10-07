"""Do not start Compose over an unrelated service; a known Compose service is allowed."""

import socket
import subprocess

from local_postgres import private_env

env = private_env()
port = int(env["DATABASE_PORT"])
with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", port)) == 0:
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", "db"], capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            raise SystemExit(
                f"Port {port} occupied by another service; choose DATABASE_PORT in .env"
            )
print(f"Host port {port} available or owned by this Compose project")

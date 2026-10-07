"""Local configuration; credentials never enter manifests or exception output."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def resolve_connection(*, env_file=None, environ=None):
    """Resolve all clients consistently: process environment > local .env > defaults.

    Does not mutate os.environ. Callers must keep the password out of serialized evidence.
    """
    if env_file is None:
        candidate = ROOT / ".env"
        env_file = candidate if candidate.is_file() else Path.cwd() / ".env"
    values = dotenv_values(env_file, interpolate=False)
    process = os.environ if environ is None else environ
    defaults = {
        "host": ("DATABASE_HOST", "127.0.0.1"),
        "port": ("DATABASE_PORT", "5433"),
        "dbname": ("DATABASE_NAME", "retaillens"),
        "user": ("DATABASE_USER", "retaillens_app"),
        "password": ("DATABASE_PASSWORD", ""),
    }
    resolved = {
        field: process.get(key, values.get(key) or default)
        for field, (key, default) in defaults.items()
    }
    for field in ["host", "dbname", "user"]:
        if not resolved[field] or any(char in resolved[field] for char in "\r\n\x00"):
            raise ValueError(f"Invalid database configuration: {field}")
    try:
        if not 1 <= int(resolved["port"]) <= 65535:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid database configuration: port") from exc
    return resolved


@dataclass(frozen=True)
class Settings:
    mode: str = "synthetic"
    tolerance: Decimal = Decimal("0.01")

    def __post_init__(self):
        if self.mode not in {"real", "synthetic"}:
            raise ValueError("Data mode must be real or synthetic")
        if not self.tolerance.is_finite() or self.tolerance < 0:
            raise ValueError("Tolerance must be a finite nonnegative Decimal")

    @property
    def schema(self):
        return f"rl_{self.mode}"

    def connect(self):
        return psycopg.connect(
            **resolve_connection(),
            connect_timeout=10,
            application_name="retaillens",
        )

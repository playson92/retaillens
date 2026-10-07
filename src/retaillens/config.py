"""Local configuration; credentials never enter manifests or exception output."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


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
        source_env = ROOT / ".env"
        load_dotenv(source_env if source_env.is_file() else Path.cwd() / ".env", override=False)
        return psycopg.connect(
            host=os.getenv("DATABASE_HOST", "127.0.0.1"),
            port=os.getenv("DATABASE_PORT", "5433"),
            dbname=os.getenv("DATABASE_NAME", "retaillens"),
            user=os.getenv("DATABASE_USER", "retaillens_app"),
            password=os.getenv("DATABASE_PASSWORD", ""),
            connect_timeout=10,
            application_name="retaillens",
        )

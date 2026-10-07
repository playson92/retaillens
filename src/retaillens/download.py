"""Supported public Kaggle download with an explicit, immutable version handle."""

import json
from datetime import UTC, datetime
from pathlib import Path

from retaillens.source import sha256, write_json


def download(directory, version=2):
    import kagglehub

    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        provenance = directory / "SOURCE.json"
        if not provenance.exists():
            raise ValueError("Nonempty source directory without provenance; choose a new directory")
        existing = json.loads(provenance.read_text(encoding="utf-8"))
        if (
            existing.get("source_version") != f"olist-v{version}"
            or existing.get("data_mode") != "real"
        ):
            raise ValueError("Existing source has a different version; use a new directory")
        if not existing.get("file_sha256"):
            raise ValueError("Cached real source is missing pinned file checksums")
        for name, expected in existing["file_sha256"].items():
            if Path(name).name != name or sha256(directory / name) != expected:
                raise ValueError(f"Pinned source checksum mismatch: {name}")
        return directory
    kagglehub.dataset_download(
        f"olistbr/brazilian-ecommerce/versions/{version}", output_dir=str(directory)
    )
    write_json(
        directory / "SOURCE.json",
        {
            "data_mode": "real",
            "source_version": f"olist-v{version}",
            "official_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
            "handle": f"olistbr/brazilian-ecommerce/versions/{version}",
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
            "license": "CC BY-NC-SA 4.0",
            "license_reference": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
            "attribution": "Olist and collaborators, Brazilian E-Commerce Public Dataset by Olist",
            "file_sha256": {path.name: sha256(path) for path in sorted(directory.glob("*.csv"))},
        },
    )
    return directory

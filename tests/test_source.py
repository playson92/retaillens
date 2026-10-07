import json
from decimal import Decimal

import pytest

from retaillens.cli import main
from retaillens.config import Settings
from retaillens.fixture import make_fixture
from retaillens.source import FILES, convert, profile, sha256
from retaillens.warehouse import ingest, prepare_rows


@pytest.mark.parametrize("has_provenance", [True, False])
def test_fixture_never_overwrites_real_or_unknown_inputs(tmp_path, has_provenance):
    (tmp_path / "olist_orders_dataset.csv").write_text(
        "unrelated original content", encoding="utf-8"
    )
    if has_provenance:
        (tmp_path / "SOURCE.json").write_text(
            '{"data_mode":"real","source_version":"olist-v2"}', encoding="utf-8"
        )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="refuses to overwrite"):
        make_fixture(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert main(["demo", "--mode", "synthetic", "--input", str(tmp_path)]) == 1
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_cli_rejects_conflicting_source_modes_before_writing(tmp_path):
    assert main(["fixture", "--mode", "real", "--input", str(tmp_path)]) == 1
    assert main(["download", "--input", str(tmp_path)]) == 1
    assert list(tmp_path.iterdir()) == []


def test_real_import_rejects_modified_pinned_files_before_database_use(tmp_path, monkeypatch):
    source = make_fixture(tmp_path)
    provenance = {
        "data_mode": "real",
        "source_version": "olist-v2",
        "official_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "file_sha256": {name: sha256(source / name) for name in FILES.values()},
    }
    (source / "SOURCE.json").write_text(json.dumps(provenance), encoding="utf-8")
    orders = source / FILES["orders"]
    orders.write_text(orders.read_text().replace("o1", "modified-order"), encoding="utf-8")
    monkeypatch.setattr(
        Settings, "connect", lambda self: pytest.fail("Must validate before DB mutation")
    )
    with pytest.raises(ValueError, match="pinned SOURCE.json checksum"):
        ingest(Settings("real"), source, "olist-v2")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.001", "10000000000000000"])
def test_invalid_money_is_not_silently_rounded(value):
    with pytest.raises(ValueError):
        convert(value, "numeric(18,2)", "price")


def test_exact_money_and_source_timestamps():
    assert convert("10.01", "numeric(18,2)", "price") == Decimal("10.01")
    assert convert("2018-01-10 18:00:00", "timestamp", "date").tzinfo is None
    with pytest.raises(ValueError):
        convert("2018-01-10T18:00:00Z", "timestamp", "date")


def test_fixture_profile_is_reproducible(tmp_path):
    source = make_fixture(tmp_path / "fixture")
    a = profile(source, "synthetic", "fixture-v1")
    make_fixture(source)
    assert a == profile(source, "synthetic", "fixture-v1")
    orders = next(f for f in a["files"] if f["table"] == "orders")
    assert orders["rows"] == 8
    assert orders["date_min"] == "2018-01-01 10:00:00"
    assert orders["date_max"] == "2018-06-01 10:00:00"


def test_all_review_rows_are_retained(tmp_path):
    source = make_fixture(tmp_path)
    path = source / "olist_order_reviews_dataset.csv"
    raw, accepted, issues = prepare_rows("reviews", path, sha256(path))
    assert len(raw) == len(accepted) == 8
    assert issues == []


@pytest.mark.parametrize("mode", ["rl_real; DROP SCHEMA public", "test", ""])
def test_schema_is_allowlisted(mode):
    with pytest.raises(ValueError):
        Settings(mode)


@pytest.mark.parametrize("tolerance", ["NaN", "Infinity", "-0.01"])
def test_bad_tolerance(tolerance):
    with pytest.raises(ValueError):
        Settings(tolerance=Decimal(tolerance))

"""Tests for the project health check."""

from retaillens.health import health_check


def test_health_check_returns_ok_status() -> None:
    """Health check should report a successful status."""
    assert health_check() == {"status": "ok"}

"""Single source of server time. Services call clock.now(); tests monkeypatch it."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)

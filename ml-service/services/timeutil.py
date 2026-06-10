"""UTC datetime helpers.

The database stores naive datetimes that are UTC by convention, so every
timestamp written or compared must be naive UTC. These helpers replace the
deprecated datetime.utcnow() and centralize tz-aware -> naive conversion.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (DB storage convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Convert a possibly tz-aware datetime to naive UTC."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_to_naive_utc(value) -> datetime | None:
    """Parse an ISO string or datetime into naive UTC."""
    if value is None or isinstance(value, datetime):
        return to_naive_utc(value)
    if isinstance(value, str):
        return to_naive_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    return value

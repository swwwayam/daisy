"""Validated retention policy helpers shared by API and storage tests."""
from datetime import datetime, timedelta, timezone


def parse_retention_days(raw: str | None) -> int:
    """Return a disabled (0) or bounded retention window in whole days."""
    value = (raw or "0").strip()
    try:
        days = int(value)
    except ValueError as exc:
        raise ValueError("DAISY_RUN_RETENTION_DAYS must be a whole number") from exc
    if days < 0 or days > 3650:
        raise ValueError("DAISY_RUN_RETENTION_DAYS must be between 0 and 3650")
    return days


def retention_cutoff(days: int, now: datetime | None = None) -> str | None:
    if days == 0:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Retention time must include a timezone")
    return (current.astimezone(timezone.utc) - timedelta(days=days)).isoformat()

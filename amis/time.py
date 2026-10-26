"""Shared parsing for recorded, timezone-aware ISO timestamps."""

from datetime import datetime, timezone


def parse_utc_iso_timestamp(value: str) -> datetime:
    """Reject ambiguous naive timestamps and normalize explicit offsets to UTC."""
    moment = datetime.fromisoformat(value)
    if moment.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return moment.astimezone(timezone.utc)

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_utc_if_naive(dt: datetime, tz: ZoneInfo | None) -> datetime:
    """Interpret a naive datetime in `tz` and return it as UTC.

    Aware datetimes are returned unchanged (their offset is authoritative).
    If `tz` is None, the datetime is returned unchanged (legacy behavior).
    """
    if dt.tzinfo is None and tz is not None:
        return dt.replace(tzinfo=tz).astimezone(timezone.utc)
    return dt

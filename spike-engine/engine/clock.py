"""
Pacific billing clock [CONTRACT A.2] — BR-34, new row BE-1.

All month and day boundaries use IANA America/Los_Angeles with daylight saving,
never a fixed offset. Stored timestamps are ISO 8601 UTC strings ("...Z").

Pacific midnight is never ambiguous or missing (US DST switches at 02:00), so
building a local midnight with ZoneInfo is always well defined. Six-hour
buckets follow the wall clock (00/06/12/18 PT); on DST-change days the first
bucket lasts 5 or 7 real hours.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime; pass an aware UTC datetime")
    return dt.astimezone(UTC)


def iso_utc(dt: datetime | None) -> str | None:
    """2026-10-25T13:50:00Z (second precision)."""
    if dt is None:
        return None
    return ensure_utc(dt).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"not an ISO 8601 UTC string: {value!r}")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)


def pacific_date(dt: datetime) -> date:
    return ensure_utc(dt).astimezone(PACIFIC).date()


def pacific_midnight(d: date) -> datetime:
    """00:00 America/Los_Angeles on local date d, as UTC."""
    return datetime.combine(d, time(0, 0), tzinfo=PACIFIC).astimezone(UTC)


def month_start(now: datetime) -> datetime:
    """00:00 America/Los_Angeles on the 1st of the current Pacific month, as UTC."""
    local = pacific_date(now)
    return pacific_midnight(local.replace(day=1))


def day_start(now: datetime) -> datetime:
    return pacific_midnight(pacific_date(now))


def day_starts(now: datetime, count: int) -> list[datetime]:
    """Start (UTC) of the last `count` Pacific days, oldest first; the last is today."""
    today = pacific_date(now)
    return [pacific_midnight(today - timedelta(days=k)) for k in range(count - 1, -1, -1)]


def bucket_start(dt: datetime, hours: int) -> datetime:
    """Start (UTC) of the wall-clock Pacific bucket of `hours` that contains dt."""
    if 24 % hours:
        raise ValueError("bucket hours must divide 24")
    local = ensure_utc(dt).astimezone(PACIFIC)
    h = (local.hour // hours) * hours
    return datetime.combine(local.date(), time(h, 0), tzinfo=PACIFIC).astimezone(UTC)


def bucket_starts(now: datetime, hours: int, count: int) -> list[datetime]:
    """Start (UTC) of the last `count` Pacific buckets, oldest first; the last contains now."""
    per_day = 24 // hours
    cur = bucket_start(now, hours)
    local = cur.astimezone(PACIFIC)
    index_today = local.hour // hours
    out = []
    for back in range(count - 1, -1, -1):
        idx = index_today - back
        day_offset, slot = divmod(idx, per_day)
        d = local.date() + timedelta(days=day_offset)
        out.append(datetime.combine(d, time(slot * hours, 0), tzinfo=PACIFIC).astimezone(UTC))
    return out


def next_bucket_start(start: datetime, hours: int) -> datetime:
    """The bucket boundary after `start` (handles 23/25-hour days)."""
    local = start.astimezone(PACIFIC)
    h = local.hour + hours
    d = local.date()
    if h >= 24:
        d, h = d + timedelta(days=1), h - 24
    return datetime.combine(d, time(h, 0), tzinfo=PACIFIC).astimezone(UTC)


def floor_hour(dt: datetime) -> datetime:
    return ensure_utc(dt).replace(minute=0, second=0, microsecond=0)

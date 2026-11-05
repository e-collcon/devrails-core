"""
Normalized readings — BR-33, BR-35, BR-38 (TASK-047..049), Contract v1.3.

Pure functions that turn raw Cloud Monitoring points into the same internal
shape for every metric. No I/O here; the Monitoring adapter (monitoring.py)
and the fixture source (fixtures.py) both feed these functions, so tests cover
the real arithmetic.

Point semantics
  delta_count : one point per hour, `at` = hour start (UTC), value = requests
                in that hour. The last point may cover a partial hour.
  gauge_bytes : one point per sample, `at` = sample time (UTC), value = total
                bytes across all buckets at that time.

Zero usage (N5): once a Monitoring read succeeds, an hour with no points is an
hour with zero requests, and no gauge points means zero stored bytes. Missing
data only exists before collection started (D5) — and failures never reach
this module (they fail the poll instead).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import config
from engine import clock
from engine.metrics_config import MetricConfig

SPARKLINE_DAYS = 7      # [CONTRACT v1.3 A.7.3] the same 7 Pacific days as v1.2
BUCKET_HOURS = config.SPARKLINE_BUCKET_HOURS
MAX_BUCKETS = SPARKLINE_DAYS * (24 // BUCKET_HOURS)  # 28
HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Point:
    at: datetime
    value: float


@dataclass(frozen=True)
class VelocityFacts:
    hours_collected: float       # hours of collected history (D5), capped at the lookback span
    pace_per_hour: float         # change per hour over the last 24 complete hours
    last_24h: float              # Cloud Run: requests in the last 24 complete hours; Storage: growth in 24 h
    week_total: float            # Cloud Run: requests in the last 7 x 24 complete hours
    resets_at: datetime | None   # when the allowance resets (Cloud Run: next Pacific month start)
    activity: float              # for no_recent_activity: Cloud Run requests in 7 x 24 h; Storage bytes held


@dataclass(frozen=True)
class MetricReading:
    config: MetricConfig
    current_value: int
    window_started_at: datetime | None
    sparkline: list[int]
    bucket_hours: int
    last_bucket_started_at: datetime
    velocity: VelocityFacts


def lookback_start(now: datetime) -> datetime:
    """Earliest instant a poll needs: month start, or 8 Pacific days back (BR-38)."""
    eight_days = clock.pacific_midnight(clock.pacific_date(now) - timedelta(days=8))
    return min(clock.month_start(now), eight_days)


def next_month_start(now: datetime) -> datetime:
    local = clock.pacific_date(now)
    first = local.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return clock.pacific_midnight(nxt)


def sparkline_buckets(now: datetime) -> list[datetime]:
    """Bucket starts (UTC) for v1.3 C1: the last 7 Pacific days including today, four
    wall-clock buckets per day (00/06/12/18 PT), up to and including the current bucket.
    Today's future buckets are absent, so a full week has 25–28 slots."""
    first_day = clock.day_starts(now, SPARKLINE_DAYS)[0]
    return [b for b in clock.bucket_starts(now, BUCKET_HOURS, MAX_BUCKETS) if b >= first_day]


def _visible(starts: list[datetime], collection_start: datetime | None) -> list[datetime]:
    """Buckets that overlap collected history. Never padded before collection began (A.7.3)."""
    if collection_start is None:
        return starts
    return [b for b in starts if clock.next_bucket_start(b, BUCKET_HOURS) > collection_start] or starts[-1:]


def _hours_collected(now: datetime, collection_start: datetime | None) -> float:
    span = (now - lookback_start(now)) / HOUR
    if collection_start is None:
        return span
    return max(0.0, min(span, (now - collection_start) / HOUR))


def delta_reading(cfg: MetricConfig, points: list[Point], now: datetime,
                  collection_start: datetime | None = None) -> MetricReading:
    pts = sorted((p for p in points if p.at < now), key=lambda p: p.at)
    m_start = clock.month_start(now)
    mtd = sum(p.value for p in pts if p.at >= m_start)  # D2: actual month-to-date, collected or not

    starts = sparkline_buckets(now)
    spark = []
    for b in _visible(starts, collection_start):
        end = clock.next_bucket_start(b, BUCKET_HOURS)
        spark.append(int(round(sum(p.value for p in pts if b <= p.at < end))))

    hour = clock.floor_hour(now)
    last_24h = sum(p.value for p in pts if hour - config.PACE_WINDOW_HOURS * HOUR <= p.at < hour)
    week = sum(p.value for p in pts if hour - config.HISTORY_HOURS * HOUR <= p.at < hour)

    return MetricReading(
        config=cfg,
        current_value=int(round(mtd)),
        window_started_at=m_start,
        sparkline=spark,
        bucket_hours=BUCKET_HOURS,
        last_bucket_started_at=starts[-1],
        velocity=VelocityFacts(
            hours_collected=_hours_collected(now, collection_start),
            pace_per_hour=last_24h / config.PACE_WINDOW_HOURS,
            last_24h=last_24h,
            week_total=week,
            resets_at=next_month_start(now) if cfg.value_window == "month_to_date" else None,
            activity=week,
        ),
    )


def gauge_reading(cfg: MetricConfig, points: list[Point], now: datetime,
                  collection_start: datetime | None = None) -> MetricReading:
    pts = sorted((p for p in points if p.at <= now), key=lambda p: p.at)

    def value_at(t: datetime) -> float:
        before = [p for p in pts if p.at <= t]
        return before[-1].value if before else 0.0  # no reading = no stored bytes (N5)

    latest = pts[-1].value if pts else 0.0
    starts = sparkline_buckets(now)
    spark = []
    for b in _visible(starts, collection_start):
        end = clock.next_bucket_start(b, BUCKET_HOURS)
        spark.append(int(round(value_at(min(now, end - timedelta(microseconds=1))))))

    growth = latest - value_at(now - config.PACE_WINDOW_HOURS * HOUR)
    return MetricReading(
        config=cfg,
        current_value=int(round(latest)),
        window_started_at=None,
        sparkline=spark,
        bucket_hours=BUCKET_HOURS,
        last_bucket_started_at=starts[-1],
        velocity=VelocityFacts(
            hours_collected=_hours_collected(now, collection_start),
            pace_per_hour=growth / config.PACE_WINDOW_HOURS,
            last_24h=growth,
            week_total=0.0,
            resets_at=None,  # stored bytes don't reset
            activity=latest,
        ),
    )


def build_reading(cfg: MetricConfig, points: list[Point], now: datetime,
                  collection_start: datetime | None = None) -> MetricReading:
    if cfg.kind == "delta_count":
        return delta_reading(cfg, points, now, collection_start)
    if cfg.kind == "gauge_bytes":
        return gauge_reading(cfg, points, now, collection_start)
    raise ValueError(f"unknown metric kind {cfg.kind!r}")

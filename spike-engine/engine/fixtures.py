"""
Fixture source — BR-37 (TASK-020, TASK-051), Contract v1.3.

Deterministic Cloud Monitoring-shaped points for each dashboard state, so the
whole engine (readings → classification → payload → schema) runs offline. The
same scenarios generate the web-app fixtures (`main.py export-fixtures`), so
the dashboard depicts real engine output, not hand-written JSON.

A scenario sets the month-to-date ratio and, optionally, the pace of the last
24 hours as "hours until the free tier runs out". `history_hours` is how long
DevRails has been collecting (it sets the stub's sync_initialized_at).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from engine import clock
from engine.metrics_config import MetricConfig
from engine.monitoring import MetricFetchError
from engine.readings import Point, lookback_start

# Hourly shape (Pacific hour 0..23): quiet nights, busy afternoons.
_DIURNAL = [0.35, 0.3, 0.28, 0.27, 0.3, 0.4, 0.6, 0.85, 1.05, 1.2, 1.3, 1.35,
            1.4, 1.42, 1.4, 1.35, 1.3, 1.25, 1.2, 1.1, 0.95, 0.8, 0.6, 0.45]


def _jitter(i: int) -> float:
    return 1 + 0.06 * math.sin(i * 1.7) + 0.03 * math.cos(i * 0.61)


@dataclass(frozen=True)
class Scenario:
    run_ratio: float                    # target month-to-date usage ratio
    storage_ratio: float                # latest total bytes / limit
    storage_growth: float = 0.0         # growth per Pacific day, as a share of the limit
    run_runs_out_in_hours: float | None = None  # pace of the last 24 h; None = the month's steady pace
    history_hours: float | None = None  # how long DevRails has collected (None = 30 days)
    fail: bool = False
    description: str = ""


SCENARIOS: dict[str, Scenario] = {
    "normal": Scenario(0.2251, 0.30, 0.0003, description="Both signals below 75 %, steady"),
    "insufficient_history": Scenario(0.12, 0.08, history_hours=12,
                                     description="DevRails has collected only 12 h"),
    "rising": Scenario(0.40, 0.30, 0.0003, run_runs_out_in_hours=120,
                       description="Below 75 %, but at today's pace Cloud Run runs out in ~5 days"),
    "elevated": Scenario(0.83, 0.45, 0.0005, description="Cloud Run past the 75 % lower threshold"),
    "risky": Scenario(0.55, 1.15, 0.0105, description="Cloud Storage over the allowance and growing"),
    "runs_out_soon": Scenario(0.60, 0.30, 0.0003, run_runs_out_in_hours=30,
                              description="At today's pace Cloud Run runs out in ~30 h"),
    "empty": Scenario(0.0, 0.0, description="Reachable, but no Cloud Run traffic and no stored data"),
    "failing": Scenario(0.0, 0.0, fail=True, description="Cloud Monitoring unreachable"),
}


class FixtureSource:
    def __init__(self, scenario: str):
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown fixture {scenario!r}; choose from {sorted(SCENARIOS)}")
        self.name = scenario
        self.s = SCENARIOS[scenario]
        self.calls = 0

    def fetch_points(self, cfg: MetricConfig, now: datetime) -> list[Point]:
        self.calls += 1
        if self.s.fail:
            raise MetricFetchError("unavailable", cfg.key, "fixture")
        if cfg.kind == "delta_count":
            return self._run_points(cfg, now)
        return self._storage_points(cfg, now)

    def _run_points(self, cfg: MetricConfig, now: datetime) -> list[Point]:
        s = self.s
        if s.run_ratio <= 0:
            return []
        hour = clock.floor_hour(now)
        m_start = clock.month_start(now)
        partial = (now - hour).total_seconds() / 3600
        times, t = [], lookback_start(now)
        while t <= hour:
            times.append(t)
            t += timedelta(hours=1)
        w = {t: _DIURNAL[t.astimezone(clock.PACIFIC).hour] * _jitter(i) for i, t in enumerate(times)}
        w[hour] *= partial  # the current hour is only partly over
        target = s.run_ratio * cfg.free_tier_limit
        recent = {t for t in times if hour - timedelta(hours=24) <= t < hour}

        if s.run_runs_out_in_hours is None:
            in_month = sum(w[t] for t in times if t >= m_start)
            k = target / in_month
            values = {t: w[t] * k for t in times}
        else:
            pace = (cfg.free_tier_limit - target) / s.run_runs_out_in_hours  # requests per hour
            recent_w = sum(w[t] for t in recent)
            k_recent = pace * 24 / recent_w
            current = pace * partial
            rest = [t for t in times if t >= m_start and t not in recent and t != hour]
            k_rest = (target - pace * 24 - current) / sum(w[t] for t in rest)
            if k_rest <= 0:
                raise ValueError("scenario pace is too fast for its month-to-date ratio")
            values = {t: (w[t] * k_recent if t in recent else w[t] * k_rest) for t in times}
            values[hour] = current
        return [Point(at=t, value=round(v)) for t, v in values.items() if round(v) > 0]

    def _storage_points(self, cfg: MetricConfig, now: datetime) -> list[Point]:
        s = self.s
        if s.storage_ratio <= 0:
            return []  # no buckets: Monitoring returns no series, which is zero bytes (N5)
        today = clock.pacific_date(now)
        pts: list[Point] = []
        t = lookback_start(now)
        while t <= now:
            days_back = (today - clock.pacific_date(t)).days
            ratio = max(0.0, s.storage_ratio - s.storage_growth * days_back)  # GCP measures once a day
            pts.append(Point(at=t, value=round(ratio * cfg.free_tier_limit)))
            t += timedelta(hours=1)
        pts.append(Point(at=now, value=round(s.storage_ratio * cfg.free_tier_limit)))
        return pts

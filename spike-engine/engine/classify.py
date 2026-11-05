"""
Classification — the "spike engine" proper. BR-40..46 (TASK-054..059, 063), Contract v1.3 A.8.

Pure functions, no I/O.

Two independent axes per metric, each mapped to a level:
  threshold (E, 2026-10-25): <75% Normal · 75–90% Elevated · ≥90% Risky
  pace      (E, N4 2026-10-27): projected to run out of the free tier
            <7×24 h Elevated · <2×24 h Risky (Risky wins, no overlap)
A metric's level is the worse of the two; the system status is the worst metric
[PENDING D3 rec]. Reason precedence is [PENDING D3]; the order used here is
documented in `_tier`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import config
from engine.readings import MetricReading

ABSOLUTE_ORDER = {"within_limit": 0, "near_limit": 1, "over_limit": 2}
VELOCITY_ORDER = {"stable": 0, "insufficient_data": 1, "elevated": 2, "accelerating": 3}
LEVEL_ORDER = {"Normal": 0, "Elevated": 1, "Risky": 2}
ABSOLUTE_LEVEL = {"within_limit": "Normal", "near_limit": "Elevated", "over_limit": "Risky"}
VELOCITY_LEVEL = {"stable": "Normal", "insufficient_data": "Normal", "elevated": "Elevated", "accelerating": "Risky"}


@dataclass(frozen=True)
class MetricStatus:
    key: str
    reason_prefix: str
    display_name: str
    usage_ratio: float
    absolute: str
    velocity: str
    projected_hours: float | None   # projected_hours_to_limit
    multiplier: float | None        # burn_rate_multiplier (display only)
    level: str                      # Normal | Elevated | Risky
    activity: float
    hours_collected: float


@dataclass(frozen=True)
class Rollup:
    system_status: str
    status_model: dict
    primary: MetricStatus | None
    statuses: tuple[MetricStatus, ...]


def usage_ratio(current_value: float, limit: float) -> float:
    """BR-40: current_value / free_tier_limit, may exceed 1.0."""
    return round(current_value / limit, 4)


def absolute_status(ratio: float) -> str:
    """BR-41: independent of velocity."""
    if ratio >= config.THRESHOLD_UPPER:
        return "over_limit"
    if ratio >= config.THRESHOLD_LOWER:
        return "near_limit"
    return "within_limit"


def project(reading: MetricReading, now: datetime) -> tuple[str, float | None]:
    """N4: (velocity_status, projected_hours_to_limit).

    - fewer than 24 h of collected data          -> insufficient_data, null
    - already at/over the limit                   -> 0 h; accelerating if still growing, else stable
    - not growing                                 -> stable, null
    - allowance resets before the crossing (Run)  -> stable, null
    - otherwise hours = remaining / pace: <48 h accelerating, <168 h elevated, else stable
    """
    v = reading.velocity
    if v.hours_collected < config.MIN_HOURS_FOR_PROJECTION:
        return "insufficient_data", None
    remaining = reading.config.free_tier_limit - reading.current_value
    pace = v.pace_per_hour
    if remaining <= 0:
        return ("accelerating" if pace > 0 else "stable"), 0.0
    if pace <= 0:
        return "stable", None
    hours = remaining / pace
    if v.resets_at is not None and now + timedelta(hours=hours) >= v.resets_at:
        return "stable", None  # the monthly allowance resets first
    hours = round(hours, 1)
    if hours < config.RISKY_WITHIN_HOURS:
        return "accelerating", hours
    if hours < config.ELEVATED_WITHIN_HOURS:
        return "elevated", hours
    return "stable", hours


def burn_multiplier(reading: MetricReading) -> float | None:
    """Display only (v1.3): last 24 h ÷ the average 24 h over the last 7 × 24 h.
    Null for capacity signals, before 7 × 24 h are collected, or on a tiny baseline."""
    v = reading.velocity
    if reading.config.metric_role != "primary_burn_rate_signal":
        return None
    if v.hours_collected < config.HISTORY_HOURS or v.week_total < config.BASELINE_MIN_REQUESTS:
        return None
    return round(v.last_24h / (v.week_total / 7), 2)


def metric_level(absolute: str, velocity: str) -> str:
    """v1.3 A.8: the worse of the threshold level and the pace level."""
    a, b = ABSOLUTE_LEVEL[absolute], VELOCITY_LEVEL[velocity]
    return a if LEVEL_ORDER[a] >= LEVEL_ORDER[b] else b


def classify_metric(reading: MetricReading, now: datetime) -> MetricStatus:
    cfg = reading.config
    ratio = usage_ratio(reading.current_value, cfg.free_tier_limit)
    absolute = absolute_status(ratio)
    velocity, hours = project(reading, now)
    return MetricStatus(
        key=cfg.key,
        reason_prefix=cfg.reason_prefix,
        display_name=cfg.display_name,
        usage_ratio=ratio,
        absolute=absolute,
        velocity=velocity,
        projected_hours=hours,
        multiplier=burn_multiplier(reading),
        level=metric_level(absolute, velocity),
        activity=reading.velocity.activity,
        hours_collected=reading.velocity.hours_collected,
    )


def _tier(ms: MetricStatus) -> tuple[int, float, str]:
    """Reason precedence [PENDING D3]. Returns (tier, sub-rank, primary_reason token).
      0 threshold ≥90%            <metric>_over_limit
      1 runs out within 48 h      <metric>_accelerating
      2 threshold ≥75%            <metric>_near_limit
      3 runs out within 7 days    <metric>_accelerating
      4 not enough history        cloud_run_insufficient_history / cloud_storage_insufficient_history
      5 nothing to report         all_within_limits (or no_recent_activity, decided in rollup)
    Ties: Cloud Run first (metric order)."""
    p = ms.reason_prefix
    if ms.absolute == "over_limit":
        return 0, 0, f"{p}_over_limit"
    if ms.velocity == "accelerating":
        return 1, 0, f"{p}_accelerating"
    if ms.absolute == "near_limit":
        return 2, 0, f"{p}_near_limit"
    if ms.velocity == "elevated":
        return 3, 0, f"{p}_accelerating"
    if ms.velocity == "insufficient_data":
        return 4, 0, f"{p}_insufficient_history"
    return 5, 0, "all_within_limits"


def _no_recent_activity(statuses: tuple[MetricStatus, ...]) -> bool:
    """N5 [rule PROPOSED]: 7 × 24 h collected, no Cloud Run requests in that time, no stored bytes."""
    return all(s.hours_collected >= config.NO_ACTIVITY_HOURS and s.activity == 0 for s in statuses)


def rollup(statuses: list[MetricStatus] | tuple[MetricStatus, ...]) -> Rollup:
    """BR-45/46: worst of both metrics [PENDING D3 rec]."""
    statuses = tuple(statuses)
    if not statuses:
        raise ValueError("rollup needs at least one metric")
    ranked = sorted(enumerate(statuses), key=lambda iv: (_tier(iv[1])[0], _tier(iv[1])[1], iv[0]))
    top = ranked[0][1]
    tier, _, token = _tier(top)
    if tier == 5 and _no_recent_activity(statuses):
        token = "no_recent_activity"
    system_status = max((s.level for s in statuses), key=LEVEL_ORDER.__getitem__)
    status_model = {
        "absolute_threshold_status": max((s.absolute for s in statuses), key=ABSOLUTE_ORDER.__getitem__),
        "velocity_status": max((s.velocity for s in statuses), key=VELOCITY_ORDER.__getitem__),
        "primary_reason": token,
    }
    return Rollup(
        system_status=system_status,
        status_model=status_model,
        primary=top if tier < 4 else None,
        statuses=statuses,
    )

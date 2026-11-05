"""
Feed payloads — BR-51, BR-52, §9 (TASK-018, 021, 061). Contract v1.3.

  stub_document()   exactly the nine A.5 fields (provisioning)
  synced_document() the full A.6 shape after a successful poll

Field names and enum values are transcribed from Contract v1.3; never
paraphrased.
"""

from __future__ import annotations

from datetime import datetime

import config
from engine import clock
from engine.classify import MetricStatus, Rollup
from engine.readings import MetricReading

STUB_FIELDS = (
    "gcp_project_id",
    "guardrail_mode",
    "guardrail_label",
    "monthly_budget_usd",
    "initial_sync_complete",
    "sync_initialized_at",
    "last_sync_timestamp",
    "system_status",
    "status_explanation",
)
SYNCED_FIELDS = STUB_FIELDS + ("status_model", "metrics")


def stub_document(gcp_project_id: str, now: datetime) -> dict:
    """A.5: exactly nine fields."""
    return {
        "gcp_project_id": gcp_project_id,
        "guardrail_mode": config.GUARDRAIL_MODE,
        "guardrail_label": config.GUARDRAIL_LABEL,
        "monthly_budget_usd": None,
        "initial_sync_complete": False,
        "sync_initialized_at": clock.iso_utc(now),
        "last_sync_timestamp": None,
        "system_status": "Pending",
        "status_explanation": config.STATE_001_EXPLANATION,
    }


def metric_object(reading: MetricReading, status: MetricStatus) -> dict:
    """v1.3 A.7.3 — fifteen fields, in contract order."""
    cfg = reading.config
    return {
        "metric_id": cfg.metric_id,
        "metric_role": cfg.metric_role,
        "value_window": cfg.value_window,
        "window_started_at": clock.iso_utc(reading.window_started_at) if cfg.value_window == "month_to_date" else None,
        "current_value": reading.current_value,
        "free_tier_limit": cfg.free_tier_limit,
        "usage_ratio": status.usage_ratio,
        "absolute_threshold_status": status.absolute,
        "velocity_status": status.velocity,
        "projected_hours_to_limit": status.projected_hours,
        "burn_rate_multiplier": status.multiplier,
        "freshness_profile": cfg.freshness_profile,
        "sparkline_data_points": list(reading.sparkline),
        "sparkline_bucket_hours": reading.bucket_hours,
        "sparkline_last_bucket_started_at": clock.iso_utc(reading.last_bucket_started_at),
    }


def synced_document(
    *,
    existing: dict,
    readings: list[MetricReading],
    result: Rollup,
    explanation: str,
    now: datetime,
) -> dict:
    """A.6. `existing` is the stored stub/synced doc; sync_initialized_at and the
    project identity are carried over from it, never regenerated."""
    by_key = {s.key: s for s in result.statuses}
    return {
        "gcp_project_id": existing["gcp_project_id"],
        "guardrail_mode": config.GUARDRAIL_MODE,
        "guardrail_label": config.GUARDRAIL_LABEL,
        "monthly_budget_usd": None,
        "initial_sync_complete": True,
        "sync_initialized_at": existing["sync_initialized_at"],
        "last_sync_timestamp": clock.iso_utc(now),
        "system_status": result.system_status,
        "status_explanation": explanation,
        "status_model": dict(result.status_model),
        "metrics": {r.config.key: metric_object(r, by_key[r.config.key]) for r in readings},
    }

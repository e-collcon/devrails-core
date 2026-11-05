"""
Contract v1.3 validator — BR-53, new row BE-3. Mirrored by web-app/src/lib/feed/contract.ts.

validate_feed(doc) returns a list of human-readable errors; an empty list means
the document is valid. The engine runs it before every write and never writes
a document that fails.
"""

from __future__ import annotations

import math
from typing import Any

import config
from engine import clock
from engine.payload import STUB_FIELDS, SYNCED_FIELDS

SYSTEM_STATUS_WRITTEN = {"Pending", "Normal", "Elevated", "Risky", "Sync Failed"}  # A.7.1
ABSOLUTE = {"within_limit", "near_limit", "over_limit"}
VELOCITY = {"stable", "elevated", "accelerating", "insufficient_data"}
METRIC_ROLE = {"primary_burn_rate_signal", "capacity_status_signal"}
FRESHNESS = {"near_real_time", "daily_or_delayed"}
VALUE_WINDOW = {"month_to_date", "latest"}
PRIMARY_REASON = {  # v1.3 A.7.8
    "all_within_limits", "awaiting_initial_data",
    "cloud_run_near_limit", "cloud_run_accelerating", "cloud_run_over_limit", "cloud_run_insufficient_history",
    "cloud_storage_near_limit", "cloud_storage_accelerating", "cloud_storage_over_limit",
    "cloud_storage_insufficient_history",
    "no_recent_activity",
}
METRIC_FIELDS = {  # v1.3 A.7.3: fifteen fields
    "metric_id", "metric_role", "value_window", "window_started_at", "current_value", "free_tier_limit",
    "usage_ratio", "absolute_threshold_status", "velocity_status", "projected_hours_to_limit",
    "burn_rate_multiplier", "freshness_profile", "sparkline_data_points", "sparkline_bucket_hours",
    "sparkline_last_bucket_started_at",
}
MAX_SPARKLINE = 28
METRIC_KEYS = {"cloud_run_requests", "cloud_storage_bytes"}


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_utc(v: Any) -> bool:
    try:
        clock.parse_iso_utc(v)
        return True
    except (ValueError, TypeError):
        return False


def _check_metric(key: str, m: Any, errors: list[str]) -> None:
    where = f"metrics.{key}"
    if not isinstance(m, dict):
        errors.append(f"{where} must be an object")
        return
    for f in sorted(METRIC_FIELDS - m.keys()):
        errors.append(f"{where}.{f} is missing")
    for f in sorted(m.keys() - METRIC_FIELDS):
        errors.append(f"{where}.{f} is not a contract field")

    if m.get("metric_role") not in METRIC_ROLE:
        errors.append(f"{where}.metric_role has an unknown value")
    if m.get("value_window") not in VALUE_WINDOW:
        errors.append(f"{where}.value_window has an unknown value")
    if m.get("absolute_threshold_status") not in ABSOLUTE:
        errors.append(f"{where}.absolute_threshold_status has an unknown value")
    if m.get("velocity_status") not in VELOCITY:
        errors.append(f"{where}.velocity_status has an unknown value")
    if m.get("freshness_profile") not in FRESHNESS:
        errors.append(f"{where}.freshness_profile has an unknown value")
    if not isinstance(m.get("metric_id"), str) or not m.get("metric_id"):
        errors.append(f"{where}.metric_id must be a non-empty string")
    for f in ("current_value", "free_tier_limit", "usage_ratio"):
        if not _is_num(m.get(f)):
            errors.append(f"{where}.{f} must be a number")

    if m.get("value_window") == "month_to_date" and not _is_utc(m.get("window_started_at")):
        errors.append(f"{where}.window_started_at must be a UTC string for month_to_date")
    if m.get("value_window") == "latest" and m.get("window_started_at") is not None:
        errors.append(f"{where}.window_started_at must be null for latest")

    proj = m.get("projected_hours_to_limit")
    if proj is not None and (not _is_num(proj) or proj < 0):
        errors.append(f"{where}.projected_hours_to_limit must be a non-negative number or null")
    if m.get("velocity_status") == "insufficient_data" and proj is not None:
        errors.append(f"{where}.projected_hours_to_limit must be null when insufficient_data")
    if m.get("velocity_status") in ("elevated", "accelerating") and proj is None:
        errors.append(f"{where}.projected_hours_to_limit is required when velocity is elevated or accelerating")

    mult = m.get("burn_rate_multiplier")
    if mult is not None and not _is_num(mult):
        errors.append(f"{where}.burn_rate_multiplier must be a number or null")
    if m.get("metric_role") == "capacity_status_signal" and mult is not None:
        errors.append(f"{where}.burn_rate_multiplier must be null for capacity signals")
    if m.get("velocity_status") == "insufficient_data" and mult is not None:
        errors.append(f"{where}.burn_rate_multiplier must be null when insufficient_data")

    if _is_num(m.get("current_value")) and _is_num(m.get("free_tier_limit")) and _is_num(m.get("usage_ratio")):
        if m["free_tier_limit"] <= 0:
            errors.append(f"{where}.free_tier_limit must be positive")
        elif abs(m["current_value"] / m["free_tier_limit"] - m["usage_ratio"]) > 1e-3:
            errors.append(f"{where}.usage_ratio does not equal current_value / free_tier_limit")

    spark = m.get("sparkline_data_points")
    if not isinstance(spark, list) or not all(_is_num(v) for v in spark):
        errors.append(f"{where}.sparkline_data_points must be a list of numbers")
    elif not 1 <= len(spark) <= MAX_SPARKLINE:
        errors.append(f"{where}.sparkline_data_points must hold 1–{MAX_SPARKLINE} values, got {len(spark)}")
    if m.get("sparkline_bucket_hours") != config.SPARKLINE_BUCKET_HOURS:
        errors.append(f"{where}.sparkline_bucket_hours must be {config.SPARKLINE_BUCKET_HOURS}")
    if not _is_utc(m.get("sparkline_last_bucket_started_at")):
        errors.append(f"{where}.sparkline_last_bucket_started_at must be a UTC string")


def validate_feed(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["document must be an object"]
    synced = doc.get("initial_sync_complete") is True
    expected = set(SYNCED_FIELDS if synced else STUB_FIELDS)
    for f in sorted(expected - doc.keys()):
        errors.append(f"{f} is missing")
    for f in sorted(doc.keys() - expected):
        errors.append(f"{f} is not allowed in a {'synced' if synced else 'stub'} document")

    if doc.get("guardrail_mode") != config.GUARDRAIL_MODE:
        errors.append('guardrail_mode must be "free_tier"')
    if doc.get("guardrail_label") != config.GUARDRAIL_LABEL:
        errors.append('guardrail_label must be "Free Tier Watch"')
    if doc.get("monthly_budget_usd", 0) is not None:
        errors.append("monthly_budget_usd must be null in the PoC")
    if not isinstance(doc.get("gcp_project_id"), str) or not doc.get("gcp_project_id"):
        errors.append("gcp_project_id must be a non-empty string")
    if not isinstance(doc.get("initial_sync_complete"), bool):
        errors.append("initial_sync_complete must be a boolean")
    if not _is_utc(doc.get("sync_initialized_at")):
        errors.append("sync_initialized_at must be a UTC string")
    if not isinstance(doc.get("status_explanation"), str) or not doc.get("status_explanation"):
        errors.append("status_explanation must be a non-empty string")
    status = doc.get("system_status")
    if status not in SYSTEM_STATUS_WRITTEN:
        errors.append("system_status has a value the backend may not write")

    if not synced:
        if doc.get("last_sync_timestamp") is not None:
            errors.append("last_sync_timestamp must be null before the first successful sync")
        if status != "Pending":
            errors.append('a stub document must have system_status "Pending"')
        return errors

    if not _is_utc(doc.get("last_sync_timestamp")):
        errors.append("last_sync_timestamp must be a UTC string once synced")
    if status == "Pending":
        errors.append('system_status "Pending" is only valid in a stub')
    model = doc.get("status_model")
    if not isinstance(model, dict) or set(model.keys()) != {"absolute_threshold_status", "velocity_status", "primary_reason"}:
        errors.append("status_model must have exactly absolute_threshold_status, velocity_status, primary_reason")
    else:
        if model["absolute_threshold_status"] not in ABSOLUTE:
            errors.append("status_model.absolute_threshold_status has an unknown value")
        if model["velocity_status"] not in VELOCITY:
            errors.append("status_model.velocity_status has an unknown value")
        if model["primary_reason"] not in PRIMARY_REASON:
            errors.append("status_model.primary_reason has an unknown value")
    metrics = doc.get("metrics")
    if not isinstance(metrics, dict) or set(metrics.keys()) != METRIC_KEYS:
        errors.append("metrics must have exactly cloud_run_requests and cloud_storage_bytes")
    else:
        for key in sorted(METRIC_KEYS):
            _check_metric(key, metrics[key], errors)
    return errors

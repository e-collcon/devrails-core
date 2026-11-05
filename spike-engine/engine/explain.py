"""
status_explanation templates — BR-47 (TASK-060; final wording: Lexie, UX-001), Contract v1.3.

One or two calm sentences. Sentence 1 names the main driver (primary_reason).
Sentence 2, when there is room, adds the most useful secondary fact. Never
mentions billing sync, budgets, cost estimates or automatic action.

These are Claudia's placeholder templates until Lexie's copy lands; they live
in one file so the swap is a single edit.
"""

from __future__ import annotations

import config
from engine.classify import MetricStatus, Rollup

SYNC_FAILED_EXPLANATION = (
    "DevRails could not reach this project's usage data on its latest check. "
    "Showing the last known readings; they may be out of date."
)

# subject, verb, allowance phrase, pronoun + verb for "would use it up"
_SUBJECT = {
    "cloud_run": ("Cloud Run requests", "are", "this month’s free-tier allowance", "they would"),
    "cloud_storage": ("Cloud Storage", "is", "its free-tier allowance", "it would"),
}

LOWER = f"{round(config.THRESHOLD_LOWER * 100)}% lower threshold"
UPPER = f"{round(config.THRESHOLD_UPPER * 100)}% upper threshold"
PACE = "at the last 24 hours’ pace"


def pct(ratio: float) -> str:
    n = round(ratio * 1000) / 10
    return f"{n:.0f}%" if n == int(n) else f"{n:.1f}%"


def duration(hours: float) -> str:
    if hours < 1:
        return "under an hour"
    if hours < 48:
        h = round(hours)
        return f"about {h} hour{'s' if h != 1 else ''}"
    return f"about {round(hours / 24)} days"


def _threshold_sentence(ms: MetricStatus) -> str:
    subj, verb, allowance, _ = _SUBJECT[ms.reason_prefix]
    at = f"{subj} {verb} at {pct(ms.usage_ratio)} of {allowance}"
    if ms.absolute == "over_limit":
        if ms.usage_ratio >= 1:
            growing = " and still growing" if ms.velocity == "accelerating" else ""
            return f"{at} — over the allowance{growing}."
        return f"{at} — past the {UPPER}."
    return f"{at} — past the {LOWER}, still below the {UPPER}."


def _pace_sentence(ms: MetricStatus) -> str:
    """For a metric that is projected to run out (projected_hours > 0)."""
    subj, verb, allowance, would = _SUBJECT[ms.reason_prefix]
    link = "but" if ms.absolute == "within_limit" else "and"
    return (f"{subj} {verb} at {pct(ms.usage_ratio)} of {allowance}, {link} {PACE} "
            f"{would} use it up in {duration(ms.projected_hours)}.")


def _pace_followup(ms: MetricStatus) -> str | None:
    if ms.projected_hours and ms.velocity in ("elevated", "accelerating"):
        _, _, _, would = _SUBJECT[ms.reason_prefix]
        return f"{PACE.capitalize()}, {would} use it up in {duration(ms.projected_hours)}."
    return None


def _secondary(primary: MetricStatus | None, others: list[MetricStatus]) -> str | None:
    for ms in others:
        subj, verb, _, _ = _SUBJECT[ms.reason_prefix]
        if ms.absolute == "over_limit":
            return f"{subj} {verb} also past the {UPPER} ({pct(ms.usage_ratio)})."
        if ms.absolute == "near_limit":
            return f"{subj} {verb} also past the {LOWER} ({pct(ms.usage_ratio)})."
    for ms in others:
        subj, verb, _, would = _SUBJECT[ms.reason_prefix]
        if ms.velocity in ("elevated", "accelerating") and ms.projected_hours:
            return f"{subj} {verb} also climbing: {PACE} {would} run out in {duration(ms.projected_hours)}."
    if primary is not None and primary.velocity == "insufficient_data":
        return "DevRails needs a full day of readings before it can tell how fast this is growing."
    for ms in others:
        if ms.velocity == "insufficient_data":
            subj, verb, _, _ = _SUBJECT[ms.reason_prefix]
            return f"DevRails needs a full day of readings before it can tell how fast {subj} {verb} growing."
    if primary is not None and primary.usage_ratio > 1:
        return "Usage above the free-tier allowance may be billed."
    return None


def explain(result: Rollup) -> str:
    token = result.status_model["primary_reason"]
    statuses = list(result.statuses)
    if token == "no_recent_activity":
        return ("DevRails can reach this project, but it has had no Cloud Run requests and has held "
                "no stored data for the last 7 days.")
    if token.endswith("_insufficient_history"):
        prefix = token.removesuffix("_insufficient_history")
        subj, verb, _, _ = _SUBJECT[prefix]
        return (f"Usage is below the {LOWER}. DevRails needs a full day of readings before it can "
                f"tell how fast {subj} {verb} growing.")
    if result.primary is None:  # all_within_limits
        first = f"Cloud Run requests and Cloud Storage are both below the {LOWER} of their free-tier allowances."
        second = _secondary(None, statuses)
        return f"{first} {second}" if second else first

    primary = result.primary
    others = [s for s in statuses if s is not primary]
    pace_driven = token.endswith("_accelerating")
    if pace_driven:
        first = _pace_sentence(primary)
        second = _secondary(None, others)
    else:
        first = _threshold_sentence(primary)
        second = _pace_followup(primary) if primary.usage_ratio < 1 else None
        second = second or _secondary(primary, others)
    return f"{first} {second}" if second else first

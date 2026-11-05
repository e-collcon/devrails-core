"""BR-40..46, TASK-062/063, Contract v1.3 A.8: thresholds, N4 pace bands, levels, rollup, precedence, N5."""

from datetime import timedelta

import pytest

from engine import clock
from engine.classify import (
    MetricStatus, absolute_status, burn_multiplier, classify_metric, metric_level, project, rollup, usage_ratio,
)
from engine.explain import explain
from engine.metrics_config import CLOUD_RUN_REQUESTS as RUN, CLOUD_STORAGE_BYTES as STO
from engine.readings import MetricReading, VelocityFacts, next_month_start

NOW = clock.parse_iso_utc("2026-10-25T19:55:00Z")   # 155.1 h before the Nov 1 reset
VELOCITIES = ["stable", "elevated", "accelerating", "insufficient_data"]


def run_reading(ratio, *, pace=0.0, collected=24 * 30, week=None, now=NOW):
    v = VelocityFacts(hours_collected=collected, pace_per_hour=pace, last_24h=pace * 24,
                      week_total=week if week is not None else pace * 168, resets_at=next_month_start(now),
                      activity=week if week is not None else pace * 168)
    return MetricReading(RUN, int(ratio * RUN.free_tier_limit), clock.month_start(now), [1], 6, now, v)


def sto_reading(ratio, *, growth_per_day=0.0, collected=24 * 30):
    pace = growth_per_day * STO.free_tier_limit / 24
    v = VelocityFacts(hours_collected=collected, pace_per_hour=pace, last_24h=pace * 24, week_total=0.0,
                      resets_at=None, activity=ratio * STO.free_tier_limit)
    return MetricReading(STO, int(ratio * STO.free_tier_limit), None, [1], 6, NOW, v)


def status(prefix, absolute, velocity, ratio=0.5, hours=None, activity=1.0, collected=24 * 30):
    return MetricStatus(f"{prefix}_x", prefix, prefix, ratio, absolute, velocity, hours, None,
                        metric_level(absolute, velocity), activity, collected)


# --- thresholds (E, 2026-10-25) -------------------------------------------------------------

@pytest.mark.parametrize("ratio,expected", [
    (0.0, "within_limit"), (0.7499, "within_limit"), (0.75, "near_limit"), (0.8999, "near_limit"),
    (0.90, "over_limit"), (1.0, "over_limit"), (1.15, "over_limit"),
])
def test_absolute_status_boundaries(ratio, expected):
    assert absolute_status(ratio) == expected


def test_usage_ratio_may_exceed_one():
    assert usage_ratio(6_174_015_488, 5_368_709_120) == 1.15


# --- N4: time until the free tier runs out ---------------------------------------------------

REMAINING_AT_40 = 0.6 * 2_000_000  # 1.2 M requests left


@pytest.mark.parametrize("hours_left,expected", [
    (10, "accelerating"), (47.9, "accelerating"), (48, "elevated"), (100, "elevated"), (154, "elevated"),
])
def test_cloud_run_pace_bands(hours_left, expected):
    vel, hours = project(run_reading(0.4, pace=REMAINING_AT_40 / hours_left), NOW)
    assert vel == expected and hours == pytest.approx(hours_left, abs=0.1)


def test_cloud_run_not_at_risk_when_the_month_resets_first():
    # 160 h to run out, but the allowance resets in ~155 h.
    assert project(run_reading(0.4, pace=REMAINING_AT_40 / 160), NOW) == ("stable", None)


def test_storage_has_no_reset_so_long_runways_are_reported():
    vel, hours = project(sto_reading(0.5, growth_per_day=0.01), NOW)
    assert vel == "stable" and hours == pytest.approx(50 * 24, abs=0.1)


def test_storage_elevated_and_risky_bands():
    assert project(sto_reading(0.5, growth_per_day=0.1), NOW)[0] == "elevated"      # 5 days
    assert project(sto_reading(0.5, growth_per_day=0.3), NOW)[0] == "accelerating"  # 40 h


def test_not_growing_is_stable_with_no_projection():
    assert project(run_reading(0.4, pace=0), NOW) == ("stable", None)
    assert project(sto_reading(0.5, growth_per_day=-0.02), NOW) == ("stable", None)


def test_past_the_limit_growing_is_accelerating_flat_is_stable():
    assert project(sto_reading(1.15, growth_per_day=0.01), NOW) == ("accelerating", 0.0)
    assert project(sto_reading(1.15, growth_per_day=0.0), NOW) == ("stable", 0.0)
    assert project(run_reading(1.02, pace=50), NOW) == ("accelerating", 0.0)


def test_insufficient_with_less_than_24_hours_collected():
    assert project(run_reading(0.4, pace=1e6, collected=23.9), NOW) == ("insufficient_data", None)
    assert project(run_reading(0.4, pace=1e6, collected=24), NOW)[0] == "accelerating"


def test_burn_multiplier_is_display_only_and_needs_seven_days():
    r = run_reading(0.4, pace=1000, week=7 * 24 * 500)  # last 24 h twice the weekly average
    assert burn_multiplier(r) == 2.0
    assert burn_multiplier(run_reading(0.4, pace=1000, collected=167)) is None
    assert burn_multiplier(run_reading(0.4, pace=1, week=999)) is None
    assert burn_multiplier(sto_reading(0.5, growth_per_day=0.1)) is None


# --- per-metric level = worse of threshold and pace ------------------------------------------

@pytest.mark.parametrize("velocity", VELOCITIES)
def test_over_limit_is_always_risky(velocity):
    assert metric_level("over_limit", velocity) == "Risky"


@pytest.mark.parametrize("absolute,velocity,expected", [
    ("within_limit", "stable", "Normal"), ("within_limit", "insufficient_data", "Normal"),
    ("within_limit", "elevated", "Elevated"), ("within_limit", "accelerating", "Risky"),
    ("near_limit", "stable", "Elevated"), ("near_limit", "insufficient_data", "Elevated"),
    ("near_limit", "elevated", "Elevated"), ("near_limit", "accelerating", "Risky"),
])
def test_level_is_the_worse_axis(absolute, velocity, expected):
    assert metric_level(absolute, velocity) == expected


# --- rollup and precedence [PENDING D3] ---------------------------------------------------------

def test_threshold_risky_beats_pace_risky():
    r = rollup([status("cloud_run", "within_limit", "accelerating", hours=30),
                status("cloud_storage", "over_limit", "stable", ratio=0.92)])
    assert r.system_status == "Risky" and r.status_model["primary_reason"] == "cloud_storage_over_limit"


def test_pace_risky_beats_threshold_elevated():
    r = rollup([status("cloud_run", "near_limit", "stable", ratio=0.8),
                status("cloud_storage", "within_limit", "accelerating", hours=20)])
    assert r.system_status == "Risky" and r.status_model["primary_reason"] == "cloud_storage_accelerating"


def test_threshold_elevated_beats_pace_elevated():
    r = rollup([status("cloud_run", "within_limit", "elevated", hours=100),
                status("cloud_storage", "near_limit", "stable", ratio=0.8)])
    assert r.system_status == "Elevated" and r.status_model["primary_reason"] == "cloud_storage_near_limit"


def test_cloud_run_wins_ties():
    r = rollup([status("cloud_run", "over_limit", "stable"), status("cloud_storage", "over_limit", "stable")])
    assert r.status_model["primary_reason"] == "cloud_run_over_limit"


def test_insufficient_history_tokens():
    r = rollup([status("cloud_run", "within_limit", "insufficient_data"), status("cloud_storage", "within_limit", "stable")])
    assert (r.system_status, r.status_model["primary_reason"]) == ("Normal", "cloud_run_insufficient_history")
    r = rollup([status("cloud_run", "within_limit", "stable"), status("cloud_storage", "within_limit", "insufficient_data")])
    assert r.status_model["primary_reason"] == "cloud_storage_insufficient_history"
    assert r.status_model["velocity_status"] == "insufficient_data"
    assert "full day of readings" in explain(r)


def test_all_within_limits():
    r = rollup([status("cloud_run", "within_limit", "stable"), status("cloud_storage", "within_limit", "stable")])
    assert (r.system_status, r.status_model["primary_reason"], r.primary) == ("Normal", "all_within_limits", None)


def test_a6_example_v13_reproduces():
    """v1.3 A.6: storage over the allowance and growing, Cloud Run steady."""
    r = rollup([classify_metric(run_reading(0.55, pace=10), NOW), classify_metric(sto_reading(1.15, growth_per_day=0.0105), NOW)])
    assert r.system_status == "Risky"
    assert r.status_model == {"absolute_threshold_status": "over_limit", "velocity_status": "accelerating",
                              "primary_reason": "cloud_storage_over_limit"}


# --- N5: no recent activity ------------------------------------------------------------------

def test_no_recent_activity_after_seven_days_of_collection():
    quiet = [status("cloud_run", "within_limit", "stable", ratio=0, activity=0),
             status("cloud_storage", "within_limit", "stable", ratio=0, activity=0)]
    r = rollup(quiet)
    assert (r.system_status, r.status_model["primary_reason"]) == ("Normal", "no_recent_activity")
    assert "no Cloud Run requests" in explain(r)


def test_no_activity_needs_seven_days_and_both_signals_empty():
    young = [status("cloud_run", "within_limit", "stable", ratio=0, activity=0, collected=100),
             status("cloud_storage", "within_limit", "stable", ratio=0, activity=0, collected=100)]
    assert rollup(young).status_model["primary_reason"] == "all_within_limits"
    stored = [status("cloud_run", "within_limit", "stable", ratio=0, activity=0),
              status("cloud_storage", "within_limit", "stable", ratio=0.01, activity=5e7)]
    assert rollup(stored).status_model["primary_reason"] == "all_within_limits"


# --- explanations ------------------------------------------------------------------------------

def test_pace_sentence_names_the_time_left():
    r = rollup([classify_metric(run_reading(0.4, pace=REMAINING_AT_40 / 30), NOW), classify_metric(sto_reading(0.3), NOW)])
    assert r.system_status == "Risky"
    assert explain(r) == ("Cloud Run requests are at 40% of this month’s free-tier allowance, but at the last "
                          "24 hours’ pace they would use it up in about 30 hours.")


@pytest.mark.parametrize("abs_run", ["within_limit", "near_limit", "over_limit"])
@pytest.mark.parametrize("vel_run", VELOCITIES)
@pytest.mark.parametrize("abs_sto", ["within_limit", "near_limit", "over_limit"])
@pytest.mark.parametrize("vel_sto", VELOCITIES)
def test_explanation_is_one_or_two_calm_sentences(abs_run, vel_run, abs_sto, vel_sto):
    def h(v):
        return 30.0 if v == "accelerating" else 100.0 if v == "elevated" else None
    r = rollup([status("cloud_run", abs_run, vel_run, 0.5, h(vel_run)), status("cloud_storage", abs_sto, vel_sto, 0.5, h(vel_sto))])
    text = explain(r)
    sentences = [s for s in text.split(". ") if s]
    assert 1 <= len(sentences) <= 2, text
    for banned in ("budget", "cost estimate", "invoice", "billing sync", "automatically", "killswitch"):
        assert banned not in text.lower()
    if r.system_status != "Normal":
        assert ("Cloud Run" in text) or ("Cloud Storage" in text)

"""
spike-engine — config.py
DevRails PoC | PRD-001 | Contract v1.3 | Backend Requirements BR-10..14

Central configuration for the spike-engine.

Everything environment-specific comes from env vars (BR-10). Everything that
is a product rule (thresholds, limits, copy) is a constant here, so it can be
reviewed in one place and is never user-configurable during the PoC (BR-14).

Markers follow DevRails_Backend-Requirements.md:
  [CONTRACT]  Firestore Data Contract v1.3 (normative)
  [E-DECIDED] E's decision, not yet copied into the canon documents
  [PROPOSED]  Claudia's recommendation, waiting for E's approval
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# -----------------------------------------------------------------------------
# Environment (BR-10). Names unchanged from the TASK-008 scaffold.
# -----------------------------------------------------------------------------
GCP_PROJECT_ID = os.environ.get("DEVRAILS_GCP_PROJECT_ID", "")          # target (monitored) project
FIREBASE_PROJECT_ID = os.environ.get("DEVRAILS_FIREBASE_PROJECT_ID", "")  # host project (Firestore)
POC_USER_UID = os.environ.get("DEVRAILS_POC_USER_UID", "")
POC_PROJECT_ID = os.environ.get("DEVRAILS_POC_PROJECT_ID", "")
POLLING_INTERVAL_MINUTES = int(os.environ.get("DEVRAILS_POLLING_INTERVAL_MINUTES", "10"))

# -----------------------------------------------------------------------------
# Guardrail mode (locked for PoC) [CONTRACT A.4]
# Machine-readable enum — never use "Free Tier Watch" as the mode value.
# -----------------------------------------------------------------------------
GUARDRAIL_MODE = "free_tier"
GUARDRAIL_LABEL = "Free Tier Watch"

# -----------------------------------------------------------------------------
# Thresholds [E-DECIDED 2026-10-25] (TASK-053, TASK-055)
#   ratio <  0.75          -> within_limit
#   0.75 <= ratio < 0.90   -> near_limit  (Elevated)
#   ratio >= 0.90          -> over_limit  (Risky)
# -----------------------------------------------------------------------------
THRESHOLD_LOWER = 0.75
THRESHOLD_UPPER = 0.90

# -----------------------------------------------------------------------------
# Free-tier limits [CONTRACT A.7.3] — re-verify against current GCP terms
# before acceptance (BR-13).
# -----------------------------------------------------------------------------
CLOUD_RUN_FREE_REQUESTS_PER_MONTH = 2_000_000
CLOUD_STORAGE_FREE_BYTES = 5_368_709_120  # 5 GiB

# -----------------------------------------------------------------------------
# Velocity = time left before the free tier runs out at the current pace
# [E-DECIDED N4, 2026-10-27] (TASK-056, Contract v1.3 A.7.10)
#   projected to run out in under 2 x 24 h  -> accelerating -> Risky
#   projected to run out in under 7 x 24 h  -> elevated     -> Elevated
#   Risky wins; the bands never overlap.
# -----------------------------------------------------------------------------
RISKY_WITHIN_HOURS = 2 * 24
ELEVATED_WITHIN_HOURS = 7 * 24
PACE_WINDOW_HOURS = 24            # pace = the last 24 complete hours        [PROPOSED]
MIN_HOURS_FOR_PROJECTION = 24     # less collected data -> insufficient_data [PROPOSED]

# History = 7 x 24 h of collected data [E-DECIDED D5 definition, 2026-10-27]
HISTORY_HOURS = 7 * 24
BASELINE_MIN_REQUESTS = 1_000     # burn multiplier needs a real baseline [CONTRACT A.7.5.1]

# No recent activity [E-DECIDED N5; rule PROPOSED]: after 7 x 24 h of collection,
# zero Cloud Run requests in the last 7 x 24 h and zero stored bytes.
NO_ACTIVITY_HOURS = 7 * 24

# -----------------------------------------------------------------------------
# Copy
# -----------------------------------------------------------------------------
# STATE-001, copied verbatim [CONTRACT A.5]
STATE_001_EXPLANATION = (
    "Calculating Initial Burn Rate Metrics. Your data will appear here within 5–10 minutes."
)

# -----------------------------------------------------------------------------
# Run safeguards (BR-70, ledger lexie_006 §4)
# -----------------------------------------------------------------------------
API_TIMEOUT_SECONDS = 20.0
API_MAX_ATTEMPTS = 2           # one retry, never more
API_RETRY_BACKOFF_SECONDS = 2.0

SPARKLINE_BUCKET_HOURS = 6     # [CONTRACT v1.3 C1]
HISTORY_BASES = ("devrails_start", "cloud_monitoring")


@dataclass(frozen=True)
class Settings:
    """Run settings. Built from env vars by `load_settings()`; tests build it directly."""

    gcp_project_id: str = ""
    firebase_project_id: str = ""
    uid: str = ""
    project_id: str = ""
    polling_interval_minutes: int = 10
    # Quota/billing project for Cloud Monitoring reads: the DevRails host project,
    # never the customer's (BR-74, E-DECIDED 2026-10-27). [VERIFY LEDGER-09]
    quota_project_id: str = ""
    # Where "collected history" starts (D5):
    #   devrails_start   (default): from sync_initialized_at — E: "data that we collected"
    #   cloud_monitoring (option):  everything Cloud Monitoring already holds counts
    history_basis: str = "devrails_start"
    api_timeout_seconds: float = API_TIMEOUT_SECONDS
    api_max_attempts: int = API_MAX_ATTEMPTS
    api_retry_backoff_seconds: float = API_RETRY_BACKOFF_SECONDS
    extra: dict = field(default_factory=dict)

    def quota_problem(self) -> str | None:
        """DevRails' reads must never be billed to the customer (E, 2026-10-27)."""
        if not self.quota_project_id:
            return "DEVRAILS_QUOTA_PROJECT_ID (or DEVRAILS_FIREBASE_PROJECT_ID) must name the DevRails host project"
        if self.quota_project_id == self.gcp_project_id:
            return "the quota project equals the monitored project; reads would be billed to the customer"
        return None

    def missing_for_live_run(self) -> list[str]:
        missing = []
        if not self.gcp_project_id:
            missing.append("DEVRAILS_GCP_PROJECT_ID")
        if not self.uid:
            missing.append("DEVRAILS_POC_USER_UID")
        if not self.project_id:
            missing.append("DEVRAILS_POC_PROJECT_ID")
        return missing


def load_settings(env: dict | None = None) -> Settings:
    env = os.environ if env is None else env
    basis = env.get("DEVRAILS_HISTORY_BASIS", "devrails_start")
    if basis not in HISTORY_BASES:
        raise ValueError(f"DEVRAILS_HISTORY_BASIS must be one of {HISTORY_BASES}, got {basis!r}")
    interval = int(env.get("DEVRAILS_POLLING_INTERVAL_MINUTES", "10"))
    if interval not in (5, 10):
        # 10 is the PoC cadence; 5 is demo-only and needs E's approval (SYNC-001).
        raise ValueError("DEVRAILS_POLLING_INTERVAL_MINUTES must be 10 (or 5 for an approved demo)")
    firebase = env.get("DEVRAILS_FIREBASE_PROJECT_ID", "")
    return Settings(
        gcp_project_id=env.get("DEVRAILS_GCP_PROJECT_ID", ""),
        firebase_project_id=firebase,
        uid=env.get("DEVRAILS_POC_USER_UID", ""),
        project_id=env.get("DEVRAILS_POC_PROJECT_ID", ""),
        polling_interval_minutes=interval,
        quota_project_id=env.get("DEVRAILS_QUOTA_PROJECT_ID", firebase),
        history_basis=basis,
    )

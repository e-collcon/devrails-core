"""
spike-engine — config.py
DevRails PoC | PRD-001 v1.0

Central configuration for spike-engine.

Loads environment variables for:
  - Target GCP project (operator-configured for PoC)
  - Local credential path (GOOGLE_APPLICATION_CREDENTIALS)
  - Firebase / Firestore project references
  - PoC user uid and project id for Firestore path construction

Metric config objects and Free Tier Watch threshold constants
are defined here in Phase 2 (TASK-045, TASK-053).
"""

import os

# -----------------------------------------------------------------------------
# GCP target project
# Operator-configured for PoC — no user-facing input
# -----------------------------------------------------------------------------
GCP_PROJECT_ID = os.environ.get("DEVRAILS_GCP_PROJECT_ID", "")

# -----------------------------------------------------------------------------
# Firebase / Firestore
# -----------------------------------------------------------------------------
FIREBASE_PROJECT_ID = os.environ.get("DEVRAILS_FIREBASE_PROJECT_ID", "")

# PoC operator-configured user and project for Firestore path
# Canonical path: users/{uid}/projects/{projectId}/dashboard_feed/current
POC_USER_UID = os.environ.get("DEVRAILS_POC_USER_UID", "")
POC_PROJECT_ID = os.environ.get("DEVRAILS_POC_PROJECT_ID", "")

# -----------------------------------------------------------------------------
# Polling config
# Default is 10 minutes per PRD-001 v1.0 §7.2 and SYNC-001
# 5 minutes is demo-only and requires E approval
# -----------------------------------------------------------------------------
POLLING_INTERVAL_MINUTES = int(os.environ.get("DEVRAILS_POLLING_INTERVAL_MINUTES", "10"))

# -----------------------------------------------------------------------------
# Guardrail mode (locked for PoC)
# Machine-readable enum — do not change to "Free Tier Watch"
# -----------------------------------------------------------------------------
GUARDRAIL_MODE = "free_tier"
GUARDRAIL_LABEL = "Free Tier Watch"

# -----------------------------------------------------------------------------
# Metric configuration — scaffold
# Full metric config objects implemented in Phase 2 (TASK-045)
# -----------------------------------------------------------------------------
# TODO (TASK-045): Define reusable metric config structure
# TODO (TASK-053): Define Free Tier Watch threshold constants
METRICS = {}

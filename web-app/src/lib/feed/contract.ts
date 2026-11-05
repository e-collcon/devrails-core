// web-app/src/lib/feed/contract.ts
// DevRails Firestore Data Contract v1.3 — TypeScript mirror (LEDGER-12, BE-3).
// Python twin: spike-engine/engine/schema.py. Field names and enums are
// transcribed from the contract; never paraphrase them.

export type WrittenSystemStatus = "Pending" | "Normal" | "Elevated" | "Risky" | "Sync Failed"; // A.7.1
export type AbsoluteThresholdStatus = "within_limit" | "near_limit" | "over_limit";
export type VelocityStatus = "stable" | "elevated" | "accelerating" | "insufficient_data";
export type MetricRole = "primary_burn_rate_signal" | "capacity_status_signal";
export type FreshnessProfile = "near_real_time" | "daily_or_delayed";
export type ValueWindow = "month_to_date" | "latest";

export const PRIMARY_REASONS = [ // v1.3 A.7.8
  "all_within_limits",
  "awaiting_initial_data",
  "no_recent_activity",
  "cloud_run_over_limit",
  "cloud_run_accelerating",
  "cloud_run_near_limit",
  "cloud_run_insufficient_history",
  "cloud_storage_over_limit",
  "cloud_storage_accelerating",
  "cloud_storage_near_limit",
  "cloud_storage_insufficient_history",
] as const;
// Unknown tokens are allowed through: the UI falls back to status_explanation (A.7.8).
export type PrimaryReason = (typeof PRIMARY_REASONS)[number] | (string & {});

export interface StatusModel {
  absolute_threshold_status: AbsoluteThresholdStatus;
  velocity_status: VelocityStatus;
  primary_reason: PrimaryReason;
}

export interface MetricObject {
  metric_id: string;
  metric_role: MetricRole;
  value_window: ValueWindow;
  window_started_at: string | null;
  current_value: number;
  free_tier_limit: number;
  usage_ratio: number;
  absolute_threshold_status: AbsoluteThresholdStatus;
  velocity_status: VelocityStatus; // v1.3: time left before the free tier runs out (A.7.5)
  projected_hours_to_limit: number | null; // v1.3 A.7.6
  burn_rate_multiplier: number | null; // display only in v1.3
  freshness_profile: FreshnessProfile;
  sparkline_data_points: number[]; // 1–28 six-hour Pacific buckets, oldest first
  sparkline_bucket_hours: 6;
  sparkline_last_bucket_started_at: string;
}

interface FeedBase {
  gcp_project_id: string;
  guardrail_mode: "free_tier";
  guardrail_label: "Free Tier Watch";
  monthly_budget_usd: null;
  sync_initialized_at: string;
  status_explanation: string;
}

export interface StubFeed extends FeedBase {
  initial_sync_complete: false;
  last_sync_timestamp: null;
  system_status: "Pending";
}

export interface SyncedFeed extends FeedBase {
  initial_sync_complete: true;
  last_sync_timestamp: string;
  system_status: Exclude<WrittenSystemStatus, "Pending">;
  status_model: StatusModel;
  metrics: { cloud_run_requests: MetricObject; cloud_storage_bytes: MetricObject };
}

export type DashboardFeed = StubFeed | SyncedFeed;

export type ParseResult = { ok: true; feed: DashboardFeed } | { ok: false; errors: string[] };

const SYSTEM = new Set(["Pending", "Normal", "Elevated", "Risky", "Sync Failed"]);
const ABS = new Set(["within_limit", "near_limit", "over_limit"]);
const VEL = new Set(["stable", "elevated", "accelerating", "insufficient_data"]);
const ROLE = new Set(["primary_burn_rate_signal", "capacity_status_signal"]);
const FRESH = new Set(["near_real_time", "daily_or_delayed"]);
const WINDOW = new Set(["month_to_date", "latest"]);
const STUB_KEYS = [
  "gcp_project_id", "guardrail_mode", "guardrail_label", "monthly_budget_usd", "initial_sync_complete",
  "sync_initialized_at", "last_sync_timestamp", "system_status", "status_explanation",
];
const UTC_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isUtc = (v: unknown): v is string => typeof v === "string" && UTC_RE.test(v) && !Number.isNaN(Date.parse(v));

function checkMetric(key: string, m: unknown, errors: string[]) {
  if (!isObj(m)) return void errors.push(`metrics.${key} must be an object`);
  const at = (f: string) => `metrics.${key}.${f}`;
  if (typeof m.metric_id !== "string" || !m.metric_id) errors.push(`${at("metric_id")} missing`);
  if (!ROLE.has(m.metric_role as string)) errors.push(`${at("metric_role")} unknown`);
  if (!WINDOW.has(m.value_window as string)) errors.push(`${at("value_window")} unknown`);
  if (!ABS.has(m.absolute_threshold_status as string)) errors.push(`${at("absolute_threshold_status")} unknown`);
  if (!VEL.has(m.velocity_status as string)) errors.push(`${at("velocity_status")} unknown`);
  if (!FRESH.has(m.freshness_profile as string)) errors.push(`${at("freshness_profile")} unknown`);
  for (const f of ["current_value", "free_tier_limit", "usage_ratio"]) if (!isNum(m[f])) errors.push(`${at(f)} must be a number`);
  if (m.value_window === "month_to_date" && !isUtc(m.window_started_at)) errors.push(`${at("window_started_at")} must be UTC`);
  if (m.value_window === "latest" && m.window_started_at !== null) errors.push(`${at("window_started_at")} must be null`);
  if (m.burn_rate_multiplier !== null && !isNum(m.burn_rate_multiplier)) errors.push(`${at("burn_rate_multiplier")} invalid`);
  const proj = m.projected_hours_to_limit;
  if (proj === undefined || (proj !== null && (!isNum(proj) || proj < 0))) errors.push(`${at("projected_hours_to_limit")} invalid`);
  if (m.velocity_status === "insufficient_data" && proj !== null) errors.push(`${at("projected_hours_to_limit")} must be null`);
  if ((m.velocity_status === "elevated" || m.velocity_status === "accelerating") && proj == null) {
    errors.push(`${at("projected_hours_to_limit")} required`);
  }
  if (m.sparkline_bucket_hours !== 6) errors.push(`${at("sparkline_bucket_hours")} must be 6`);
  if (!isUtc(m.sparkline_last_bucket_started_at)) errors.push(`${at("sparkline_last_bucket_started_at")} must be UTC`);
  const spark = m.sparkline_data_points;
  if (!Array.isArray(spark) || !spark.every(isNum) || spark.length < 1 || spark.length > 28) {
    errors.push(`${at("sparkline_data_points")} must hold 1–28 numbers`);
  }
}

/** Runtime check of a Firestore snapshot. A failure is displayed as Sync Failed with last-known data (A.9). */
export function parseFeed(raw: unknown): ParseResult {
  const errors: string[] = [];
  if (!isObj(raw)) return { ok: false, errors: ["document must be an object"] };
  for (const k of STUB_KEYS) if (!(k in raw)) errors.push(`${k} missing`);
  if (raw.guardrail_mode !== "free_tier") errors.push("guardrail_mode must be free_tier");
  if (raw.monthly_budget_usd !== null) errors.push("monthly_budget_usd must be null");
  if (!SYSTEM.has(raw.system_status as string)) errors.push("system_status unknown");
  if (!isUtc(raw.sync_initialized_at)) errors.push("sync_initialized_at must be UTC");
  if (typeof raw.status_explanation !== "string") errors.push("status_explanation must be a string");
  if (raw.initial_sync_complete === true) {
    if (!isUtc(raw.last_sync_timestamp)) errors.push("last_sync_timestamp must be UTC");
    const sm = raw.status_model;
    if (!isObj(sm) || !ABS.has(sm.absolute_threshold_status as string) || !VEL.has(sm.velocity_status as string) || typeof sm.primary_reason !== "string") {
      errors.push("status_model invalid");
    }
    const metrics = raw.metrics;
    if (!isObj(metrics)) errors.push("metrics missing");
    else for (const key of ["cloud_run_requests", "cloud_storage_bytes"]) checkMetric(key, metrics[key], errors);
  } else if (raw.initial_sync_complete === false) {
    if (raw.last_sync_timestamp !== null) errors.push("last_sync_timestamp must be null in a stub");
  } else {
    errors.push("initial_sync_complete must be a boolean");
  }
  return errors.length ? { ok: false, errors } : { ok: true, feed: raw as unknown as DashboardFeed };
}

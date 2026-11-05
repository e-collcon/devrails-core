// web-app/src/lib/feed/viewModel.ts
// Turns a derived A.9 state plus the feed into everything the dashboard renders.
// Pure and framework-free, so it is unit-tested without React.
//
// Rules kept here (Contract v1.3 A.9 "Display rules"):
//  - status comes from the backend; nothing is re-derived from raw numbers
//  - metric labels come from value_window; freshness from freshness_profile
//  - insufficient_data gets its own "Not enough history yet" treatment
//  - velocity is shown with its time to the limit (projected_hours_to_limit, N4)
//  - no_recent_activity shows a notice the user can dismiss (N5; browser-only in the PoC)
//  - usage is labelled as this project's usage; the allowance is account-wide (P3)
// Copy is placeholder until Lexie's UX-001 pass; it matches the reviewed canvas.

import type { MetricObject, SyncedFeed } from "./contract";
import type { DerivedState, UiState } from "./deriveState";
import { SLOT_LABELS, ago, count, dayLabel, gb, hoursText, pacificParts, pct, times, utcClock } from "./format";

export const LOWER = 0.75; // display copy only — the backend owns classification
export const UPPER = 0.9;

export type Zone = "within" | "near" | "over";
export type ToneKey = "normal" | "elevated" | "risky" | "neutral" | "info";

export interface Tone {
  key: ToneKey;
  label: string;
}

export interface Step {
  status: "done" | "active" | "waiting" | "problem";
  label: string;
  /** May contain "{time}", rendered as the viewer's local time of `timeIso`. */
  detail: string;
  timeIso?: string;
}

export interface Bar {
  /** 0–100, share of the chart height. */
  height: number;
  fill: "run" | Zone | "empty";
  current: boolean;
  title: string;
}

export interface DayColumn {
  label: string;
  /** One entry per slot; `null` = a future slot of today (nothing drawn). */
  bars: (Bar | null)[];
}

export interface TrendView {
  caption: string;
  days: DayColumn[];
  summary: string;
  aria: string;
  thresholds?: { lower: number; upper: number }; // bottom offsets in % of chart height
}

export interface VelocityView {
  text: string;
  kind: "stable" | "rising" | "accelerating" | "insufficient";
  /** Time to the limit at the current pace, from projected_hours_to_limit. */
  detail: string;
}

export interface MetricCardView {
  title: string;
  roleLabel: string;
  windowLabel: string;
  freshnessLabel: string;
  valueText: string;
  limitText: string;
  pctText: string;
  ratio: number;
  zone: Zone;
  chipLabel: string;
  barAria: string;
  burnText: string;
  velocity: VelocityView;
  emphasis: "none" | "elevated" | "risky";
  overText?: string;
  trend: TrendView;
}

export interface RiskView {
  happening: string;
  changed: string;
  next: string;
}

export interface DashboardView {
  state: UiState;
  projectId: string | null;
  subtitle: string;
  tone: Tone | null;
  explanation: string;
  reasonLabel: string;
  steps: Step[];
  lastSyncShort: string;
  pending?: { title: string; body: string; delayed: boolean };
  dataBanner?: { kind: "stale" | "failed"; title: string; body: string; timeIso?: string };
  dimmed: boolean;
  insufficientHistory: boolean;
  run?: MetricCardView;
  storage?: MetricCardView;
  risk?: RiskView;
  /** N5: shown when primary_reason is no_recent_activity. */
  notice?: { title: string; body: string; dismissKey: string };
}

const CHIP: Record<string, { zone: Zone; label: string }> = {
  within_limit: { zone: "within", label: "Below lower threshold" },
  near_limit: { zone: "near", label: "Past lower threshold" },
  over_limit: { zone: "over", label: "Past upper threshold" },
};

const VELOCITY: Record<string, Omit<VelocityView, "detail">> = {
  stable: { text: "Stable", kind: "stable" },
  elevated: { text: "Rising", kind: "rising" },
  accelerating: { text: "Accelerating", kind: "accelerating" },
  insufficient_data: { text: "Not enough history yet", kind: "insufficient" },
};

const MONTH = 30 * 24;

/** v1.3 A.7.5/A.7.6: the band word plus the time left at the current pace. */
function velocityView(m: MetricObject): VelocityView {
  const base = VELOCITY[m.velocity_status];
  const h = m.projected_hours_to_limit;
  const run = m.value_window === "month_to_date";
  let detail: string;
  if (m.velocity_status === "insufficient_data") detail = "Needs a full day of readings";
  else if (h === 0) detail = m.velocity_status === "accelerating" ? "Past the allowance and still growing" : "Past the allowance, not growing";
  else if (h == null) detail = run ? "Not on track to run out this month" : "Not growing at the moment";
  else if (h > MONTH) detail = run ? "Not on track to run out this month" : "Not on track to fill up within 30 days";
  else detail = `${run ? "Runs out" : "Fills up"} in ${hoursText(h)} at this pace`;
  return { ...base, detail };
}

const WINDOW_LABEL: Record<string, string> = {
  month_to_date: "This month (since 1st, Pacific Time)",
  latest: "Current total",
};
const ROLE_LABEL: Record<string, string> = {
  primary_burn_rate_signal: "Primary spike signal",
  capacity_status_signal: "Capacity signal",
};
const FRESHNESS_LABEL: Record<string, string> = {
  near_real_time: "Near real-time · checked every 10 min",
  daily_or_delayed: "Reported daily by GCP · may lag",
};

function reasonLabel(token: string): string {
  if (token === "all_within_limits") return "All signals below the lower threshold";
  if (token === "no_recent_activity") return "No recent activity";
  if (token.endsWith("_insufficient_history")) return "Trend not known yet";
  if (token.startsWith("cloud_run_")) return "Responsible: Cloud Run requests";
  if (token.startsWith("cloud_storage_")) return "Responsible: Cloud Storage";
  return "See explanation";
}

// --- trend charts -------------------------------------------------------------------

interface TrendInput {
  metric: MetricObject;
  toChart: (v: number) => number; // value in the unit the bars are scaled in
  max: number;
  fill: (v: number) => Bar["fill"];
  fmt: (v: number) => string;
}

/** v1.3 C1: 7 Pacific-day columns x 4 six-hour slots, anchored on sparkline_last_bucket_started_at. */
function buildDays({ metric, toChart, max, fill, fmt }: TrendInput) {
  const values = metric.sparkline_data_points;
  const n = values.length;
  const anchor = pacificParts(metric.sparkline_last_bucket_started_at);
  const perDay = 4;
  const lastG = 6 * perDay + Math.floor(anchor.hour / 6);
  const firstG = lastG - n + 1;
  let collecting = false;
  const index: { g: number; label: string; value: number }[] = [];
  const days: DayColumn[] = [];
  for (let d = 0; d < 7; d++) {
    const label = dayLabel(anchor, d - 6);
    const bars: (Bar | null)[] = [];
    for (let k = 0; k < perDay; k++) {
      const g = d * perDay + k;
      const slot = `${label} ${SLOT_LABELS[k]} PT`;
      if (g > lastG) {
        bars.push(null);
        continue;
      }
      const j = g - firstG;
      if (j < 0) {
        collecting = true;
        bars.push({ height: 0, fill: "empty", current: false, title: `${slot} · no data yet` });
        continue;
      }
      const v = values[j];
      const current = g === lastG;
      index.push({ g, label: slot, value: v });
      bars.push({
        height: Math.max(2, (toChart(v) / max) * 100),
        fill: fill(v),
        current,
        title: `${slot} · ${fmt(v)}${current ? " (so far)" : ""}`,
      });
    }
    days.push({ label, bars });
  }
  return { days, collecting, index, slots: lastG + 1, n };
}

function runTrend(m: MetricObject): TrendView {
  const values = m.sparkline_data_points;
  const max = Math.max(1, ...values) * 1.15;
  const t = buildDays({ metric: m, max, toChart: (v) => v, fill: () => "run", fmt: (v) => `${count(v)} requests` });
  let summary: string;
  if (t.collecting) {
    summary = `Collecting history: ${t.n} of ${t.slots} six-hour buckets so far. The latest bucket is still filling.`;
  } else if (values.every((v) => v === 0)) {
    summary = "No requests in the last 7 days.";
  } else {
    const past = t.index.slice(0, -1);
    const peak = past.reduce((a, b) => (b.value > a.value ? b : a), past[0] ?? t.index[0]);
    summary = `Peak: ${count(peak.value)} requests (${peak.label}). The latest bucket is still filling.`;
  }
  return {
    caption: "Requests per 6 hours",
    days: t.days,
    summary,
    aria: `Bar chart of Cloud Run requests per six-hour bucket over the last 7 days. ${summary}`,
  };
}

function storageTrend(m: MetricObject): TrendView {
  const limit = m.free_tier_limit;
  const ratios = m.sparkline_data_points.map((v) => v / limit);
  const max = Math.max(1, ...ratios) * 1.1;
  const t = buildDays({
    metric: m, max, toChart: (v) => v / limit,
    fill: (v) => (v / limit >= UPPER ? "over" : v / limit >= LOWER ? "near" : "within"),
    fmt: (v) => `${gb(v)} · ${pct(v / limit)}`,
  });
  const now = pct(m.usage_ratio);
  let summary: string;
  if (t.collecting) {
    summary = `Collecting history: ${t.n} of ${t.slots} readings so far. Now ${now} of the free tier.`;
  } else if (m.sparkline_data_points.every((v) => v === 0)) {
    summary = "No stored data in the last 7 days.";
  } else {
    const firstAt = (threshold: number) => t.index.find((p) => p.value / limit >= threshold);
    const c90 = firstAt(UPPER);
    const c100 = firstAt(1);
    const day = (p: { label: string }) => p.label.split(" ").slice(0, 2).join(" ");
    if (c100 && c100 === t.index[0]) summary = `Above the free-tier allowance for the whole period shown. Now ${now}.`;
    else if (c100 && c90) summary = `Crossed the 90% upper threshold on ${day(c90)} and the free-tier allowance on ${day(c100)}. Now ${now}.`;
    else if (c90 && c90 !== t.index[0]) summary = `Crossed the 90% upper threshold on ${day(c90)}. Now ${now}.`;
    else summary = `Now ${now} of the free tier. Bars turn amber past the 75% lower threshold and red past the 90% upper threshold (dashed lines).`;
  }
  return {
    caption: "Total stored, every 6 hours",
    days: t.days,
    summary,
    aria: `Bar chart of total Cloud Storage at each six-hour mark over the last 7 days, with the 75% and 90% thresholds. ${summary}`,
    thresholds: { lower: (LOWER / max) * 100, upper: (UPPER / max) * 100 },
  };
}

// --- metric cards ---------------------------------------------------------------------

function emphasis(feed: SyncedFeed, prefix: string): MetricCardView["emphasis"] {
  const reason = feed.status_model.primary_reason;
  if (!reason.startsWith(prefix) || reason.endsWith("insufficient_history")) return "none";
  if (feed.system_status === "Risky") return "risky";
  if (feed.system_status === "Elevated") return "elevated";
  return "none";
}

function runCard(feed: SyncedFeed): MetricCardView {
  const m = feed.metrics.cloud_run_requests;
  const chip = CHIP[m.absolute_threshold_status];
  return {
    title: "Cloud Run requests",
    roleLabel: ROLE_LABEL[m.metric_role],
    windowLabel: WINDOW_LABEL[m.value_window],
    freshnessLabel: FRESHNESS_LABEL[m.freshness_profile],
    valueText: count(m.current_value),
    limitText: count(m.free_tier_limit),
    pctText: pct(m.usage_ratio),
    ratio: m.usage_ratio,
    zone: chip.zone,
    chipLabel: chip.label,
    barAria: `Cloud Run requests at ${pct(m.usage_ratio)} of this month’s free-tier allowance; thresholds at 75% and 90%`,
    burnText: m.burn_rate_multiplier == null ? "—" : times(m.burn_rate_multiplier),
    velocity: velocityView(m),
    emphasis: emphasis(feed, "cloud_run_"),
    trend: runTrend(m),
  };
}

function storageCard(feed: SyncedFeed): MetricCardView {
  const m = feed.metrics.cloud_storage_bytes;
  const chip = CHIP[m.absolute_threshold_status];
  return {
    title: "Cloud Storage",
    roleLabel: ROLE_LABEL[m.metric_role],
    windowLabel: WINDOW_LABEL[m.value_window],
    freshnessLabel: FRESHNESS_LABEL[m.freshness_profile],
    valueText: gb(m.current_value),
    limitText: gb(m.free_tier_limit),
    pctText: pct(m.usage_ratio),
    ratio: m.usage_ratio,
    zone: chip.zone,
    chipLabel: chip.label,
    barAria: `Cloud Storage at ${pct(m.usage_ratio)} of the free-tier allowance; thresholds at 75% and 90%`,
    burnText: "n/a",
    velocity: velocityView(m),
    emphasis: emphasis(feed, "cloud_storage_"),
    overText: m.usage_ratio > 1 ? `+${pct(m.usage_ratio - 1)} over free tier` : undefined,
    trend: storageTrend(m),
  };
}

// --- "What this means" ------------------------------------------------------------------

function riskPanel(state: UiState, feed: SyncedFeed, minutesSinceSync: number | null): RiskView {
  const run = feed.metrics.cloud_run_requests;
  const sto = feed.metrics.cloud_storage_bytes;
  const token = feed.status_model.primary_reason;
  const when = minutesSinceSync == null ? "" : ` (${ago(minutesSinceSync)})`;

  if (state === "SyncFailed" || state === "Stale") {
    // status_model is untouched by a failed poll, so it still describes the last success (A.8).
    const worst = feed.status_model.absolute_threshold_status;
    return {
      happening: state === "SyncFailed"
        ? `DevRails couldn’t complete its latest sync. These are the last known readings${when}.`
        : `DevRails hasn’t completed a sync recently. These are the last known readings${when}.`,
      changed:
        worst === "within_limit" ? "At the last successful sync, both signals were below the 75% lower threshold."
        : worst === "near_limit" ? "At the last successful sync, at least one signal was past the 75% lower threshold."
        : "At the last successful sync, at least one signal was past the 90% upper threshold.",
      next: state === "SyncFailed"
        ? "Nothing you need to do yet. DevRails will try again on its next scheduled check."
        : "Nothing you need to do yet. If this lasts more than a few hours, contact the DevRails team.",
    };
  }

  const runPace = run.burn_rate_multiplier == null ? null : times(run.burn_rate_multiplier);
  const paceNote = runPace ? ` (${runPace} the usual daily pace)` : "";
  if (token === "no_recent_activity") {
    return {
      happening: "DevRails can reach this project, but nothing is happening in it.",
      changed: "No Cloud Run requests and no stored data in the last 7 days.",
      next: "If it’s quiet on purpose, mark it as intentional. If you don’t need it watched, ask the DevRails team to stop monitoring it, so you’re not paying to watch an empty project.",
    };
  }
  if (token === "all_within_limits" || token.endsWith("_insufficient_history")) {
    const young = token.endsWith("_insufficient_history");
    return {
      happening: "Both monitored signals are below the 75% lower threshold.",
      changed: young
        ? "DevRails started collecting less than a day ago, so it can’t project the trend yet."
        : "Nothing unusual. At the last 24 hours’ pace, neither signal is on track to run out of its free tier this month.",
      next: young
        ? "Nothing right now. The projection appears after a full day of readings."
        : "Nothing right now. DevRails keeps checking every 10 minutes.",
    };
  }
  if (token.startsWith("cloud_run_")) {
    const h = run.projected_hours_to_limit;
    const changed =
      run.velocity_status === "insufficient_data" ? "There isn’t enough history yet to project how fast requests are climbing."
      : h === 0 ? "This month’s free requests are used up; every further request is billable."
      : h != null && h <= 7 * 24 ? `At the last 24 hours’ pace, the free tier runs out in ${hoursText(h)}${paceNote}.`
      : `No sudden spike — requests have built up steadily this month${paceNote}.`;
    return {
      happening: feed.status_explanation.split(/(?<=\.)\s/)[0],
      changed,
      next: "Look for unexpected traffic: bots, retry loops, or a scheduled job calling your service more often than planned.",
    };
  }
  if (token.startsWith("cloud_storage_")) {
    const h = sto.projected_hours_to_limit;
    const changed =
      sto.velocity_status === "insufficient_data" ? "There isn’t enough history yet to project how fast storage is growing."
      : h === 0 && sto.velocity_status === "accelerating" ? "Storage is past the free allowance and still growing."
      : h != null && h > 0 && h <= 7 * 24 ? `At the last day’s growth, storage fills the free allowance in ${hoursText(h)}.`
      : "No sudden spike — storage has grown steadily.";
    return {
      happening: `Cloud Storage holds ${gb(sto.current_value)} — ${pct(sto.usage_ratio)} of the ${gb(sto.free_tier_limit)} free allowance.`,
      changed,
      next: "Review your largest buckets, then delete objects or add lifecycle rules for data you no longer need.",
    };
  }
  return { happening: feed.status_explanation, changed: "—", next: "DevRails keeps checking every 10 minutes." };
}

// --- page view --------------------------------------------------------------------------

const TONES: Partial<Record<UiState, Tone>> = {
  Normal: { key: "normal", label: "Normal" },
  Elevated: { key: "elevated", label: "Elevated" },
  Risky: { key: "risky", label: "Risky" },
  SyncFailed: { key: "neutral", label: "Sync failed" },
  Stale: { key: "neutral", label: "Readings out of date" },
  Pending: { key: "info", label: "Calculating first readings" },
  SyncDelayed: { key: "neutral", label: "Sync delayed" },
};

export function buildDashboardView(d: DerivedState): DashboardView {
  const { state, feed, synced, minutesSinceInit, minutesSinceSync } = d;
  const projectId = feed?.gcp_project_id ?? null;
  const base: DashboardView = {
    state,
    projectId,
    subtitle: projectId ? `Free Tier Watch · ${projectId}` : "Free Tier Watch · no project connected",
    tone: TONES[state] ?? null,
    explanation: "",
    reasonLabel: "",
    steps: [],
    lastSyncShort: "",
    dimmed: state === "Stale" || state === "SyncFailed",
    insufficientHistory: false,
  };
  if (state === "SignedOut" || state === "NoConfiguredProject") return base;

  const connected: Step = { status: "done", label: "Project connected", detail: projectId ?? "—" };

  if (state === "Pending" || state === "SyncDelayed") {
    const delayed = state === "SyncDelayed";
    const started = minutesSinceInit == null ? "" : `Started ${ago(minutesSinceInit)}`;
    const [title, ...rest] = (feed?.status_explanation ?? "").split(/(?<=\.)\s/);
    return {
      ...base,
      explanation: delayed
        ? "Your first sync is taking longer than usual. Nothing is lost — DevRails is still working on it."
        : "DevRails is calculating initial usage signals for this configured GCP project.",
      reasonLabel: delayed ? started : "First readings in 5–10 min",
      steps: [
        connected,
        delayed
          ? { status: "problem", label: "First sync taking longer than usual", detail: started }
          : { status: "active", label: "First sync in progress", detail: started },
        { status: "waiting", label: "Live monitoring", detail: "Starts after the first sync" },
      ],
      lastSyncShort: "No successful sync yet",
      pending: delayed
        ? {
            delayed,
            title: "This is taking a little longer than usual",
            body: "Your first readings usually arrive within 15 minutes. DevRails is still working on it — there’s nothing you need to do right now.",
          }
        : { delayed, title: title.replace(/\.$/, ""), body: rest.join(" ") }, // STATE-001, verbatim
    };
  }

  if (!synced) {
    // Sync Failed because the snapshot failed the contract check and nothing valid is known yet.
    return {
      ...base,
      explanation: "DevRails received an update it couldn’t read. It will try again on its next check.",
      reasonLabel: "No readable data",
      steps: [connected, { status: "problem", label: "Latest update unreadable", detail: "Waiting for the next sync" }],
      lastSyncShort: "No readable sync",
      dimmed: false,
    };
  }

  const lastIso = synced.last_sync_timestamp;
  const agoText = minutesSinceSync == null ? "" : ago(minutesSinceSync);
  const lastDetail = `Last successful sync {time} · ${agoText}`;
  const run = runCard(synced);
  const storage = storageCard(synced);
  const insufficientHistory = run.velocity.kind === "insufficient" || storage.velocity.kind === "insufficient";
  const live: Step =
    state === "SyncFailed" ? { status: "problem", label: "Latest sync failed", detail: lastDetail, timeIso: lastIso }
    : state === "Stale" ? { status: "problem", label: "No recent sync", detail: lastDetail, timeIso: lastIso }
    : { status: "active", label: "Live monitoring", detail: "Last successful sync {time} · every 10 min", timeIso: lastIso };

  return {
    ...base,
    explanation:
      state === "Stale"
        ? "DevRails hasn’t completed a sync recently. Showing the last known readings; data may be out of date."
        : synced.status_explanation,
    reasonLabel: state === "Stale" || state === "SyncFailed" ? "Last known data" : reasonLabel(synced.status_model.primary_reason),
    steps: [connected, { status: "done", label: "First sync complete", detail: "Readings available" }, live],
    lastSyncShort: `Last successful sync ${agoText}`,
    dataBanner:
      state === "Stale" || state === "SyncFailed"
        ? {
            kind: state === "Stale" ? "stale" : "failed",
            title: state === "Stale" ? "Readings may be out of date." : "The latest sync failed.",
            body: `Showing the last known numbers from {time} (${agoText}).`,
            timeIso: lastIso,
          }
        : undefined,
    insufficientHistory,
    run,
    storage,
    risk: riskPanel(state, synced, minutesSinceSync),
    notice:
      synced.status_model.primary_reason === "no_recent_activity" && state === "Normal"
        ? {
            title: "This project has been quiet for 7 days",
            body: "DevRails can reach it, but there have been no Cloud Run requests and no stored data all week. If that’s on purpose, mark it as intentional. If you don’t need it watched, you may not want to keep paying to monitor an empty project.",
            dismissKey: `devrails-quiet-ack:${synced.gcp_project_id}:${synced.sync_initialized_at}`,
          }
        : undefined,
  };
}

export { utcClock };

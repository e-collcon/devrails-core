// web-app/src/lib/feed/deriveState.ts
// Contract v1.3 A.9 (order unchanged from v1.2) — frontend state derivation (normative). First match wins.
// The UI never re-derives Normal / Elevated / Risky from raw numbers; it only
// adds the time-based states the backend cannot write (Sync Delayed, Stale).

import { parseFeed, type DashboardFeed, type SyncedFeed } from "./contract";

export const PENDING_WINDOW_MINUTES = 15; // A.9 #3–4
export const STALE_AFTER_MINUTES = 30; // A.9 #5 — [PENDING D4; rec 30 min]

export type UiState =
  | "SignedOut"
  | "NoConfiguredProject"
  | "Pending"
  | "SyncDelayed"
  | "Stale"
  | "SyncFailed"
  | "Normal"
  | "Elevated"
  | "Risky";

export interface DerivedState {
  state: UiState;
  /** The data to render. For Stale / Sync Failed this is last-known data. */
  feed: DashboardFeed | null;
  synced: SyncedFeed | null;
  minutesSinceInit: number | null;
  minutesSinceSync: number | null;
  /** Set when the snapshot failed the contract check (shown as Sync Failed). */
  schemaErrors?: string[];
}

const minutesBetween = (fromIso: string, now: Date) => (now.getTime() - Date.parse(fromIso)) / 60000;

/**
 * @param raw        the Firestore snapshot data (`undefined` = document absent)
 * @param lastKnown  the last snapshot that passed the contract check, if any
 */
export function deriveState(args: {
  signedIn: boolean;
  raw: unknown | undefined;
  now: Date;
  lastKnown?: SyncedFeed | null;
}): DerivedState {
  const { signedIn, raw, now, lastKnown = null } = args;
  const base = { feed: null, synced: null, minutesSinceInit: null, minutesSinceSync: null };

  if (!signedIn) return { state: "SignedOut", ...base }; // 1
  if (raw === undefined || raw === null) return { state: "NoConfiguredProject", ...base }; // 2

  const parsed = parseFeed(raw);
  if (!parsed.ok) {
    // Unknown enum or failed schema check → Sync Failed display with last-known data.
    return {
      state: "SyncFailed",
      feed: lastKnown,
      synced: lastKnown,
      minutesSinceInit: null,
      minutesSinceSync: lastKnown ? minutesBetween(lastKnown.last_sync_timestamp, now) : null,
      schemaErrors: parsed.errors,
    };
  }
  const feed = parsed.feed;
  const sinceInit = minutesBetween(feed.sync_initialized_at, now);

  if (!feed.initial_sync_complete) {
    return {
      state: sinceInit <= PENDING_WINDOW_MINUTES ? "Pending" : "SyncDelayed", // 3, 4
      feed,
      synced: null,
      minutesSinceInit: sinceInit,
      minutesSinceSync: null,
    };
  }

  const sinceSync = minutesBetween(feed.last_sync_timestamp, now);
  const common = { feed, synced: feed, minutesSinceInit: sinceInit, minutesSinceSync: sinceSync };
  if (sinceSync > STALE_AFTER_MINUTES) return { state: "Stale", ...common }; // 5
  if (feed.system_status === "Sync Failed") return { state: "SyncFailed", ...common }; // 6
  return { state: feed.system_status, ...common }; // 7
}

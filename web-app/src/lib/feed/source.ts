// web-app/src/lib/feed/source.ts
// Where the dashboard feed comes from.
//
//   fixtures  (default) engine-generated documents in src/fixtures/dashboard-feed.json,
//             produced by `python spike-engine/main.py export-fixtures`
//   firestore (next)    onSnapshot on users/{uid}/projects/{projectId}/dashboard_feed/current,
//             read-only, behind Firebase Auth — TASK-010/012 (auth) and TASK-083 (read helper)
//
// The dashboard only ever receives `{ raw, now }`, so swapping the source does not
// touch any component.

import fixtures from "@/fixtures/dashboard-feed.json";

export type FeedSourceKind = "fixtures" | "firestore";

export const FEED_SOURCE: FeedSourceKind =
  process.env.NEXT_PUBLIC_DEVRAILS_FEED_SOURCE === "firestore" ? "firestore" : "fixtures";

export interface FixtureEntry {
  label: string;
  as_of: string;
  note: string;
  doc: unknown | null;
}

const STATES = (fixtures as { states: Record<string, FixtureEntry> }).states;

export const FIXTURE_KEYS = Object.keys(STATES);
export const DEFAULT_FIXTURE = "normal";

export function getFixture(key: string | undefined): { key: string; entry: FixtureEntry } {
  const k = key && STATES[key] ? key : DEFAULT_FIXTURE;
  return { key: k, entry: STATES[k] };
}

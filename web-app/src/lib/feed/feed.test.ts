// A.9 state derivation, the contract guard, and the dashboard view model —
// run against the engine-generated fixtures so both halves agree.
import { describe, expect, it } from "vitest";
import fixtures from "@/fixtures/dashboard-feed.json";
import { parseFeed, type SyncedFeed } from "./contract";
import { deriveState } from "./deriveState";
import { buildDashboardView } from "./viewModel";

type Entry = { as_of: string; doc: unknown };
const states = (fixtures as { states: Record<string, Entry> }).states;
const at = (iso: string, minutes: number) => new Date(Date.parse(iso) + minutes * 60000);
const derive = (key: string, now?: Date) =>
  deriveState({ signedIn: true, raw: states[key].doc ?? undefined, now: now ?? new Date(states[key].as_of) });

describe("contract guard", () => {
  it("accepts every engine fixture", () => {
    for (const [key, s] of Object.entries(states)) {
      if (s.doc === null) continue;
      const r = parseFeed(s.doc);
      expect(r.ok, `${key}: ${!r.ok && r.errors.join(", ")}`).toBe(true);
    }
  });
  it("rejects unknown enums and malformed sparklines", () => {
    const doc = structuredClone(states.normal.doc) as SyncedFeed;
    expect(parseFeed({ ...doc, system_status: "Stale" }).ok).toBe(false);
    const bad = structuredClone(doc);
    bad.metrics.cloud_run_requests.sparkline_data_points = [];
    expect(parseFeed(bad).ok).toBe(false);
  });
});

describe("A.9 state derivation (first match wins)", () => {
  it("1 signed out", () => {
    expect(deriveState({ signedIn: false, raw: states.normal.doc, now: new Date() }).state).toBe("SignedOut");
  });
  it("2 absent document", () => expect(derive("no_project").state).toBe("NoConfiguredProject"));
  it("3 pending within 15 min, 4 delayed after", () => {
    expect(derive("pending").state).toBe("Pending");
    expect(derive("sync_delayed").state).toBe("SyncDelayed");
    const init = (states.pending.doc as { sync_initialized_at: string }).sync_initialized_at;
    expect(derive("pending", at(init, 15)).state).toBe("Pending");
    expect(derive("pending", at(init, 15.1)).state).toBe("SyncDelayed");
  });
  it("5 stale beats Sync Failed after 30 min", () => {
    expect(derive("stale").state).toBe("Stale");
    const last = (states.sync_failed.doc as SyncedFeed).last_sync_timestamp;
    expect(derive("sync_failed").state).toBe("SyncFailed");
    expect(derive("sync_failed", at(last, 31)).state).toBe("Stale");
  });
  it("7 renders the backend status, never re-derived", () => {
    expect(derive("normal").state).toBe("Normal");
    expect(derive("elevated").state).toBe("Elevated");
    expect(derive("rising").state).toBe("Elevated");
    expect(derive("risky").state).toBe("Risky");
    expect(derive("runs_out_soon").state).toBe("Risky");
    expect(derive("no_activity").state).toBe("Normal");
  });
  it("a failed contract check shows Sync Failed with last-known data", () => {
    const last = states.normal.doc as SyncedFeed;
    const d = deriveState({ signedIn: true, raw: { ...last, system_status: "Weird" }, now: new Date(states.normal.as_of), lastKnown: last });
    expect(d.state).toBe("SyncFailed");
    expect(d.synced).toBe(last);
    expect(d.schemaErrors?.length).toBeGreaterThan(0);
  });
});

describe("dashboard view model", () => {
  const view = (key: string) => buildDashboardView(derive(key));

  it("pending copies STATE-001 verbatim and hides metric cards", () => {
    const v = view("pending");
    expect(`${v.pending?.title}. ${v.pending?.body}`).toBe(
      "Calculating Initial Burn Rate Metrics. Your data will appear here within 5–10 minutes.",
    );
    expect(v.run).toBeUndefined();
  });

  it("six-hour trend: 7 day columns, 4 slots, future slots of today empty", () => {
    const t = view("normal").run!.trend;
    expect(t.days).toHaveLength(7);
    expect(t.days.every((d) => d.bars.length === 4)).toBe(true);
    const today = t.days[6].bars;
    expect(today.filter((b) => b === null)).toHaveLength(1); // Sun 12:55 PT → the 18:00 slot is in the future
    expect(today[2]?.current).toBe(true);
    expect(t.days[0].label).toBe("Mon 19");
    expect(t.days[6].label).toBe("Sun 25");
  });

  it("rejects a v1.2-shaped document (no six-hour fields, no projection)", () => {
    const doc = structuredClone(states.normal.doc) as SyncedFeed;
    const m = doc.metrics.cloud_run_requests as unknown as Record<string, unknown>;
    delete m.projected_hours_to_limit;
    delete m.sparkline_bucket_hours;
    delete m.sparkline_last_bucket_started_at;
    expect(parseFeed(doc).ok).toBe(false);
  });

  it("N4: velocity shows the time left at the current pace", () => {
    expect(view("runs_out_soon").run!.velocity).toMatchObject({ text: "Accelerating", detail: "Runs out in about 30 hours at this pace" });
    expect(view("rising").run!.velocity).toMatchObject({ text: "Rising", detail: "Runs out in about 5 days at this pace" });
    expect(view("normal").run!.velocity.detail).toBe("Not on track to run out this month");
    expect(view("risky").storage!.velocity.detail).toBe("Past the allowance and still growing");
    expect(view("runs_out_soon").run!.emphasis).toBe("risky");
  });

  it("N5: a quiet project is Normal with a dismissible notice", () => {
    const v = view("no_activity");
    expect(v.tone?.label).toBe("Normal");
    expect(v.notice?.title).toMatch(/quiet for 7 days/);
    expect(v.notice?.dismissKey).toContain("devrails-quiet-ack:");
    expect(v.run!.trend.summary).toBe("No requests in the last 7 days.");
    expect(view("normal").notice).toBeUndefined();
  });

  it("short history gets 'no data yet' stubs, never zero padding", () => {
    const t = view("insufficient_history").run!.trend;
    const empties = t.days.flatMap((d) => d.bars).filter((b) => b?.fill === "empty");
    expect(empties.length).toBeGreaterThan(0);
    expect(t.summary).toMatch(/^Collecting history/);
    expect(view("insufficient_history").run!.velocity).toMatchObject({ text: "Not enough history yet", detail: "Needs a full day of readings" });
  });

  it("storage bars are zoned and thresholds drawn; over-allowance badge shows", () => {
    const s = view("risky").storage!;
    expect(s.zone).toBe("over");
    expect(s.overText).toBe("+15% over free tier");
    expect(s.trend.thresholds!.upper).toBeGreaterThan(s.trend.thresholds!.lower);
    expect(s.emphasis).toBe("risky");
    expect(view("risky").run!.emphasis).toBe("none");
  });

  it("stale and failed keep last-known data, dimmed, with a banner", () => {
    for (const key of ["stale", "sync_failed"]) {
      const v = view(key);
      expect(v.run && v.storage).toBeTruthy();
      expect(v.dimmed).toBe(true);
      expect(v.dataBanner?.kind).toBe(key === "stale" ? "stale" : "failed");
    }
  });

  it("labels come from value_window and freshness_profile", () => {
    const v = view("normal");
    expect(v.run!.windowLabel).toBe("This month (since 1st, Pacific Time)");
    expect(v.storage!.windowLabel).toBe("Current total");
    expect(v.storage!.freshnessLabel).toMatch(/daily/);
  });
});

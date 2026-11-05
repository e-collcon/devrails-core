// web-app/src/lib/feed/format.ts
// Display formatting only. Billing windows are never computed here (A.2):
// Pacific dates are used solely to label chart columns.

export const GIB = 1073741824;
export const PACIFIC = "America/Los_Angeles";

export function pct(ratio: number): string {
  const n = Math.round(ratio * 1000) / 10;
  return (Number.isInteger(n) ? n.toFixed(0) : n.toFixed(1)) + "%";
}

/** Binary GB, as the contract asks the UI to format bytes (A.9 Units). */
export function gb(bytes: number): string {
  const g = bytes / GIB;
  return (Number.isInteger(Math.round(g * 100) / 100) ? g.toFixed(0) : g.toFixed(2)) + " GB";
}

export const count = (n: number) => Math.round(n).toLocaleString("en-US");

export function times(multiplier: number): string {
  return multiplier.toFixed(2).replace(/0+$/, "").replace(/\.$/, "") + "×";
}

export function ago(minutes: number): string {
  if (minutes < 1) return "just now";
  if (minutes < 120) return `${Math.floor(minutes)} min ago`;
  const h = Math.floor(minutes / 60);
  return h < 48 ? `${h} h ago` : `${Math.floor(h / 24)} days ago`;
}

export interface PacificParts {
  year: number;
  month: number;
  day: number;
  hour: number;
}

export function pacificParts(iso: string): PacificParts {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: PACIFIC,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return { year: get("year"), month: get("month"), day: get("day"), hour: get("hour") % 24 };
}

/** "Sun 25" for the Pacific calendar day `offset` days from (year, month, day). */
export function dayLabel(p: Pick<PacificParts, "year" | "month" | "day">, offset = 0): string {
  const d = new Date(Date.UTC(p.year, p.month - 1, p.day + offset, 12));
  const wd = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short" }).format(d);
  return `${wd} ${d.getUTCDate()}`;
}

export const SLOT_LABELS = ["00:00–06:00", "06:00–12:00", "12:00–18:00", "18:00–24:00"];

/** "HH:MM UTC" — server-side fallback; <LocalTime> swaps in the viewer's zone (A.2 Display). */
export function utcClock(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
}

/** "about 30 hours" / "about 5 days" — for projected_hours_to_limit (v1.3 A.7.6). */
export function hoursText(hours: number): string {
  if (hours < 1) return "under an hour";
  if (hours < 48) {
    const h = Math.round(hours);
    return `about ${h} hour${h === 1 ? "" : "s"}`;
  }
  return `about ${Math.round(hours / 24)} days`;
}

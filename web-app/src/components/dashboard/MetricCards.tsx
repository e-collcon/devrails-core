// Cloud Run Request Progress Bar + Cloud Storage Capacity Gauge (TASK-084..090).
import type { MetricCardView } from "@/lib/feed/viewModel";
import { BarTrend } from "./BarTrend";

function Velocity({ v }: { v: MetricCardView["velocity"] }) {
  return (
    <>
      <dd className={`vel-${v.kind}`}>{v.text}</dd>
      <dd className="note">{v.detail}</dd>
    </>
  );
}

function CardHead({ m, stale }: { m: MetricCardView; stale: boolean }) {
  return (
    <div className="dr-card-head">
      <div>
        <h2>{m.title}</h2>
        <span className="dr-eyebrow">
          {m.roleLabel} · {m.windowLabel}
        </span>
      </div>
      <div className="dr-chips">
        {stale && <span className="dr-stale-chip">STALE</span>}
        <span className={`dr-zone-chip zone-${m.zone}`}>{m.chipLabel}</span>
      </div>
    </div>
  );
}

function cardClass(m: MetricCardView, dimmed: boolean) {
  return `dr-card metric${dimmed ? " is-dimmed" : ""}${m.emphasis !== "none" ? ` emph-${m.emphasis}` : ""}`;
}

const SHARED_NOTE = "This project's usage · the free-tier allowance is shared across your billing account";

export function CloudRunCard({ m, dimmed }: { m: MetricCardView; dimmed: boolean }) {
  return (
    <section aria-label="Cloud Run requests" className={cardClass(m, dimmed)}>
      <CardHead m={m} stale={dimmed} />
      <div className="dr-big">
        <span className="dr-big-num">{m.valueText}</span>
        <span className="dr-big-of">of {m.limitText} free requests this month</span>
      </div>
      <div className={`zone-${m.zone}`}>
        <div className="dr-progress">
          <div role="img" aria-label={m.barAria} className="dr-progress-track">
            <div className="dr-progress-fill" style={{ width: `${(Math.min(m.ratio, 1) * 100).toFixed(1)}%` }} />
          </div>
          <span aria-hidden="true" className="dr-tick dr-tick-lo" />
          <span aria-hidden="true" className="dr-tick dr-tick-hi" />
        </div>
        <div aria-hidden="true" className="dr-scale">
          <span style={{ left: 0 }}>0</span>
          <span className="lo">75%</span>
          <span className="hi">90%</span>
        </div>
      </div>
      <dl className="dr-stats">
        <div><dt>Used</dt><dd>{m.pctText}</dd></div>
        <div><dt>Burn rate</dt><dd>{m.burnText}</dd></div>
        <div><dt>Velocity</dt><Velocity v={m.velocity} /></div>
      </dl>
      <BarTrend trend={m.trend} />
      <div className="dr-card-foot">
        <span>{SHARED_NOTE}</span>
        <span className="dr-mono">{m.freshnessLabel}</span>
      </div>
    </section>
  );
}

const ARC = 282.74; // length of the 180° gauge arc (r = 90)

export function StorageCard({ m, dimmed }: { m: MetricCardView; dimmed: boolean }) {
  return (
    <section aria-label="Cloud Storage capacity" className={cardClass(m, dimmed)}>
      <CardHead m={m} stale={dimmed} />
      <div className={`dr-gauge-row zone-${m.zone}`}>
        <div className="dr-gauge">
          <div className="dr-gauge-box">
            <svg role="img" aria-label={m.barAria} width="200" height="116" viewBox="0 0 220 124">
              <path className="dr-gauge-track" d="M 20 112 A 90 90 0 0 1 200 112" fill="none" strokeWidth="16" strokeLinecap="round" />
              <path className="dr-gauge-fill" d="M 20 112 A 90 90 0 0 1 200 112" fill="none" strokeWidth="16" strokeLinecap="round"
                style={{ strokeDasharray: `${(Math.min(m.ratio, 1) * ARC).toFixed(1)} 400` }} />
              {[
                [0.75, "dr-gauge-tick-lo"],
                [0.9, "dr-gauge-tick-hi"],
              ].map(([t, cls]) => (
                <g key={cls as string} style={{ transform: `rotate(${((t as number) * 180).toFixed(1)}deg)`, transformOrigin: "110px 112px" }}>
                  <line className="dr-gauge-tick-bg" x1="8" y1="112" x2="32" y2="112" strokeWidth="6" strokeLinecap="round" />
                  <line className={cls as string} x1="8" y1="112" x2="32" y2="112" strokeWidth="3" strokeLinecap="round" />
                </g>
              ))}
            </svg>
            <div className="dr-gauge-label">
              <b>{m.pctText}</b>
              <span>of free tier</span>
            </div>
          </div>
          <div aria-hidden="true" className="dr-legend">
            <span className="lo"><i />75% lower</span>
            <span className="hi"><i />90% upper</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
          <span className="dr-big-num">{m.valueText}</span>
          <span className="dr-big-of">of {m.limitText} free storage</span>
          {m.overText && <span className="dr-over-badge">{m.overText}</span>}
        </div>
      </div>
      <dl className="dr-stats">
        <div><dt>Used</dt><dd>{m.pctText}</dd></div>
        <div><dt>Burn rate</dt><dd className="na">n/a</dd><dd className="note">Not used for capacity</dd></div>
        <div><dt>Velocity</dt><Velocity v={m.velocity} /></div>
      </dl>
      <BarTrend trend={m.trend} />
      <div className="dr-card-foot">
        <span>{SHARED_NOTE}</span>
        <span className="dr-mono">{m.freshnessLabel}</span>
      </div>
    </section>
  );
}

// 7-day bar trend: 7 Pacific-day columns, 4 six-hour bars each
// (Contract v1.3 C1). The current bucket is drawn at 45% opacity
// ("so far"); slots before the data begins get a 2px "no data yet" stub; today's
// future slots are left empty. Never padded with zeros (A.7.3).
import type { TrendView } from "@/lib/feed/viewModel";

export function BarTrend({ trend }: { trend: TrendView }) {
  const gutter = !!trend.thresholds;
  return (
    <div className="dr-trend">
      <div className="dr-trend-head">
        <span>{trend.caption}</span>
        <span>LAST 7 DAYS · PACIFIC TIME</span>
      </div>
      <div role="img" aria-label={trend.aria} className={`dr-plot${gutter ? " has-gutter" : ""}`}>
        {!gutter && (
          <>
            <div aria-hidden="true" className="dr-gridline" style={{ top: 0 }} />
            <div aria-hidden="true" className="dr-gridline" style={{ top: "50%" }} />
          </>
        )}
        <div className="dr-cols">
          {trend.days.map((day) => (
            <div className="dr-col" key={day.label}>
              {day.bars.map((b, k) =>
                b === null ? (
                  <div key={k} aria-hidden="true" className="dr-bar is-future" />
                ) : (
                  <div
                    key={k}
                    title={b.title}
                    className={`dr-bar f-${b.fill}${b.current ? " is-current" : ""}`}
                    style={b.fill === "empty" ? undefined : { height: `${b.height.toFixed(1)}%` }}
                  />
                ),
              )}
            </div>
          ))}
        </div>
        {trend.thresholds && (
          <>
            <div aria-hidden="true" className="dr-thr lo" style={{ bottom: `${trend.thresholds.lower.toFixed(1)}%` }} />
            <div aria-hidden="true" className="dr-thr hi" style={{ bottom: `${trend.thresholds.upper.toFixed(1)}%` }} />
            <span aria-hidden="true" className="dr-thr-label lo" style={{ bottom: `${trend.thresholds.lower.toFixed(1)}%` }}>75%</span>
            <span aria-hidden="true" className="dr-thr-label hi" style={{ bottom: `${trend.thresholds.upper.toFixed(1)}%` }}>90%</span>
          </>
        )}
      </div>
      <div aria-hidden="true" className={`dr-days${gutter ? " has-gutter" : ""}`}>
        {trend.days.map((d) => (
          <span key={d.label}>{d.label}</span>
        ))}
      </div>
      <p>{trend.summary}</p>
    </div>
  );
}

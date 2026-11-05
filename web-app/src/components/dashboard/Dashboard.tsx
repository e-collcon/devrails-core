// DevRails dashboard (EPIC-010/011). Renders a DashboardView; holds no data logic.
// Layout and styling follow the canvas Dashboard and dev.thedevrails.com.
import type { DashboardView, Step } from "@/lib/feed/viewModel";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { WithTime } from "./LocalTime";
import { CloudRunCard, StorageCard } from "./MetricCards";
import { QuietNotice } from "./QuietNotice";
import "./dashboard.css";

const CloudIcon = ({ size = 16 }: { size?: number }) => (
  <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 18a5 5 0 0 1-.7-9.95A6 6 0 0 1 18 9a4 4 0 0 1-1 9z" />
  </svg>
);

function AppHeader({ projectId }: { projectId: string | null }) {
  return (
    <header className="dr-header">
      <div className="dr-header-in">
        <div className="dr-brand-row">
          <a href="/dashboard" className="dr-brand">DevRails</a>
          <nav aria-label="App" className="dr-nav">
            <a href="/dashboard" aria-current="page">Dashboard</a>
          </nav>
        </div>
        <div className="dr-actions">
          {projectId && (
            <span className="dr-project-pill">
              <CloudIcon />
              {projectId}
            </span>
          )}
          <ThemeToggle />
          <span aria-label="Signed-in user" role="img" className="dr-avatar">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></svg>
          </span>
          {/* TODO (TASK-012): wire to Firebase Auth signOut */}
          <a href="/" className="dr-signout">Sign out</a>
        </div>
      </div>
    </header>
  );
}

function StatusBanner({ v }: { v: DashboardView }) {
  if (!v.tone) return null;
  return (
    <section aria-label="Global status" className={`dr-banner tone-${v.tone.key}`}>
      <div className="dr-banner-body">
        <span aria-hidden="true" className="dr-banner-dot" />
        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          <span className="dr-eyebrow">System status</span>
          <h2>{v.tone.label}</h2>
          <p>{v.explanation}</p>
        </div>
      </div>
      <span className="dr-banner-reason">{v.reasonLabel}</span>
    </section>
  );
}

function ModeCard() {
  return (
    <section aria-label="Guardrail mode" className="dr-card" style={{ gap: 14 }}>
      <div className="dr-card-head" style={{ alignItems: "center" }}>
        <span className="dr-eyebrow">Guardrail mode</span>
        <span className="dr-active">ACTIVE</span>
      </div>
      <div className="dr-mode-title">
        <span aria-hidden="true" className="dr-mode-ico">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" /><path d="M9 12l2 2 4-4" /></svg>
        </span>
        <h2>Free Tier Watch</h2>
      </div>
      <p style={{ margin: 0, fontSize: 15 }} className="dr-muted">
        Compares your usage with GCP free-tier allowances and flags how fast it&apos;s climbing.
      </p>
      <div className="dr-pills">
        <span className="dr-pill dr-pill-warn">Elevated from 75%</span>
        <span className="dr-pill dr-pill-err">Risky from 90%</span>
        <span style={{ fontSize: 13 }} className="dr-muted">of each free-tier allowance · fixed during early access</span>
      </div>
      <div className="dr-pills">
        <span className="dr-tag">Cloud Run requests</span>
        <span className="dr-tag">Cloud Storage bytes</span>
      </div>
    </section>
  );
}

function StepDot({ s }: { s: Step }) {
  return (
    <span aria-hidden="true" className={`dr-step-dot step-${s.status}`}>
      {s.status === "done" && (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-10" /></svg>
      )}
      {s.status === "problem" && (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M12 6v8" /><path d="M12 18h.01" /></svg>
      )}
    </span>
  );
}

function SyncTracker({ v }: { v: DashboardView }) {
  return (
    <section aria-label="Sync status" className="dr-card">
      <div className="dr-card-head" style={{ alignItems: "center" }}>
        <span className="dr-eyebrow">Sync status</span>
        <span className="dr-mono dr-muted" style={{ fontSize: 12 }}>{v.lastSyncShort}</span>
      </div>
      <ol className="dr-steps">
        {v.steps.map((s) => (
          <li key={s.label}>
            <StepDot s={s} />
            <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
              <span className="dr-step-label">{s.label}</span>
              <span className="dr-step-detail"><WithTime text={s.detail} iso={s.timeIso} /></span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function EmptyState() {
  return (
    <section aria-labelledby="empty-title" className="dr-empty">
      <span aria-hidden="true" className="dr-empty-ico">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M7 18a5 5 0 0 1-.7-9.95A6 6 0 0 1 18 9a4 4 0 0 1-1 9z" /><path d="M12 11v4" /><path d="M10 13h4" /></svg>
      </span>
      <span className="dr-mono" style={{ fontSize: 12, fontWeight: 500, color: "var(--deep-azure)" }}>[ NO PROJECT CONNECTED ]</span>
      <h2 id="empty-title">Your account is ready. Your project isn&apos;t connected yet.</h2>
      <p>During early access, the DevRails team connects your GCP project for you — there&apos;s nothing to upload. Once it&apos;s connected, your Free Tier Watch dashboard will appear here.</p>
      {/* [CONTACT LINK] — Lexie/E to supply the early-access contact address */}
      <a href="#" className="dr-cta">Contact the DevRails team</a>
    </section>
  );
}

function PendingPanel({ p }: { p: NonNullable<DashboardView["pending"]> }) {
  return (
    <section aria-labelledby="pending-title" className={`dr-pending${p.delayed ? " is-delayed" : ""}`}>
      <svg className="dr-spinner" aria-hidden="true" width="44" height="44" viewBox="0 0 44 44" fill="none">
        <circle cx="22" cy="22" r="18" strokeWidth="4" />
        <path d="M22 4a18 18 0 0 1 18 18" strokeWidth="4" strokeLinecap="round" />
      </svg>
      <h2 id="pending-title">{p.title}</h2>
      <p>{p.body}</p>
      <span className="dr-mono dr-muted" style={{ fontSize: 12 }}>Usage cards appear after the first successful sync</span>
    </section>
  );
}

function DataBanner({ b }: { b: NonNullable<DashboardView["dataBanner"]> }) {
  return (
    <div role="status" className="dr-databanner">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l9.5 17h-19z" /><path d="M12 10v4" /><path d="M12 17h.01" /></svg>
      <strong>{b.title}</strong>
      <span><WithTime text={b.body} iso={b.timeIso} /></span>
    </div>
  );
}

function RiskPanel({ r }: { r: NonNullable<DashboardView["risk"]> }) {
  return (
    <section aria-labelledby="risk-title" className="dr-card dr-risk">
      <h2 id="risk-title">What this means</h2>
      <div className="dr-risk-grid">
        <div><span>WHAT&apos;S HAPPENING</span><p>{r.happening}</p></div>
        <div><span>WHAT CHANGED</span><p>{r.changed}</p></div>
        <div><span>WHAT TO CHECK NEXT</span><p>{r.next}</p></div>
      </div>
    </section>
  );
}

export function Dashboard({ view, preview }: { view: DashboardView; preview?: React.ReactNode }) {
  const hasProject = view.state !== "NoConfiguredProject";
  return (
    <div className="dr-app">
      {preview}
      <AppHeader projectId={view.projectId} />
      <main className="dr-main">
        <div className="dr-heading">
          <div>
            <h1>Dashboard</h1>
            <p>{view.subtitle}</p>
          </div>
          <span className="dr-mono dr-muted" style={{ fontSize: 12 }}>Source: Cloud Monitoring · checks every 10 min</span>
        </div>

        {!hasProject && <EmptyState />}

        {hasProject && (
          <>
            <StatusBanner v={view} />
            {view.notice && <QuietNotice notice={view.notice} />}
            <div className="dr-grid-2">
              <ModeCard />
              <SyncTracker v={view} />
            </div>
          </>
        )}

        {view.pending && <PendingPanel p={view.pending} />}

        {view.run && view.storage && (
          <>
            {view.dataBanner && <DataBanner b={view.dataBanner} />}
            <div className="dr-grid-metrics">
              <CloudRunCard m={view.run} dimmed={view.dimmed} />
              <StorageCard m={view.storage} dimmed={view.dimmed} />
            </div>
            {view.risk && <RiskPanel r={view.risk} />}
          </>
        )}

        <p className="dr-disclaimer">
          DevRails watches usage signals and warns you early. It doesn&apos;t guarantee you won&apos;t be billed — you stay in control of your GCP project.
        </p>
      </main>
    </div>
  );
}

import { AlertTriangle } from "lucide-react";

/* =====================================================================
   Shared auth primitives — EPIC-016 / EPIC-017.

   The LIVE app ships a Google-only /signin (PRD-001 TASK-155/161) wired to
   real Firebase Auth (TASK-012). Field/validEmail are kept only because the
   parked full-suite variant under src/_parked/auth-full-suite/ still imports
   them; MOCK_USERS/GoogleModal/openCenteredPopup were dropped here since the
   live flow now calls signInWithPopup(auth, googleProvider) directly instead
   of a mocked popup window.
===================================================================== */

/** DevRails wordmark shown above the card title (TASK-155/160: the logo
    belongs inside the card itself, not only in the page chrome). */
export function AuthLogo() {
  return (
    <img
      src="/devrails-logo-black.png"
      alt="DevRails"
      className="mx-auto mb-5 block"
      style={{ height: 28 }}
    />
  );
}

/* Multicolour Google "G" — not a Lucide glyph, so inlined. */
export function GoogleIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="m6.306 14.691 6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}

/** Page chrome: technical grid, bracket labels, header, footer. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="section-grid" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <style>{AUTH_CSS}</style>

      <div className="tech-grid tech-grid-fade" style={{ position: "fixed", inset: 0, pointerEvents: "none", opacity: 0.5 }} />
      <span className="bracket-label" style={{ position: "fixed", left: "6%", top: "16%", pointerEvents: "none" }}>[ AUTH.FIREBASE ]</span>
      <span className="bracket-label" style={{ position: "fixed", right: "7%", top: "22%", pointerEvents: "none" }}>[ SESSION.SECURE ]</span>
      <span className="crosshair" style={{ position: "fixed", left: "12%", bottom: "24%" }} />
      <span className="crosshair" style={{ position: "fixed", right: "14%", bottom: "18%" }} />

      <header style={{ position: "relative", zIndex: 10 }}>
        <div className="mx-auto flex h-[72px] max-w-[1200px] items-center justify-between px-6">
          <a href="/">
            <img src="/devrails-logo-black.png" alt="DevRails" style={{ height: 26, display: "block" }} />
          </a>
          <span className="font-mono text-[11px] text-ink-muted">{"// GCP usage guardrails · $1/month"}</span>
        </div>
      </header>

      <main
        style={{
          position: "relative",
          zIndex: 10,
          flex: 1,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          padding: "40px 24px 80px",
        }}
      >
        {children}
      </main>

      <footer
        className="font-mono text-ink-muted"
        style={{ position: "relative", zIndex: 10, padding: "0 24px 24px", textAlign: "center", fontSize: 11 }}
      >
        {"// an Elmscorp product · firebase auth · © 2026"}
      </footer>
    </div>
  );
}

/** Card-level error banner (Firebase-code messaging). */
export function Callout({ msg }: { msg: string }) {
  if (!msg) return null;
  return (
    <div className="au-callout">
      <AlertTriangle size={16} />
      <span>{msg}</span>
    </div>
  );
}

/** Labelled input with inline field-level validation error. Kept only for
    src/_parked/auth-full-suite/. */
export function Field({
  label,
  required,
  error,
  children,
}: {
  label: React.ReactNode;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`au-field${error ? " show-err" : ""}`}>
      {label}
      {children}
      {error ? <span className="au-field-err">{error}</span> : null}
      {required ? null : null}
    </div>
  );
}

/** Kept only for src/_parked/auth-full-suite/. */
export function validEmail(e: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}

export function Spinner({ dark, size = 16 }: { dark?: boolean; size?: number }) {
  return <span className={`au-spin${dark ? " dark" : ""}`} style={{ height: size, width: size }} />;
}

export const AUTH_CSS = `
.au-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:10px;font-weight:600;cursor:pointer;text-decoration:none;transition:background-color .15s,color .15s,border-color .15s;border:1px solid transparent;font-family:var(--font-sans)}
.au-btn-primary{background:var(--flame);color:#fff}
.au-btn-primary:hover{background:var(--flame-hover);color:#fff}
.au-btn-primary:disabled{opacity:.6;cursor:default}
.au-btn-outline{background:#fff;color:var(--ink);border-color:var(--border)}
.au-btn-outline:hover{border-color:var(--flame);color:var(--flame);background:rgba(11,61,145,.05)}
.au-in{height:44px;width:100%;border-radius:10px;border:1px solid var(--border);background:#fff;padding:0 12px;font-size:15px;color:var(--ink);font-family:var(--font-sans);outline:none}
.au-in::placeholder{color:var(--ink-muted)}
.au-in:focus{border-color:var(--flame);box-shadow:0 0 0 2px rgba(11,61,145,.2)}
.au-field{display:flex;flex-direction:column;gap:6px}
.au-lbl{font-size:13px;font-weight:500;color:var(--ink)}
.au-field-err{display:flex;align-items:flex-start;gap:6px;font-size:12px;line-height:1.4;color:var(--danger-text)}
.au-field.show-err .au-in{border-color:var(--danger);box-shadow:0 0 0 2px rgba(239,68,68,.15)}
.au-callout{display:flex;align-items:flex-start;gap:8px;border-radius:10px;border:1px solid var(--danger-border);background:var(--danger-soft);padding:12px;font-size:13px;line-height:1.5;color:var(--danger-text)}
.au-callout svg{flex-shrink:0}
.au-link{font-size:13px;font-weight:500;color:var(--flame);cursor:pointer}
.au-link:hover{color:var(--flame-hover);text-decoration:underline;text-underline-offset:2px}
.au-gacct{display:flex;width:100%;align-items:center;gap:12px;border-radius:10px;border:1px solid transparent;background:none;padding:10px 12px;cursor:pointer;text-align:left;font-family:var(--font-sans)}
.au-gacct:hover{background:var(--surface)}
.au-spin{display:inline-block;border-radius:999px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;animation:au-sp .7s linear infinite}
.au-spin.dark{border-color:rgba(11,61,145,.25);border-top-color:var(--flame);border-width:3px}
@keyframes au-sp{to{transform:rotate(360deg)}}
.au-modal-bg{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;background:rgba(8,18,31,.45);backdrop-filter:blur(2px)}
.au-card{width:440px;max-width:calc(100vw - 32px);border-radius:22px;border:1px solid var(--border);background:#fff;padding:32px}
.au-divider{margin:20px 0;display:flex;align-items:center;gap:12px}
.au-divider span.line{flex:1;height:1px;background:var(--border)}
`;

"use client";
// N5 (E, 2026-10-27): a reachable project with no traffic and no stored data for
// 7 days gets a notice, so the user can confirm it is intentional and not pay to
// watch an empty project. PoC: the dismissal lives in this browser only, because
// the client never writes to Firestore (Contract A.1). A saved acknowledgement
// needs a client-writable document and a Security Rules change (MVP decision).
import { useEffect, useState } from "react";
import type { DashboardView } from "@/lib/feed/viewModel";

type Notice = NonNullable<DashboardView["notice"]>;

export function QuietNotice({ notice }: { notice: Notice }) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(notice.dismissKey) === "intentional");
    } catch {
      /* storage blocked: keep showing the notice */
    }
  }, [notice.dismissKey]);

  function markIntentional() {
    try {
      localStorage.setItem(notice.dismissKey, "intentional");
    } catch {
      /* storage blocked: hide for this page view only */
    }
    setDismissed(true);
  }

  if (dismissed) {
    return (
      <p role="status" className="dr-quiet-done">
        Marked as intentionally quiet on this browser. <button type="button" onClick={() => {
          try { localStorage.removeItem(notice.dismissKey); } catch { /* ignore */ }
          setDismissed(false);
        }}>Undo</button>
      </p>
    );
  }
  return (
    <section aria-labelledby="quiet-title" className="dr-quiet">
      <span aria-hidden="true" className="dr-quiet-ico">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-6 9 6v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" /><path d="M9 21V12h6v9" /></svg>
      </span>
      <div className="dr-quiet-body">
        <h2 id="quiet-title">{notice.title}</h2>
        <p>{notice.body}</p>
      </div>
      <div className="dr-quiet-actions">
        <button type="button" className="dr-btn-secondary" onClick={markIntentional}>It’s intentional</button>
        {/* [CONTACT LINK] — Lexie/E to supply the early-access contact address */}
        <a href="#" className="dr-btn-link">Stop monitoring it</a>
      </div>
    </section>
  );
}

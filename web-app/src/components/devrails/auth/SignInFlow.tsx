"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, signInWithPopup } from "firebase/auth";
import { AlertTriangle, Info, LifeBuoy } from "lucide-react";
import { auth, googleProvider } from "@/lib/firebase";
import { AUTH_CSS, AuthLogo, GoogleIcon, Spinner } from "@/components/devrails/auth/authShared";

/* =====================================================================
   Shared /signin card logic — EPIC-016/EPIC-017, PRD-001 (TASK-154-162,
   TASK-012).

   Wired to real Firebase Auth: onAuthStateChanged drives both the initial
   "do we already have a session" check and the post-sign-in redirect;
   signInWithPopup(auth, googleProvider) opens the real Google account
   picker (a real, separate browser-native popup) instead of the app's own
   mock /google-picker route.
===================================================================== */

type Phase = "resolving" | "idle" | "connecting" | "redirecting" | "terminal";
type Notice =
  | null
  | { kind: "error"; variant: "cancelled" | "popup-blocked" | "network" }
  | { kind: "info"; variant: "session-expired" };

const ERROR_COPY: Record<"cancelled" | "popup-blocked" | "network", string> = {
  cancelled: "Sign-in was cancelled before it finished. You can try again whenever you're ready.",
  "popup-blocked": "Your browser blocked the Google sign-in window. Allow pop-ups for this site, then try again.",
  network: "We couldn't reach Google. Check your connection and try again.",
};

const isDev = process.env.NODE_ENV !== "production";

export function SignInFlow({
  initialReason,
  initialState,
}: {
  initialReason?: string;
  initialState?: string;
}) {
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>("resolving");
  const [notice, setNotice] = useState<Notice>(null);
  const redirectEmail = useRef("");

  /* Resolve the current session on mount, and drive the post-sign-in
     redirect from the same listener — both are just "auth state changed
     to a signed-in user" from Firebase's point of view. */
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        redirectEmail.current = user.email ?? "";
        setNotice(null);
        setPhase("redirecting");
        const provider = user.providerData[0]?.providerId ?? "google.com";
        setTimeout(() => {
          const params = new URLSearchParams({ email: redirectEmail.current, provider });
          router.push(`/signed-in?${params.toString()}`);
        }, 900);
        return;
      }

      if (isDev && initialState) {
        applyStateParam(initialState);
        return;
      }
      if (initialReason === "session-expired") {
        setNotice({ kind: "info", variant: "session-expired" });
      }
      setPhase("idle");
    });
    return () => unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyStateParam(s: string) {
    switch (s) {
      case "resolving":
        setPhase("resolving");
        return;
      case "connecting":
        setPhase("connecting");
        return;
      case "redirecting":
        setPhase("redirecting");
        return;
      case "err-disabled":
      case "terminal":
        setPhase("terminal");
        return;
      case "err-cancelled":
        setNotice({ kind: "error", variant: "cancelled" });
        setPhase("idle");
        return;
      case "err-popup-blocked":
        setNotice({ kind: "error", variant: "popup-blocked" });
        setPhase("idle");
        return;
      case "err-network":
        setNotice({ kind: "error", variant: "network" });
        setPhase("idle");
        return;
      case "info-session-expired":
        setNotice({ kind: "info", variant: "session-expired" });
        setPhase("idle");
        return;
      default:
        setPhase("idle");
    }
  }

  async function startGoogle() {
    setNotice(null);
    setPhase("connecting");
    try {
      await signInWithPopup(auth, googleProvider);
      // onAuthStateChanged above picks up the new session and moves to "redirecting".
    } catch (err) {
      const code = (err as { code?: string } | null)?.code;
      if (code === "auth/user-disabled") {
        setPhase("terminal");
        return;
      }
      setPhase("idle");
      if (code === "auth/popup-closed-by-user") {
        setNotice({ kind: "error", variant: "cancelled" });
      } else if (code === "auth/popup-blocked") {
        setNotice({ kind: "error", variant: "popup-blocked" });
      } else {
        // auth/network-request-failed and any other/unexpected code fall back
        // to the network notice — closest generic "something went wrong, retry".
        setNotice({ kind: "error", variant: "network" });
      }
    }
  }

  /* ---- full-card states (replace the default card entirely) ---- */

  if (phase === "resolving") {
    return (
      <>
        <style>{AUTH_CSS}</style>
        <StatusCard label="[ AUTH.RESOLVING ]">
          <Spinner dark size={26} />
          <h1 className="mt-4 text-[20px] font-bold tracking-[-0.02em] text-ink">Checking your session…</h1>
          <p className="mt-2 text-[14px] text-ink-soft">One moment while we confirm whether you&apos;re already signed in.</p>
        </StatusCard>
      </>
    );
  }

  if (phase === "redirecting") {
    return (
      <>
        <style>{AUTH_CSS}</style>
        <StatusCard label="[ AUTH.REDIRECTING ]">
          <Spinner dark size={26} />
          <h1 className="mt-4 text-[20px] font-bold tracking-[-0.02em] text-ink">Signing you in…</h1>
          <p className="mt-2 text-[14px] text-ink-soft">
            Signed in as <strong className="text-ink">{redirectEmail.current}</strong>. Redirecting to DevRails.
          </p>
        </StatusCard>
      </>
    );
  }

  if (phase === "terminal") {
    return (
      <>
        <style>{AUTH_CSS}</style>
        <div className="au-card shadow-card text-center">
          <AuthLogo />
          <span
            className="mx-auto grid h-12 w-12 place-items-center rounded-full"
            style={{ background: "var(--danger-soft)", color: "var(--danger-text)" }}
          >
            <AlertTriangle size={22} />
          </span>
          <h1 className="mt-4 text-[24px] font-bold tracking-[-0.02em] text-ink">Account disabled</h1>
          <p className="mt-2 text-[14px] leading-[1.55] text-ink-soft">
            This DevRails account has been disabled. If you think this is a mistake, our team can help sort it out.
          </p>
          <a
            className="au-btn au-btn-outline mt-6 h-11 w-full text-[14px] font-medium"
            href="mailto:support@thedevrails.com?subject=Disabled%20DevRails%20account"
          >
            <LifeBuoy size={16} />
            Contact support
          </a>
          <p className="mt-4 font-mono text-[11px] text-ink-muted">{"// auth/user-disabled · terminal state"}</p>
        </div>
      </>
    );
  }

  /* ---- default Google-only card (idle / connecting) ---- */

  return (
    <>
      <style>{AUTH_CSS}</style>
      <div>
        <div className="au-card shadow-card">
          <AuthLogo />
          <div className="text-center">
            <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">Sign in to DevRails</h1>
            <p className="mt-2 text-[14px] text-ink-soft">Keep your GCP usage on rails — for $1/month.</p>
          </div>

          {notice ? <div className="mt-5">{renderNotice(notice)}</div> : null}

          <button
            className="au-btn au-btn-outline mt-5 h-11 w-full text-[14px] font-medium"
            onClick={startGoogle}
            disabled={phase === "connecting"}
          >
            {phase === "connecting" ? (
              <>
                <Spinner dark />
                Connecting to Google…
              </>
            ) : (
              <>
                <GoogleIcon />
                {notice?.kind === "error" ? "Try again with Google" : "Continue with Google"}
              </>
            )}
          </button>

          <p className="mt-5 text-center text-[12px] leading-[1.6] text-ink-muted">
            By continuing you agree to the{" "}
            <a href="/terms" className="au-link text-[12px]">
              Terms
            </a>{" "}
            and{" "}
            <a href="/privacy" className="au-link text-[12px]">
              Privacy Policy
            </a>
            .
          </p>
        </div>

        {isDev ? (
          <p className="mt-4 text-center font-mono text-[11px] leading-[1.6] text-ink-muted">
            {"// preview states: /signin?state=err-network · err-popup-blocked · err-cancelled"}
            <br />
            {"// err-disabled · redirecting · resolving · info-session-expired"}
          </p>
        ) : null}
      </div>
    </>
  );
}

function StatusCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="au-card shadow-card text-center">
      <AuthLogo />
      <span className="bracket-label" style={{ display: "block", marginBottom: 18 }}>
        {label}
      </span>
      {children}
    </div>
  );
}

function renderNotice(notice: Exclude<Notice, null>) {
  if (notice.kind === "info") {
    return (
      <div
        className="flex items-start gap-2 rounded-[10px] border p-3 text-[13px] leading-[1.5]"
        style={{ borderColor: "rgba(11,61,145,.25)", background: "rgba(11,61,145,.06)", color: "var(--ink-soft)" }}
      >
        <Info size={16} style={{ flexShrink: 0, color: "var(--flame)" }} />
        <span>Your session expired for security. Please sign in again to pick up where you left off.</span>
      </div>
    );
  }
  return (
    <div className="au-callout">
      <AlertTriangle size={16} />
      <span>{ERROR_COPY[notice.variant]}</span>
    </div>
  );
}

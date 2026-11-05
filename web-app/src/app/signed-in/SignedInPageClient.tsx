"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, Gauge, Power } from "lucide-react";
import { onAuthStateChanged, signOut, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { AuthShell } from "@/components/devrails/auth/authShared";

/* EPIC-016/EPIC-017 auth-success page, wired to a real Firebase session
   (TASK-012). "Go to dashboard" points at "/" for now — DevRails doesn't
   have a dashboard route yet; "/" is the project-picker/home placeholder
   (see src/app/page.tsx). Swap the href once that route exists. */

export function SignedInPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const emailParam = searchParams.get("email") ?? undefined;
  const providerParam = searchParams.get("provider") ?? undefined;

  const [user, setUser] = useState<User | null>(null);
  const [expiresInMinutes, setExpiresInMinutes] = useState<number | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (u) => {
      setUser(u);
      if (!u) return;
      const result = await u.getIdTokenResult();
      const msRemaining = new Date(result.expirationTime).getTime() - Date.now();
      setExpiresInMinutes(Math.max(0, Math.round(msRemaining / 60000)));
    });
    return () => unsubscribe();
  }, []);

  async function handleSignOut() {
    await signOut(auth);
    router.push("/signin");
  }

  const email = user?.email ?? emailParam ?? "";
  const provider = user?.providerData[0]?.providerId ?? providerParam ?? "google.com";

  return (
    <AuthShell>
      <div
        className="shadow-card"
        style={{
          width: 520,
          maxWidth: "calc(100vw - 32px)",
          borderRadius: 22,
          border: "1px solid var(--border)",
          background: "#fff",
          padding: 32,
          textAlign: "center",
        }}
      >
        <span
          className="mx-auto grid h-[52px] w-[52px] place-items-center rounded-full"
          style={{ background: "rgba(53,198,167,.15)", color: "var(--glow)" }}
        >
          <Check size={24} />
        </span>
        <h1 className="mt-4 text-[26px] font-bold tracking-[-0.02em] text-ink">You are signed in</h1>
        <p className="mt-2 text-[14px] text-ink-soft">
          Signed in as <strong className="text-ink">{email}</strong>
        </p>

        <div className="mt-6 rounded-[14px] border border-border bg-surface p-4 text-left">
          <div className="flex items-center justify-between">
            <span className="bracket-label">[ SESSION ]</span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2 py-0.5 text-[11px] font-medium text-ink">
              <span
                className="animate-pulse-dot"
                style={{ height: 6, width: 6, borderRadius: 999, background: "var(--glow)" }}
              />
              Active
            </span>
          </div>
          <div className="mt-2.5 font-mono text-[12px] leading-[1.7] text-ink-soft">
            provider: <span className="text-ink">{provider}</span>
            <br />
            uid: <span className="text-ink">{user?.uid ?? "—"}</span>
            <br />
            token: {expiresInMinutes !== null ? `fresh · expires in ${expiresInMinutes}m` : "—"}
          </div>
        </div>

        <div className="mt-6 flex gap-2.5">
          <button
            className="au-btn au-btn-primary shadow-flame h-11 flex-1 text-[14px]"
            onClick={() => router.push("/")}
          >
            <Gauge size={16} />
            Go to dashboard
          </button>
          <button className="au-btn au-btn-outline h-11 px-[18px] text-[14px]" onClick={handleSignOut}>
            <Power size={16} />
            Sign out
          </button>
        </div>
      </div>
    </AuthShell>
  );
}

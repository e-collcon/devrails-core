import type { Metadata } from "next";
import { Suspense } from "react";
import { SignInPageClient } from "./SignInPageClient";

/* EPIC-016 /signin — GOOGLE-ONLY sign-in card (PRD-001 scope), wired to
   real Firebase Auth (TASK-012). Ported from devrails-landing-page
   (Vite + TanStack Router) per the EPIC-016 handoff — the landing page
   only links here, it never renders the sign-in card itself. */

export const metadata: Metadata = {
  title: "Sign in — DevRails",
  description: "Sign in to DevRails with Google.",
  robots: { index: false, follow: false },
};

export default function SignInPage() {
  return (
    <Suspense>
      <SignInPageClient />
    </Suspense>
  );
}

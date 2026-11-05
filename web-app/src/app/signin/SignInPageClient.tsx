"use client";

import { useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/devrails/auth/authShared";
import { SignInFlow } from "@/components/devrails/auth/SignInFlow";

export function SignInPageClient() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason") ?? undefined;
  const state = searchParams.get("state") ?? undefined;

  return (
    <AuthShell>
      <SignInFlow initialReason={reason} initialState={state} />
    </AuthShell>
  );
}

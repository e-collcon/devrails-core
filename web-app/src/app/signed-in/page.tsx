import type { Metadata } from "next";
import { Suspense } from "react";
import { SignedInPageClient } from "./SignedInPageClient";

export const metadata: Metadata = {
  title: "Signed in — DevRails",
  robots: { index: false, follow: false },
};

export default function SignedInPage() {
  return (
    <Suspense>
      <SignedInPageClient />
    </Suspense>
  );
}

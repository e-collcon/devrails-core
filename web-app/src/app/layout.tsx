import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DevRails",
  description: "GCP usage guardrail for builders — Free Tier Watch",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

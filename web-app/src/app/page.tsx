// DevRails — web-app root page
// PRD-001 v1.0 | Phase 1 scaffold
//
// Phase 3 (EPIC-002): This page will redirect authenticated users to /dashboard
// and unauthenticated users to /login via Firebase Auth state check.
// For now it renders a minimal placeholder.

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-2xl font-semibold text-gray-800">DevRails</h1>
      <p className="mt-2 text-gray-500">
        GCP usage guardrail — Free Tier Watch
      </p>
      <p className="mt-6 text-sm text-gray-400">
        Phase 1 scaffold — auth and dashboard implemented in Phase 3
      </p>
    </main>
  );
}

// DevRails — web-app home placeholder
// PRD-001 v1.0 | EPIC-016/EPIC-017
//
// Placeholder for the page users land on after signing in (see
// src/app/signed-in/SignedInPageClient.tsx). This will become the
// project/environment picker + settings/notifications/profile home;
// the real dashboard opens once a project is selected.
//
// TODO (EPIC-002, TASK-012): gate by auth state — signed-out users → /signin.
// Until a project picker exists, the Contract v1.3 dashboard (engine-generated
// fixtures) is linked from here.

export default function Home() {
  return (
    <main className="section-grid flex min-h-screen flex-col items-center justify-center p-8 text-center">
      <img src="/devrails-logo-black.png" alt="DevRails" className="mb-6 block" style={{ height: 32 }} />
      <h1 className="text-2xl font-semibold text-ink">Welcome to DevRails</h1>
      <p className="mt-3 max-w-[520px] text-sm text-ink-soft">
        This is the DevRails webapp homepage where users manage their projects, access
        settings, see notifications, and manage their profile. This is not yet the
        dashboard.
      </p>
      <a href="/dashboard" className="mt-6 text-sm font-semibold text-flame underline underline-offset-4">
        Open the dashboard preview
      </a>
    </main>
  );
}

// Server component: fixture → A.9 state → view model → <Dashboard>.
import { Dashboard } from "./Dashboard";
import { FIXTURE_KEYS, getFixture } from "@/lib/feed/source";
import { deriveState } from "@/lib/feed/deriveState";
import { buildDashboardView } from "@/lib/feed/viewModel";

function PreviewBar({ current }: { current: string }) {
  return (
    <div role="note" className="dr-preview">
      <span>
        <b>[ FIXTURE PREVIEW ]</b> Engine-generated sample data — not a live project.
      </span>
      <nav aria-label="Preview dashboard state">
        {FIXTURE_KEYS.map((k) => (
          <a key={k} href={`/dashboard/${k}`} aria-current={k === current ? "page" : undefined}>
            {getFixture(k).entry.label}
          </a>
        ))}
      </nav>
    </div>
  );
}

export function DashboardScreen({ fixtureKey }: { fixtureKey?: string }) {
  const { key, entry } = getFixture(fixtureKey);
  const derived = deriveState({
    signedIn: true, // TODO (TASK-012): Firebase Auth
    raw: entry.doc ?? undefined,
    now: new Date(entry.as_of), // fixtures carry their own "now" so time-based states are stable
  });
  return <Dashboard view={buildDashboardView(derived)} preview={<PreviewBar current={key} />} />;
}

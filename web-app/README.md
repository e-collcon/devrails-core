# web-app

Next.js 14 (App Router) dashboard for DevRails Free Tier Watch.

```bash
npm install
npm run dev          # http://localhost:3000/dashboard
npm test             # A.9 state derivation, contract guard and view model (vitest)
npm run build        # static build; every fixture state is prerendered
```

- **Data.** `/dashboard/<state>` renders engine-generated Contract v1.3 fixtures from `src/fixtures/dashboard-feed.json`. Regenerate them with `python ../spike-engine/main.py export-fixtures --out src/fixtures`. A live Firestore `onSnapshot` read plugs in at `src/lib/feed/source.ts` once auth (TASK-012) and the read helper (TASK-083) land.
- **States.** `src/lib/feed/deriveState.ts` implements Contract v1.3 A.9 (Pending, Sync Delayed, Stale, Sync Failed, …). The UI never re-derives Normal / Elevated / Risky.
- **Theme.** DS v2 tokens are in `src/styles/tokens.css`. The theme is set before first paint from `localStorage["devrails-theme"]`, falling back to the OS preference, and switched with the sun/moon toggle in the header.

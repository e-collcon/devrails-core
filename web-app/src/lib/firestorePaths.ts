// web-app/src/lib/firestorePaths.ts
// DevRails PoC | PRD-001 v1.0 | TASK-019
//
// Canonical Firestore path helpers for the dashboard feed.
//
// Canonical path: users/{uid}/projects/{projectId}/dashboard_feed/current
//
// Superseded paths — NEVER use these:
//   projects/{projectId}/metrics/current
//   users/{uid}/projects/{projectId}/metrics/current

/**
 * Returns the canonical Firestore path for the dashboard feed document.
 * Per PRD-001 v1.0 §10.5 and TASK-019.
 */
export function dashboardFeedPath(uid: string, projectId: string): string {
  return `users/${uid}/projects/${projectId}/dashboard_feed/current`;
}

# NOTE — Auth entry point origin (deferred / revisit later)

**Raised:** July 2026, during TASK-164 (Firebase Web App registration)
**Raised by:** E · **Written by:** Claudia
**Status:** Parked. Not a PRD-001 change. Revisit post-PoC.

---

## The question

Should the Google Sign-In popup fire from the landing page (`thedevrails.com`),
with successful auth then handing the user to the product app
(`app.thedevrails.com`)?

## Resolution for PRD-001

**No.** Confirmed flow stays:

1. Entry point: `thedevrails.com`
2. User clicks CTA
3. Plain link → `https://app.thedevrails.com/signin`
4. **All** authentication happens on `app.thedevrails.com`

The landing page owns the invitation. `web-app` owns the door.

## Why — the blocking technical reason

Firebase Auth persists sessions in **IndexedDB, which is strictly
same-origin.** `thedevrails.com` and `app.thedevrails.com` are different
origins.

If the popup fired on the landing page, the sequence would be:

- User signs in successfully → session written to the *landing* origin
- Browser navigates to `app.thedevrails.com`
- App boots, checks auth state, finds **nothing**
- User is bounced to `/signin` and must sign in a **second time**

Cookies can be widened to a parent domain via `Domain=.thedevrails.com`.
IndexedDB cannot. There is no configuration flag that fixes this.

## What a cross-origin handoff would actually require

Either:

- **Custom token** minted by the Firebase Admin SDK, passed to the app and
  exchanged via `signInWithCustomToken`, or
- **Admin-SDK-issued session cookies** scoped to the parent domain

Both need backend auth infrastructure that does not exist in PRD-001. The
URL-token variant also leaks a credential into browser history and referrer
headers. Neither is recommended for the PoC.

## Consistency check — this resolution matches existing signed-off artifacts

- **TASK-011 Auth Use Cases & Flows v0.1** (Lexie accepted, Kate signed off):
  all 11 in-scope flows originate at `app.thedevrails.com/signin`
- **TASK-153–162**: Lovable builds the `/signin` UI inside `web-app`
- **TASK-166 / Kate's authorized-domains spec**: `localhost`, `127.0.0.1`,
  `app.thedevrails.com` — `thedevrails.com` deliberately absent
- **Firebase Web App registration (TASK-164)**: registered against
  `devrails-core-dev`, for `devrails-core/web-app` only. The landing page has
  no Firebase registration and needs none.

No conflict. No rework required to the auth track.

## Known consequence, accepted

The landing page **cannot** read the app's session — different origins. So the
landing CTA cannot say "Go to dashboard" for already-signed-in visitors; it
always says the same thing. This is out of scope for PRD-001 and is not
considered a defect.

## Open action carried out of this discussion

E to revisit the UI generated under **TASK-153–162** and confirm it is attached
to `devrails-core/web-app` (not the landing project). Tracked separately from
this note.

## Trigger to revisit

Only if a future PRD requires seamless signed-in continuity across the
marketing and product origins — e.g. a personalized landing experience. At that
point, evaluate Admin-SDK session cookies on the parent domain. Not before.

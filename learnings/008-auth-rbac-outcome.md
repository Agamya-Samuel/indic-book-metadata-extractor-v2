# 008 — Auth/RBAC Implementation Outcome

- **Date:** 2026-11-11
- **Study Context:** Implementation of the approved design in
  `plans/005-auth-rbac.md` — email/password accounts, cookie sessions,
  role-based authorization, per-user book ownership, a user dashboard, admin
  user management, and a public metadata-only catalog. This learning records
  what was actually built, the non-obvious decisions, and the residual gaps.

## Summary

The milestone shipped end-to-end on the existing FastAPI/Next.js/Celery
stack with **no new services and no pipeline changes**; the hard parts were
the session lifecycle (rotating single-use refresh + CSRF) and making
"metadata-only for non-owners" a backend invariant rather than a UI
convention.

## Key Findings

### 1. Cookie + CSRF, not bearer tokens

The app already loads page images and job updates from plain `<img>`/`EventSource`
URLs, so an `Authorization` header was never available to those requests.
Cookie sessions (`access_token` 15 min HttpOnly + `refresh_token` 7 days +
readable `csrf_token`) keep those URLs working while still protecting
state-changing requests, which must echo `X-CSRF-Token`.

### 2. Rotating single-use refresh tokens need single-flight client handling

The refresh token is single-use; reuse is treated as theft and revokes the
session. The client therefore needs exactly one in-flight refresh promise
shared by all concurrent 401s, plus one replay of the original request.
A naive per-request refresh logs the user out under concurrency.

### 3. Session invalidation rides on `users.token_version`

Role changes, deactivation, and admin password resets must invalidate the
target's existing sessions. A `token_version` column on `users`, checked
when validating the access token, does this without a per-session lookup.

### 4. "Metadata-only for non-owners" must be enforced at the serializer

The library detail endpoint returns the same shape for everyone, so the
backend sets `can_view_full` and omits pages/OCR/jobs/LLM runs for
non-owners and anonymous visitors. The frontend then gates the review CTAs
and the resume banner on that flag. Any new field added to the detail
response needs the same treatment, otherwise it leaks by default.

### 5. The public catalog needed an explicit status whitelist

Listing only `complete` and `awaiting_review` books keeps in-progress books
private without needing a separate "visibility" column. The same predicate
is reused for the detail endpoint, so a non-owner gets a `404` (not a `403`)
for a private book — no existence leak.

### 6. Migration 012 must refuse to run on a non-empty `books` table

`books.owner_id` is non-nullable and there is no backfill path (the plan
locked "DB will be reset"). The migration therefore aborts with a clear
message instead of half-failing, and the deploy docs state that the
production DB is reset on this deploy.

### 7. SMTP off ≠ broken registration

With `SMTP_ENABLED=false` the email body (including the verification/reset
link) is logged to the backend log. That makes local development workable
without a mail server, but the docs must be explicit, otherwise "no SMTP"
reads as "sign-up is broken".

### 8. Auth fixtures had to stay SQLite-compatible

The backend test suite runs on SQLite in-memory with a JSONB→JSON patch.
The new auth/RBAC/dashboard tests follow the same rule: no Postgres-only
operators (`astext`) in auth paths, and `anon_client` / `user_client` /
`admin_client` fixtures instead of real logins per test.

### 9. The frontend mirrors two backend knobs

`PASSWORD_MIN_LENGTH` (backend default 10) and the email-verification
requirement are duplicated in the auth pages and the admin user dialogs.
They are constants in the frontend, not fetched from the API — a backend
change to the default must be mirrored in the UI.

### 10. React Query v5 passes a context argument to `mutationFn`

Any assertion on a mocked mutation call must read `mock.calls[0][0]`;
`toHaveBeenCalledWith(payload)` fails because of the extra second argument.

## Recommendation

**Go.** The design met its goals with no pipeline regressions: the OCR/LLM
pipeline is untouched, backend tests are at 272 passed / 1 skipped, and the
frontend suite is green with `tsc --noEmit` and lint clean for the
auth-owned files.

Residual gaps, all deliberate and documented in `README.md` →
Known Limitations and `docs/known-limitations.md` item 8:

- No per-user quotas (any registered user can upload/run unlimited jobs).
- Rate limiting covers the auth endpoints only.
- Email delivery depends on SMTP configuration in production.
- Email change, admin impersonation, and per-book sharing are out of scope.

## Next Steps

1. Commit the milestone in four logical commits (backend → frontend auth →
   frontend dashboard/admin → docs); see `todos/009-auth-rbac-handoff.md` §7.1.
2. Run the deploy sequence: reset DB → `make migrate` → `make create-admin` →
   configure SMTP.
3. Manual end-to-end check with a real scanned PDF: register → verify email →
   log in → upload → pipeline → dashboard → admin views (not yet exercised
   against a live stack).
4. Decide whether the `awaiting_review` books should stay in the public
   catalog (currently they do, per the locked decision).

## References

- `plans/005-auth-rbac.md` — approved design
- `todos/009-auth-rbac-handoff.md` — implementation checklist, verification
  state, handoff notes
- `docs/api-reference.md` — Authentication / Dashboard / Admin API contracts
- `backend/app/api/deps.py` — the authorization primitives
- `backend/app/services/auth_service.py` — session lifecycle

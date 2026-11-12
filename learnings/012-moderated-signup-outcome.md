# 012 — Moderated Signup, Admin-Only Library, Owner-Only Book Access

1. **Date** — 2026-11-12
2. **Study Context** — Implement `plans/007-moderated-signup-admin-library.md`,
   which closes the Pilot-phase access gaps in the shipped auth/RBAC system
   (`plans/005`, `learnings/008`): no anonymous access, approval-based
   registration, an admin-only Library spanning all users, and backend-enforced
   per-user book ownership.
3. **Summary** — Shipped as planned on the existing auth stack; the migration is
   purely additive and the full backend suite passes, so the migration + test
   suite served as the verification step in place of a standalone PoC.

## Key Findings

- **Two independent gates compose cleanly.** Email verification already lived in
  `authenticate_user`; approval is a separate `account_status` column gated by a
  new `require_approved_user` dependency applied at router level. `/auth/*` and
  `/health` stay outside it, so a `pending`/`rejected` user can hold a session,
  refresh it, and log out while stuck on the holding screen — which is what makes
  "log in to see the status" work without special-casing login.
- **Approval is orthogonal to `is_active`.** `is_active` keeps meaning "admin
  suspended" (login is refused); `account_status` means "awaiting/reviewed
  moderation" (login is allowed, app is refused). Keeping them separate avoided
  reworking the existing deactivation flows.
- **Additive migration backfills everyone to `approved`.** The `users.account_status`
  column has `server_default='approved'`, so existing rows — including the
  bootstrap admin — are grandfathered in. `register_user` sets `pending` only when
  `REGISTRATION_REQUIRES_APPROVAL` is true, so the flag flips open registration
  back on with no schema or code change.
- **Rejection revokes sessions; approval does not.** Approving a `pending` user
  leaves their existing session valid (they gain access immediately). Rejecting
  bumps `token_version` via `revoke_all_sessions`, so a rejected user is signed out
  and must log in again to reach the "not approved" screen — immediate effect
  without a separate revocation path. Verified by test.
- **Removing the public catalog collapses three code paths into one.** Deleting
  `PUBLIC_BOOK_STATUSES`, `get_visible_book_or_404`, and the `can_view_full_book(None)`
  branch left `get_owned_book_or_404` as the single owner-or-admin authority for
  book, page, metadata, detail, and thumbnail access; a non-owner URL now 404s
  uniformly instead of leaking metadata.
- **Library listing was made admin-only, not merely authenticated.** The plan's
  endpoint table said the listing/search/filters "require auth"; returning all
  books to any approved user would contradict the plan's own objective 4
  ("regular users can only reach books they own"). Implemented as `require_admin`
  on those three endpoints while book *detail* stays owner-or-admin (so owners can
  still open their own book via `/library/[bookId]`). Flagged as an interpretation
  in the plan's open items.
- **`rejection_reason` had to be added to `UserResponse`.** The frontend spec asked
  the rejected screen to show the reason, but the schema section only added
  `account_status`; surfaced `rejection_reason` on the same response so the holding
  screen can render it.

## Recommendation

Go — merge. The change is additive, backfills safely, and defaults to the safer
(moderated) posture. Open registration remains one env var away.

## Next Steps

- Doc/plan sync: `docs/known-issues.md` notes admin notification is an in-app
  badge only (no SMTP dependency) and a `pending`-count badge drives it.
- Deferred and unchanged from `plans/005`: OAuth/social login, per-user quotas,
  admin impersonation, per-book sharing, email-to-admins on signup.

## References

- Plan: `plans/007-moderated-signup-admin-library.md`
- Prior milestone: `plans/005-auth-rbac.md`, `learnings/008-auth-rbac-outcome.md`
- Migration: `backend/alembic/versions/013_user_approval.py`
- Gate: `backend/app/api/deps.py` (`require_approved_user`), `backend/app/api/router.py`
- Tests: `backend/tests/integration/test_signup_approval.py`, `test_rbac.py`, `test_api_library.py`
- Frontend: `frontend/src/components/auth/route-guard.tsx`, `frontend/src/app/pending-approval/page.tsx`

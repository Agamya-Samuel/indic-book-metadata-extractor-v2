# 013 — Production Hardening: End-to-End Reliability

Status: in progress (started 2026-11-14)

## Objective

Harden the deployed application end to end: fix workflow-breaking defects, make
cancellation and retries trustworthy, enforce data isolation and idempotency,
repair the mail path, and verify the full journey on the production host.

## Environment

- Testing happens on the deployed `oki` host only (`https://indic-book-metadata-extractor.agamya.us.kg/`),
  using the QA accounts in `reference/oki-qa-accounts` and throwaway books that are deleted afterwards.
- Deploys happen through Dokploy on push to `main`. Each fix is its own commit; pushes are
  confirmed with the user before they happen.
- Mail uses Resend over raw SMTP (`smtp.resend.com`), keyed by `RESEND_API_KEY` / `RESEND_FROM_EMAIL`
  in the gitignored `.env`; the same values go into the Dokploy environment.

## Decisions (2026-11-14)

| # | Decision |
|---|----------|
| 1 | Prod-only verification; create/delete test data freely (pre-launch). |
| 2 | One book in flight globally: Redis pipeline lock + worker concurrency 1. |
| 3 | Re-running extraction is allowed from `awaiting_review` and `complete`; it replaces all standard fields (null clears) and keeps `custom_fields`. |
| 4 | Partial OCR advances the book to `ocr_complete`; failed pages carry a per-page error flag. |
| 5 | Duplicate submissions are idempotent: 409 with the existing job id. |
| 6 | Terminal-job notifications always go to the book owner. |
| 7 | Mail via Resend SMTP; no SDK dependency. |
| 8 | One commit per fix; confirm before each push. |

## Confirmed defects

P0:

1. `admin_service._revoke_celery_task` is called but undefined; `POST /books/{id}/pages`
   500s whenever a job is active (`backend/app/api/books.py:262`).
2. Cancelling OCR/LLM/preprocessing only changes the DB row: no Celery revoke, and the
   tasks neither check `CANCELLED` nor avoid resurrecting a cancelled job. Prod job history
   shows `Cannot complete '<stage>' from status 'cancelled'/'completed'`.
3. Re-run extraction is rejected from `awaiting_review`, the normal post-extraction state
   (`backend/app/api/extraction.py:46`, `backend/app/services/admin_service.py:388`).

P1:

4. OCR-processing page is blank for a cancelled job and spins forever when no OCR job exists.
5. Logout after access-token expiry leaves the refresh token valid.
6. Upload writes the whole body before enforcing the 200 MB limit.
7. Page selection has no idempotency; concurrent submits can orphan pages or collide on the
   stage-attempt unique constraint.
8. Bulk preprocessing with no pages leaves the job `RUNNING`; preprocessing has no completion
   notification.
9. LLM re-runs merge non-null values and never clear stale fields.
10. Metadata PUT accepts arbitrary keys and unbounded payloads; custom-field dirty state never clears;
    select-pages failures are silent.
11. Partial OCR reports success while the book stays at `pages_selected`.
12. CORS defaults to `*`, JWT secret length is unchecked, uploads are not streamed-capped.

## Work increments

- [ ] P0: revoke helper + cancellation-aware tasks + supersession guards
- [ ] P0: re-run extraction statuses + replace semantics
- [ ] P0: idempotent submissions (409 + existing job id)
- [ ] P1: partial OCR advance + per-page failure flag (migration)
- [ ] P1: owner notifications
- [ ] P1: single-book lock, concurrency 1, reaper heartbeat
- [ ] P1: frontend reliability fixes
- [ ] P1: Resend SMTP path + real send verification
- [ ] P1: security defaults (CORS, JWT length, upload cap, metadata validation)
- [ ] Production browser + API E2E matrix
- [ ] `learnings/023-*` report with remaining issues and owners

## Test matrix

1. Auth/RBAC: anonymous, pending, rejected, approved user, admin; IDOR on every book/page/job route.
2. Upload: valid, corrupt, oversized, wrong type, duplicate, concurrent.
3. Page selection: normal, all/none, out of range, cancel mid-render, duplicate submit.
4. Preprocessing: per page, all pages, cancel, preview, re-run.
5. OCR: success, partial failure, all failure, cancel, worker restart, re-run.
6. OCR review: correction persistence, empty text, concurrent re-run, unsaved guard.
7. LLM: success, Ollama down, cancel, duplicate submit, re-run from awaiting_review, replace semantics.
8. Metadata review: save, complete, empty fields, running-job 409, stale evidence.
9. Notifications: in-app rows, dedupe on redelivery, email preference, Resend delivery.
10. Admin: user approval, role changes, jobs queue/cancel, book reset/delete while running, bulk export/import.
11. Browser sweep of every route on desktop and one narrow viewport, with console/network checks.

## Exit criteria

Every item above PASSes on the deployed host, or has a repro, severity, and an owner.
`docs/known-issues.md` is updated with anything intentionally left.
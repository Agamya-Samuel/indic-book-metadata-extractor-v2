# 023 — Production Hardening: End-to-End Outcome

Date: 2026-11-14
Scope: full application (backend API + Celery pipeline + Next.js UI), deployed host
Deployed commit tested: `96cf6e5` at `https://indic-book-metadata-extractor.agamya.us.kg/`
Environment: production `oki` (4 vCPU / 16 GB, no swap), pre-launch QA data

## Verdict

The workflow is materially hardened: the P0 defects that broke cancellation,
re-runs, duplicate submissions and the deployed backend are fixed and verified
against production. The application is **functionally ready**; **public launch
is still blocked by operator configuration**, chiefly the production SMTP
environment (below) and the pre-existing origin/backup/alerting gaps.

## What was exercised

### API (production, throwaway data)

`backend/scripts/e2e_prod.py` runs the whole journey and deletes its data:

- Anonymous: public health only; dashboard, models and admin all 401.
- User: login, `/me`, dashboard summary/books/jobs, notifications, admin denied (403).
- Admin: login, stats, users, books, global jobs.
- IDOR: another owner's book/pages/jobs return 404; a user cannot open admin routes.
- Upload (119-page Hindi PDF), page selection of two pages, duplicate submit → 409 + `X-Existing-Job-Id`.
- Preprocessing bulk job; OCR start → cancel → stayed cancelled → re-run → completed.
- OCR text read, correction written and read back; no page-level failures.
- LLM extraction (phi4-mini) → completed, metadata + evidence present, book `awaiting_review`.
- Re-run extraction from `awaiting_review` → 201 (previously a dead end).
- Metadata validation: unknown field → 422, oversized value → 422; save + custom field persisted.
- `review/complete` → book `complete`.
- Notifications listed/marked read; admin create + delete user; admin job queue; book delete + 404.

Result: **55/55 checks pass** (53 on the first run; the two failures below were
fixed and re-verified in production).

Additional boundary checks: invalid upload type 400, mutation without CSRF 403,
CSV and QuickStatements exports 200 with correct content types, forgot-password
for an unknown address 202 (non-enumerating), foreign book jobs 404, user admin
API 403.

### Browser (in-app browser, deployed host)

Login (admin and user), dashboard summary and tables, upload form, book detail
with live job panel and processing history, preprocessing controls, OCR review
assets, LLM configuration (Run again, 8 calls/49 fields, prior-run notice),
metadata review (49 field widgets, evidence pane, complete action), notifications
page, admin operations/users/books/jobs/bulk pages, user-role redirect from
`/admin` → `/dashboard`, foreign book → "Book not found", pending user → holding
screen and blocked from `/dashboard`, admin approval → dashboard access.
No console errors; all XHRs on the book detail returned 200.

### Automated suites

- Backend: **400 passed, 1 skipped** (`pytest`), ruff clean on all touched files.
- Frontend: **201 passed** (`vitest`), TypeScript clean, `next build` succeeds.

## Defects found and fixed

| Symptom | Root cause | Fix |
|---|---|---|
| `POST /books/{id}/pages` 500 while a job is active | `admin_service._revoke_celery_task` was called but never defined | `c7820aa` |
| Cancel left OCR/LLM jobs running; they later re-completed a cancelled stage (`Cannot complete … from status 'cancelled'/'completed'` in prod jobs) | No Celery revoke, and tasks never checked `CANCELLED`; an old worker could finalise a newer run's stage | `0d51bac` (+ cancellation/supersession guards) |
| Re-run extraction from `awaiting_review` returned 400 (dead end from dashboard and LLM page) | Status allow-list excluded the normal post-extraction state | `f676ad2`; re-run now replaces standard fields (null clears) and keeps `custom_fields` |
| Duplicate page-selection/preprocessing/OCR spawned racing jobs | No idempotency | `9217d52` (409 + `X-Existing-Job-Id`); duplicate LLM ordering fixed in `f8242c5` |
| Partial OCR reported success while the book stayed at `pages_selected` | Job completed but the stage was failed | `a331dfa` (advance + `pages.ocr_error`) |
| Admin-triggered job notifications went to the admin | Recipient was the requester | `9b60eb8` (book owner) |
| Two books could process at once; a healthy 121-minute run was reaped | Worker concurrency 8; reaper used `started_at` | `428e7bf` (global Redis lock, concurrency 1, `last_progress_at` heartbeat) |
| Logout after the 15-minute access token expired left the session alive | Logout required a valid access token | `a0368ef` |
| OCR page blank on cancel / endless spinner with no job; silent page-selection errors; custom fields never cleaned | Frontend state gaps | `3b5972a` |
| Unknown metadata field returned 500 | Validation handler put the `ValueError` object into JSON | `f8242c5` (422, safe encoding) |
| Stepper highlighted OCR Review while the LLM ran after an OCR re-run | Attempt numbers compared across stages | `7a56b76` (stage `created_at`) |
| Deployed backend crash-looped (`FieldEvidenceResponse` ImportError) | `origin/main` had the import without the schema class | `670ba51` (already deployed before testing) |

Hardening also added: upload Content-Length pre-check + copy cap, metadata
payload validation, bulk CSV limits/UTF-8 check, password-change reset-token
invalidation, production JWT-secret length check, explicit CORS fallback,
partial-OCR page flags, and `plans/013-production-hardening.md`.

## Verified in production

- Cancelled OCR and LLM jobs stay cancelled; the book is released to a runnable
  status; no stage resurrection after 25 seconds.
- Duplicate submissions return 409 with the existing job id.
- Re-run extraction from `awaiting_review` starts and supersedes the review.
- Replace semantics: re-run clears standard fields it cannot find, keeps custom
  fields (unit/integration tested; the E2E run produced a full metadata set).
- Metadata validation returns 422 with a readable message.
- Stepper shows LLM Extraction as current during a clean re-run, with the prior
  metadata review marked stale.
- Worker runs `--concurrency=1`; schema is at migrations `016`.
- Resend raw SMTP transport accepted a live message when configured with the
  `.env` key (sent from the backend interpreter on this machine).

## Remaining issues

| Issue | Impact | Owner / next step |
|---|---|---|
| **Production SMTP still points at the retired `mx.msgwing.com`** | Verification, reset and notification emails fail (in-app notifications work). Registration still returns 201 and tells the user to check email. | Operator: set `SMTP_HOST=smtp.resend.com`, `SMTP_PORT=587`, `SMTP_USERNAME=resend`, `SMTP_PASSWORD=<RESEND_API_KEY>`, `SMTP_FROM=<RESEND_FROM_EMAIL>` in Dokploy and redeploy. Values are in the gitignored `.env`. |
| CI is red repo-wide | `ruff check .` reports 60 issues and `ruff format --check` would reformat 131 files, so the lint gate cannot protect merges. | Next cleanup sprint; not caused by this work (touched files are clean). |
| `make check-compose-drift` fails | Staging lacks `FRONTEND_URL`/SMTP envs and the Ollama tuning present in production. | Operator/next infra change; production itself is unaffected. |
| Single-book lock and reaper heartbeat | Verified by config and unit tests; not stress-tested with two real books. | Load test on a GCP node (same hardware) when offered. |
| Partial-OCR per-page flag | Logic tested; no real page failure was induced in production. | Covered automatically on the next OCR incident. |
| Origin reachable without Cloudflare; no offsite backups; no alerting | Pre-existing operator items documented in `docs/known-issues.md`. | Operator. |
| Page images via `<img>` can 401 after the access token expires | Pre-existing; reload recovers. | Future: signed thumbnail URLs or blob fetch. |
| No per-user quotas; rate limits are per-IP only | Pre-existing. | Product decision. |

## Reproduction

From the repository root, with the QA accounts in place:

```bash
backend/.venv/bin/python backend/scripts/e2e_prod.py
```

It creates one book and one user, then deletes both. `E2E_BASE_URL`,
`E2E_PDF`, `E2E_ACCOUNTS` and `E2E_REPORT` override the defaults.

## Note on the shared tree

`origin/main` also carries pagination and stepper-display commits from a
parallel session (`881c6b5` … `96cf6e5`). They were exercised by this pass
(admin/dashboard/book pages, no console errors) but are not part of this
hardening work.
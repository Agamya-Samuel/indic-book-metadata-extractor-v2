# 010 — In-app notifications and email alerts

- **Date:** 2026-11-13
- **Status:** Decisions agreed; implementation starting.
- **Motivation:** long jobs finish in the background and account decisions happen
  while the user is elsewhere. Today the only signal is a badge on the admin nav
  (`/api/admin/users/pending-count`) and the dashboard/job screens. Add one
  notification record per event, shown in-app and mirrored to email when the
  recipient allows it.

## Objective

Deliver every in-scope event through two channels:

1. **In-app** — always on, per-recipient, with read state.
2. **Email** — same events, controlled by a per-account Boolean preference
   (`true` = send). Email never gates the in-app record.

In scope: long-running job completion, plus account approval and new-registration
(admin) events. Out of scope: account rejection, digests, push, SSE.

## Agreed decisions (2026-11-13)

| # | Decision |
|---|---|
| 1 | One self-service Boolean per account, admins included; no global switch |
| 2 | Notify on **success, failure and cancel** |
| 3 | Read/unread per notification + unread count + mark-all-read; history kept |
| 4 | New-registration alert is one row **per active admin** (per-admin read state) |
| 5 | Navbar bell + dropdown (latest 8) **and** a `/notifications` page with pagination |
| 6 | Email sent from FastAPI `BackgroundTasks` after commit; failures logged, never block or roll back |
| 7 | Keep everything (no retention job) |
| 8 | Poll unread count (~30s) with TanStack Query; no SSE changes |
| 9 | Notifications deep-link: jobs → book stage, approval → `/dashboard`, signup → `/admin/users` pending filter |

## Data model

New table `notifications` (migration `014_notifications.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | `UUIDMixin` |
| `user_id` | FK `users.id` ON DELETE CASCADE, indexed | recipient |
| `type` | String(40) | `job_completed`, `job_failed`, `job_cancelled`, `account_approved`, `pending_registration` |
| `title` | String(200) | short line for the bell |
| `body` | String(1000) | detail |
| `link_url` | String(500) null | absolute app path |
| `book_id` | FK `books.id` ON DELETE SET NULL, null | job events |
| `read_at` | timestamptz null | null = unread |
| `emailed_at` | timestamptz null | delivery audit; null also means preference off / send failed |
| `event_key` | String(200) | idempotency key, unique per user |
| `created_at` | timestamptz | server default |

`UniqueConstraint(user_id, event_key)` — a Celery redelivery
(`acks_late` + `task_reject_on_worker_lost`) or a retried request must not
create a second row. Keys:

- `job:{job_id}:{status}` — one per job terminal state.
- `account-approved:{user_id}` — once per account.
- `pending-registration:{user_id}` — once per admin per new account.

`users` gains `email_notifications_enabled` Boolean, default `true`, not null.

## Event matrix

| Event | Recipient | Type | Link | Email subject |
|---|---|---|---|---|
| Page extraction / OCR / LLM completes | `job.requested_by_id` (fallback: book owner) | `job_completed` | `/books/{id}/{stage}` | "OCR finished for «title»" |
| Job fails (incl. `task_failure` net and partial-to-zero) | same | `job_failed` | `/books/{id}/{stage}` | "OCR failed for «title»" |
| Job cancelled via `cancel_job` | same | `job_cancelled` | `/books/{id}/{stage}` | "OCR cancelled for «title»" |
| Account approved | approved user | `account_approved` | `/dashboard` | "Your account is approved" |
| New registration pending | every active admin | `pending_registration` | `/admin/users?status=pending` | "New registration awaiting approval" |

Per-event email body mirrors the in-app body plus the deep link; English, same
plain-text style as the verification mail.

## Delivery design

- `app/services/notification_service.py` owns creation:
  - `create_notifications(db, ...)` → rows, idempotent on `event_key`.
  - `notify_job_terminal(db, job, status, error)` resolves the recipient and
    stage link, inserts, and returns the rows (commit left to the caller so the
    record lands atomically with the job state).
  - `notify_admins_registration(db, user)` fans out to active admins.
  - `notify_account_approved(db, user)`.
- `deliver_notification_emails(notification_ids)` opens its own session, joins
  users, skips anyone with `email_notifications_enabled = false`, sends through
  `email_service.send_email`, stamps `emailed_at` on success. Any exception is
  logged and swallowed.
- **Request paths** (register, approve, cancel): create the row, commit, then
  `background_tasks.add_task(deliver_notification_emails, ids)` — a dead or
  slow SMTP host must not delay or fail the request.
- **Worker paths** (ocr / page / llm tasks, `task_failure`): create the row in
  the task's session right after its commit, then `await
  deliver_notification_emails(ids)` inside the existing `run_async` block.
  Email failures are logged; the job result is already committed.

## API

New router `app/api/notifications.py`, mounted with
`Depends(require_approved_user)`:

| Method | Path | Returns |
|---|---|---|
| GET | `/api/notifications?page&page_size&unread_only` | paginated list + `total`, `unread_count` |
| GET | `/api/notifications/unread-count` | `{count}` |
| POST | `/api/notifications/{id}/read` | `{id, read_at}` |
| POST | `/api/notifications/read-all` | `{updated}` |
| GET | `/api/notifications/preferences` | `{email_enabled}` |
| PATCH | `/api/notifications/preferences` | `{email_enabled}` |

Rows are scoped to `current_user.id` in every query; a notification id that
belongs to someone else returns 404.

## Frontend

- `lib/api.ts`: types + the six calls above.
- Navbar (`app-navbar.tsx`): bell button with unread badge, dropdown listing the
  latest 8, "Mark all as read", "View all". Unread count query polls every 30 s
  (`refetchInterval`) and is invalidated on read actions.
- `/notifications` page: paginated list (unread styled with the accent dot),
  click marks read then follows `link_url`, mark-all-read, and the email
  preference switch. Uses the shared `PageContainer`, `Card`, `Pagination`,
  `EmptyState`, `Banner` and `Chip` primitives.
- Design kit gains the notification row and the preference switch.

## Testing

- Backend unit: idempotency (same `event_key` twice → one row), admin fan-out
  includes only active admins, recipient fallback, preference off → no email,
  SMTP failure swallowed, cancel/success/failure mapping.
- Backend API: pagination, unread count, read/read-all, cross-user access 404,
  preference round-trip.
- Frontend: bell badge renders count and opens the dropdown; notification click
  marks read and navigates; preference switch PATCHes; empty state.
- Deployed check on OKI: register a throwaway account → admins see the bell
  entry; approve it → the user sees the approval entry; re-run a job → the
  owner gets a completion entry; toggle email off and confirm no send is
  attempted (backend log).

## Risks

- **Duplicate rows on Celery redelivery.** Mitigated by the unique constraint;
  creation must tolerate `IntegrityError` by returning the existing row.
- **Slow/broken SMTP.** Production SMTP is currently unresolved; delivery is
  off the request path and time-boxed by `smtp_timeout`, so requests stay fast.
- **Notification noise.** Self-cancels also notify, per decision 2; if it
  proves noisy, filtering by actor is a one-line change in `cancel_job`.
- **Stale links.** A deleted book sets `book_id` to null; the link 404s. Title
  and body still identify the event, and the notifications page shows them.

## Success criteria

1. All five event types create exactly one in-app row per recipient, even when
   the producing task is retried.
2. Email is attempted only when `email_notifications_enabled = true`, and an
   SMTP failure never fails the request or the job.
3. The bell badge, dropdown, `/notifications` page and preference switch work
   on the deployed host for both a regular user and an admin.
# 013 — Notifications implementation checklist

Plan: [`plans/010-notifications.md`](../plans/010-notifications.md)

## Backend

- [ ] Model `Notification` + `User.email_notifications_enabled`; migration 014
- [ ] `notification_service`: idempotent create, job-terminal mapping, admin fan-out, approval row
- [ ] `deliver_notification_emails`: preference gate, audit stamp, swallow failures
- [ ] Hook worker paths: `page_tasks._finalize`/`_fail`, `ocr_tasks._finalize`/`_mark_job_failed`, `llm_tasks` success + failure blocks, `celery_app` `task_failure`
- [ ] Hook request paths: `cancel_job` + its routes, `register_user`, `approve_user`
- [ ] Router `/api/notifications/*` + preferences
- [ ] Backend tests (service + API)

## Frontend

- [ ] API client types and calls
- [ ] Navbar bell + dropdown + 30 s unread polling
- [ ] `/notifications` page (list, read, read-all, pagination, preference switch)
- [ ] Design kit entries
- [ ] Frontend tests

## Verification

- [ ] `ruff`/backend tests, `tsc`, `eslint`, `vitest`, `next build`
- [ ] Deploy, then verify on OKI: signup → admin alert; approval → user alert; job terminal → owner alert; email preference off
- [ ] Update `docs/known-issues.md` (drop the "admin notification is in-app only via badge" entry if the bell supersedes it)
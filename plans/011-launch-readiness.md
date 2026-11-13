# 011 — Launch readiness

- **Date:** 2026-11-14
- **Status:** Code workstreams done, deployed and verified on the host. Four
  operator actions remain: close origin ingress, edge WAF/rate rules, offsite
  backups, alerting.
- **Context:** The core product is complete and the notification feature shipped.
  Production is deployed behind Cloudflare on a 4 vCPU / 15 GiB host with no swap.
  This phase hardens what a public launch needs and records the audit evidence.

## Objective

Make "deployed" mean "works and can be operated": a public surface that fails
safely, data that can be recovered, jobs that cannot wedge a book forever, and a
runbook an operator can follow at 2 a.m.

## Audit findings (measured on the deployed host, 2026-11-14)

| # | Finding | Severity |
|---|---|---|
| 1 | Rate limiting keys on `request.client.host`, which behind Cloudflare is the **edge IP**, not the user — every visitor shares one bucket, and 10 auth requests/min can lock out all logins | High |
| 2 | The origin is **directly reachable** on `187.127.174.246:443` (HTTP 200), bypassing Cloudflare; WAF/rate rules and proxy headers can be spoofed | High |
| 3 | **No security headers** (HSTS, frame-ancestors, nosniff, Referrer-Policy) and `x-powered-by: Next.js` is exposed | Medium |
| 4 | **No public health endpoint** — `/health` is not routed, `/api/health` 404s, so an uptime monitor has nothing to poll | Medium |
| 5 | Backups restore correctly (verified: 3 users / 2 books / 20 jobs / 10 pages) and keep the newest 7 dumps, but live on the **same host and disk** with no offsite copy | High |
| 6 | **Stale jobs are not reaped**: a worker restart mid-extraction left the job `running 0%` and the book `llm_running`; the task was not redelivered. Manual cancel recovers it (verified) | High |
| 7 | Ollama's **own 6 GB memory cap killed `llama-server`** twice on Nov 13 (measured 6.15 GB RSS), which is what produces "model unreachable" runs; the host has no swap | Medium |
| 8 | No APM or alerting: `NEW_RELIC_ENABLED=false`; logs rotate at 3×10 MB with no shipping | Medium |

Already good: `DEBUG=false`, `Secure` cookies, CORS pinned to the public origin,
server-side 200 MB upload cap, Redis-backed rate limiting exists, API docs and
OpenAPI are not publicly exposed, disk at 21%, all containers healthy.

## Workstreams

### W1 — Public surface (code)
- Resolve the client IP from `CF-Connecting-IP`, then the left-most
  `X-Forwarded-For`, then `request.client.host`, and key the limiter on that.
  Unit-test the precedence.
- Add security headers to both apps: HSTS, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
  Disable `x-powered-by`.
- Add a dependency-free `GET /api/health` liveness endpoint (200 `{"status":"ok"}`)
  so an external monitor has a target; keep the detailed dependency check at
  `/health` internal.
- **Ops only (needs the Cloudflare/Dokploy account):** restrict origin ingress to
  Cloudflare ranges or move to Cloudflare Tunnel, and add edge WAF/rate rules.

### W2 — Data safety
- Prune old dumps in the backup script (keep `BACKUP_KEEP_DAYS`, default 14) and
  log a loud error when a backup fails, so a silent failure is visible in logs.
- Document the offsite-copy gap and the exact restore procedure; offsite needs a
  destination + credentials from the operator.

### W3 — Resilience
- Stale-job reaper in the backend lifespan: every 5 minutes, fail a `running`
  job with no completion after a 90-minute threshold (well beyond the 10–20-minute
  norm), release the book status the same way `_mark_job_failed` does, and
  notify the requester. Unit-test the threshold and the release.
- Document the observed redelivery behaviour (a restart may resume the task; it
  must not be relied on) and the manual cancel path.
- Raise the Ollama memory cap to fit the measured 6.15 GB residency, or document
  why the cap stays; verify with a full extraction.

### W4 — Observability
- Document enabling New Relic and the minimum alert set (site down, worker down,
  job stuck, disk > 85%).
- External uptime check against the new liveness endpoint.

### W5 — Rollback and runbook
- Verify and document rollback (git revert + push, or redeploy a previous
  deployment) and confirm deployment logs are retained.
- `docs/runbook.md`: start/stop, deploy, rollback, restore a backup, clear a
  stuck job, approve a user, rotate credentials, read logs, incident checklist.

## Verification

- Backend + frontend suites, `tsc`, `eslint`, builds.
- On the deployed host: headers present on HTML and API; rate limit keyed per
  client IP (two different `CF-Connecting-IP` values get separate budgets);
  `/api/health` returns 200 through Cloudflare.
- Deliberately wedge a job, wait for (or force) the reaper, confirm the book is
  released and the owner is notified.
- Backup prune keeps the expected count; restore drill repeated after the change.

## Success criteria

1. No user-visible path can leave a book stuck in a running state for more than
   the reaper interval.
2. A fresh restore from the latest dump reproduces the production row counts,
   and the procedure is written down.
3. The public origin sets the security headers, exposes a liveness endpoint, and
   rate-limits per real client IP.
4. An operator can execute deploy, rollback and restore from `docs/runbook.md`
   without reading source.

## Out of scope

- Cloudflare account configuration (WAF, origin allowlist) — needs the operator's
  account; documented as required actions.
- SMTP delivery (deferred by decision).
- OCR quality (owned by the OCR-engine workstream).
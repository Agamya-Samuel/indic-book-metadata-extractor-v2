# 014 — Launch readiness checklist

Plan: [`plans/011-launch-readiness.md`](../plans/011-launch-readiness.md)

## W1 — Public surface

- [x] Client IP precedence (`CF-Connecting-IP` → last XFF hop → socket) + tests
- [x] Security headers on Next routes and API responses; `x-powered-by` off
- [x] `GET /api/health` liveness (200, no dependency detail)
- [x] Verified on the deployed host: headers on HTML + API, liveness 200
- [x] Per-client rate limiting proven live (10 auth requests → 429 for one IP;
      a second IP still allowed)
- [x] Operator action documented: close origin ingress / Cloudflare Tunnel

## W2 — Data safety

- [x] Backup retention configurable (`BACKUP_KEEP`) + loud failure marker
- [x] Manual backup and restore drill repeated after the change (4 users /
      3 books / 14 notifications restored, scratch DB dropped)
- [x] Offsite copy documented as the remaining operator action

## W3 — Resilience

- [x] Stale-job reaper (90 min) with book release + notification; tests
- [x] Verified live: a fabricated 121-minute job was failed, the book released
      to `ocr_complete`, the owner notified, and the sweep logged
- [x] Ollama cap raised to 7 GB (measured 6.15 GB residency vs old 6 GB cap)
- [x] Full extraction under the new cap completed with no OOM kill

## W4 — Observability

- [x] Minimum alert set + New Relic state documented in the runbook
- [x] External uptime target documented (`/api/health`)

## W5 — Rollback and runbook

- [x] Deployment history confirmed (one log per deploy under
      `/etc/dokploy/logs/<app>/`)
- [x] `docs/runbook.md` written and exercised: deploy, rollback, restart
      semantics, restore, stuck jobs, admin bootstrap, logs, email, incidents

## Verification

- [x] Backend suite (342 passed, 1 skipped), frontend suite, `tsc`, `eslint`,
      builds
- [x] Deployed and re-checked on OKI

## Remaining operator actions (need the Cloudflare account)

- [ ] Restrict origin ingress to Cloudflare ranges (or Cloudflare Tunnel)
- [ ] Edge WAF + rate rule for `/api/auth/*`
- [ ] Offsite backup destination + credentials
- [ ] Uptime/alerting monitor against `/api/health`
## Public-release blockers (2026-11-15)

Completed since the checklist above:

- [x] Resend raw SMTP configured in Dokploy; real signup verification and
      password-reset emails delivered and completed end to end
- [x] Signed page/thumbnail URLs (six-hour, page/book-scoped); verified in prod
- [x] CI green: ruff check/format, pytest on Python 3.11, fresh-DB migrations,
      frontend lint/tests/build; `make check-compose-drift` passes
- [x] Per-user quotas removed by decision (approved, verified users unlimited)
- [x] Telugu OCR integration plan recorded (`plans/017-...`), blocked on the
      model artifact/egress

Still open before public:

- [ ] Close origin ingress to Cloudflare ranges or move to a Tunnel
- [ ] Cloudflare edge WAF + `/api/auth/*` rate rule
- [ ] Offsite backup destination + credentials and a restore drill from it
- [ ] Alerting: site, worker, stuck job, disk >85%, backup age >36 h
- [ ] Launch hygiene (owner approval needed): remove/rotate `qa-admin`,
      `qa-user`, `qa-signup` and the pending `notif-signup-1113`; decide the
      3 sample books; rotate `reference/oki-qa-accounts`; confirm the first
      admin's password
- [ ] Copy accuracy: landing page says "Qwen2.5 7B" but production runs
      phi4-mini; confirm pilot-phase/approval signup copy

Expectation-setting (not blockers): Telugu CER ≈ 0.40 (Hindi ≈ 0.07); CPU-only
~10–20 min/book with a global single-book queue; per-IP rate limits, no quotas.

# 014 — Launch readiness checklist

Plan: [`plans/011-launch-readiness.md`](../plans/011-launch-readiness.md)

## W1 — Public surface

- [ ] Client IP precedence (`CF-Connecting-IP` → left-most XFF → socket) + tests
- [ ] Security headers on Next routes and API responses; `x-powered-by` off
- [ ] `GET /api/health` liveness (200, no dependency detail)
- [ ] Verify headers and per-IP limits on the deployed host
- [ ] Hand the operator the origin-ingress action (Cloudflare ranges / Tunnel)

## W2 — Data safety

- [ ] Backup retention (`BACKUP_KEEP_DAYS`) + loud failure logging
- [ ] Repeat restore drill after the change
- [ ] Document offsite copy as an operator action

## W3 — Resilience

- [ ] Stale-job reaper (90 min) with book release + notification; tests
- [ ] Wedge a job on the host, confirm the reaper releases it
- [ ] Ollama memory cap vs measured residency; verify one full extraction

## W4 — Observability

- [ ] Document enabling New Relic and the minimum alert set
- [ ] Recommend an external uptime check against `/api/health`

## W5 — Rollback and runbook

- [ ] Confirm deployment history / rollback path
- [ ] Write `docs/runbook.md`

## Verification

- [ ] Backend + frontend suites, `tsc`, `eslint`, builds
- [ ] Deploy and re-run the checks above on OKI
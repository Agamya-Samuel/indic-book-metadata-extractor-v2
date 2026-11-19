# Monitoring and alerting — options, decision, and pending actions

- **Date:** 2026-11-14
- **Status:** Done (2026-11-19). Better Stack account created (team "OKI Team");
  5 monitors + 2 heartbeats created via Uptime API v2, all green against
  production (API health, homepage, Wikibase API, QuickStatements, Ollama
  health; daily-backup + host-watchdog heartbeats). `host-watchdog` installed on
  `oki` (systemd timer, `/etc/betterstack-watchdog.env` with the ping URL —
  600 perms, root-only) and verified by a real drill: stopped worker →
  heartbeat `down` → `up` after restart. `daily-backup` verified live: real
  backup run → "Backup heartbeat pinged" → heartbeat `up` (alpine has no curl;
  script falls back to busybox wget). Remaining: confirm the alert email
  address in the Better Stack dashboard (Settings → Notifications — the API
  cannot read or set it).
- **Related:** [`plans/011-launch-readiness.md`](../plans/011-launch-readiness.md),
  [`todos/014-launch-readiness.md`](../todos/014-launch-readiness.md),
  [`docs/runbook.md`](../docs/operations/runbook.md)

## Context that shapes the decision

1. **The app origin is `https://openbookmap.oki-india.org`.** The origin IP
   remains reachable directly until the network policy is tightened.
2. **The origin IP is deliberately left open** (`https://<origin-ip>/`
   answers directly) until the network policy is tightened. Accepted for now.
   Consequences while it holds: Cloudflare-based rules are throwaway, and the
   header-derived client IP in the rate limiter is spoofable by a direct caller.
3. Therefore the only brute-force control that works today is **app-level**.
   The existing limiter keys on `CF-Connecting-IP`, else the last
   `X-Forwarded-For` hop, else the socket peer (deployed 2026-11-14).

## Monitoring: hosted, because host death is the case to catch

A monitor on `oki` cannot report that `oki` is down, so the provider must be
off-infrastructure.

**Chosen: Better Stack (free)** — the only free tier with both URL checks and
push heartbeats in one account.

Free plan: 10 monitors + 10 heartbeats, 3-minute checks, email + Slack alerts,
one status page. Alerts are sent by Better Stack itself, so they are independent
of the app's SMTP.

Verified heartbeat mechanics (from the provider docs):

- ping `https://uptime.betterstack.com/api/v1/heartbeat/<token>`
- append `/fail` to report a failure, or `/<exit-code>` with the output as body
- each heartbeat has `period` (min 30 s) and `grace`; status is
  `pending|up|down`
- a heartbeat stays `pending` until the first ping

### Items (all created 2026-11-19 via `infra/betterstack-bootstrap.sh`)

| Type | Target | Settings | Catches |
|---|---|---|---|
| HTTP keyword | `/api/health` | expect `"status":"ok"`, 3 min | site/host down, app hung |
| HTTP | `/` | expect 200 | full CF → Traefik → app path |
| HTTP keyword | `obm-wikibase.oki-india.org/w/api.php?...meta=siteinfo` | expect `"batchcomplete"`, 3 min | Wikibase/export stack down |
| HTTP | `obm-quickstatements.oki-india.org/` | expect 200, 3 min | QuickStatements down |
| HTTP keyword | `/api/health` ("Ollama (health)" monitor) | expect `"ok"`, 3 min | separate alert routing for the API tier |
| Heartbeat | `daily-backup` | period 86400 s, grace 43200 s (36 h total) | backup missing **or failing** (only a successful run pings) |
| Heartbeat | `host-watchdog` | period 600 s, grace 300 s; pings `/fail` with a one-line reason | worker down, job stuck > 90 min, disk > 85 % |

Free tier is 10 monitors + heartbeats combined; this uses 5 monitors + 2 heartbeats (7/10).
The `/login` monitor was removed (2026-11-19) — `/` already exercises the frontend, and free
slots do not roll over.

Detection latency ≈ check interval + grace; SMS/phone escalation is paid.

### Alternatives considered

| Bundle | Free capacity | Channels | Caveats |
|---|---|---|---|
| UptimeRobot + Healthchecks.io | 50 monitors + 20 heartbeats | Email/Discord/Pushover; email/webhooks | Both allow commercial use; no SSL-expiry on UR free |
| HetrixTools + Healthchecks.io | 15 uptime + 15 server agents, 1-min checks | Email, Telegram, Slack, Discord, webhooks | Log in every 90 days; one email recipient; no native heartbeats |
| Uptime Kuma (self-hosted) | unlimited | 90+ | Cannot report its own host being down — rejected for that reason |
| Gatus (self-hosted, YAML) | unlimited | Telegram/Slack/webhook | Same host-death blind spot; rejected |
| Upptime (GitHub Actions) | free | GitHub issues | Ties monitoring to GitHub; 5-min floor |

## Operator follow-ups (Better Stack)

1. Confirm the alert email in the dashboard (Settings → Notifications); the API
   cannot read or set it.
2. Free-tier ceiling: add-ons are 50 extra monitors $21/mo annual, 10 extra
   heartbeats $17/mo annual; phone/SMS needs the $29/mo responder license.

## Deferred with the domain change (Cloudflare account)

- Close origin ingress (allowlist Cloudflare ranges, or Cloudflare Tunnel).
- Edge WAF managed ruleset + a rate rule on `/api/auth/*`.
- Options if done as code: API token + Terraform/script, so rules are
  reproducible when the domain moves.
- Update the monitor URLs (app origin, Wikibase, QuickStatements) to the final
  domain.

## Also still outstanding

- **Offsite backups.** Dumps are restorable (drill verified) and pruned to the
  newest 7, but share the host and disk with the database. Needs a destination
  and credentials.
- **App-level brute-force hardening (A1)** — a global auth budget that no header
  can dodge, plus per-account failure lockout. Proposed, not yet approved.
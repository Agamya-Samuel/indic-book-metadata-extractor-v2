# Monitoring and alerting — options, decision, and pending actions

- **Date:** 2026-11-14
- **Status:** Provider chosen (Better Stack, free); waiting on account signup /
  API token. Nothing is wired yet.
- **Related:** [`plans/011-launch-readiness.md`](../plans/011-launch-readiness.md),
  [`todos/014-launch-readiness.md`](../todos/014-launch-readiness.md),
  [`docs/runbook.md`](../docs/runbook.md)

## Context that shapes the decision

1. **No domain is assigned to the Dokploy installation yet**, and
   `indic-book-metadata-extractor.agamya.us.kg` is temporary. Both change later.
2. **The origin IP is deliberately left open** (`https://187.127.174.246/`
   answers directly) until the real domain is assigned. Accepted for now.
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

### Items to create

| Type | Target | Settings | Catches |
|---|---|---|---|
| HTTP keyword | `/api/health` | expect `"status":"ok"`, 3 min | site/host down, app hung |
| HTTP | `/login` | expect 200 | frontend/routing broken |
| HTTP | `/` | expect 200 | full CF → Traefik → app path |
| Heartbeat | `daily-backup` | period 86400 s, grace 43200 s (36 h total) | backup missing **or failing** (only a successful run pings) |
| Heartbeat | `host-watchdog` | period 600 s, grace 300 s; pings `/fail` with a one-line reason | worker down, job stuck > 90 min, disk > 85 % |

Detection latency ≈ check interval + grace; SMS/phone escalation is paid.

### Alternatives considered

| Bundle | Free capacity | Channels | Caveats |
|---|---|---|---|
| UptimeRobot + Healthchecks.io | 50 monitors + 20 heartbeats | Email/Discord/Pushover; email/webhooks | Both allow commercial use; no SSL-expiry on UR free |
| HetrixTools + Healthchecks.io | 15 uptime + 15 server agents, 1-min checks | Email, Telegram, Slack, Discord, webhooks | Log in every 90 days; one email recipient; no native heartbeats |
| Uptime Kuma (self-hosted) | unlimited | 90+ | Cannot report its own host being down — rejected for that reason |
| Gatus (self-hosted, YAML) | unlimited | Telegram/Slack/webhook | Same host-death blind spot; rejected |
| Upptime (GitHub Actions) | free | GitHub issues | Ties monitoring to GitHub; 5-min floor |

## Pending from the operator (Better Stack)

1. Sign up at betterstack.com (third-party login — not handled by the agent).
2. Either create the five items above, **or** create an API token, store it in
   the gitignored `reference/betterstack`, and the agent creates them via
   `POST /api/v2/monitors` and `/api/v2/heartbeats`.
3. Say which email address receives alerts (or set it in the dashboard).

## To wire once unblocked (all in-repo, no new services)

1. `infra/host-watchdog.sh` + a systemd timer on `oki` (5 min): worker/backend
   container state, jobs stuck > 90 min (reuses `job_reaper`'s SQL), `df /`
   > 85 %, then ping the heartbeat or `/fail` with the reason. Failures also
   create an **admin in-app notification**.
2. One line in `docker/scripts/backup-db.sh`: ping the backup heartbeat after a
   successful dump (URL from a Dokploy env var, never the repo).
3. `docs/runbook.md` section: what each alert means and the first action.
4. Verify honestly: stop the worker and confirm a real alert arrives.

## Deferred with the domain change (Cloudflare account)

- Close origin ingress (allowlist Cloudflare ranges, or Cloudflare Tunnel).
- Edge WAF managed ruleset + a rate rule on `/api/auth/*`.
- Options if done as code: API token + Terraform/script, so rules are
  reproducible when the domain moves.
- Update the three monitor URLs to the final domain.

## Also still outstanding

- **Offsite backups.** Dumps are restorable (drill verified) and pruned to the
  newest 7, but share the host and disk with the database. Needs a destination
  and credentials.
- **App-level brute-force hardening (A1)** — a global auth budget that no header
  can dodge, plus per-account failure lockout. Proposed, not yet approved.
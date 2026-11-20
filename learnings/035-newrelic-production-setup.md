# New Relic Production Enablement — Retrace Guide

## Scope

Enable New Relic in production (`docker-compose.production.yml` + `.env.production` via Dokploy).
Covers the four agent layers the stack already supports: Python APM (FastAPI + Celery worker),
Node APM (Next.js), Browser RUM, and the (dev-only) infra sidecar.

## TL;DR

The Compose stack was already fully wired for New Relic; the env block in `.env.production` was
commented out and contained placeholder values. Enabling it is an env + rebuild exercise, not a
code change. The frontend bakes the config in **at build time**, so a rebuild is mandatory.

## Prerequisites / facts verified in the repo

| Fact | Where |
| --- | --- |
| Compose passes `NEW_RELIC_*` to backend, worker, frontend, and (dev only) infra | `docker-compose.production.yml:135-143,209-217,250-252,258-260` |
| Production has **no** `newrelic-infra` sidecar (dev `monitoring` profile only) | `docker-compose.production.yml` (no such service) |
| Frontend reads `NEW_RELIC_ENABLED` + `NEXT_PUBLIC_NEW_RELIC_*` as **build args** (baked at build) | `docker/Dockerfile.frontend:42-47,57-59` |
| Browser agent is injected by the app itself (not by a pasted snippet) | `frontend/src/instrumentation.ts:21`, `frontend/src/app/layout.tsx:103`, `frontend/newrelic.cjs` |
| Python agent config reads `NEW_RELIC_*` env | `backend/newrelic.ini` (`license_key = %(NEW_RELIC_LICENSE_KEY)s`, `app_name = %(NEW_RELIC_APP_NAME)s`) |

**Critical gotcha:** because the frontend is a **build ARG**, `docker compose up` after editing env
does NOT instrument the frontend. You must rebuild the frontend image (or do a full Dokploy deploy).

## Procedure (as performed)

### 1. Clean up old dev credentials (the New Relic account)

Old dev app was deleted before this work, so its APM entity was gone. In New Relic:

- Deleted the dev **Ingest - License** key (labeled "(2026-06-21)"). Done.
- Deleted the dev **Browser app** entity. Done.
- Tried to delete the account-original browser key → **failed by design**:
  "An account's original browser key cannot be deleted." This is harmless; a browser key is a
  public write-only ingest token. Leave it.
- The account-original **license key** is also undeletable. Leave it.

### 2. Create fresh production APM credentials

- **API Keys → Create key**
  - Type: **Ingest - License**
  - Name: `Prod license key`
- → 40-char key used for `NEW_RELIC_LICENSE_KEY`
  (key type **INGEST - LICENSE**; value lives in Dokploy → Environment, not in this doc)

### 3. Create the production Browser app

- **Browser → Add a browser app** → name `Open Book Map (Prod)`
- Install method: **"Place a JavaScript snippet in frontend code"**
  (NOT "Connect to APM" — that path needs an existing APM entity, which does not exist before the
  first deploy; NOT npm — the agent is already in the image.)
- **Capture session replays: off** (overhead + privacy surface; the repo's agent config does not
  enable replay, so leaving it off keeps config consistent). **Distributed tracing: on.**
- From the generated snippet, the values were:
  - Browser license key: `NRBR-…` → `NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY`
  - Application ID: `<app-id>` → `NEXT_PUBLIC_NEW_RELIC_APP_ID`
  - Account ID: `<account-id>` → `NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID`
- **Do NOT paste the snippet into the HTML.** `frontend/src/instrumentation.ts` +
  `layout.tsx` already inject the agent; pasting would double-instrument.

### 4. Fill `.env.production`

Final block (lines 94–108):

```bash
NEW_RELIC_ENABLED=true
NEW_RELIC_LICENSE_KEY="<40-char INGEST-LICENSE key from Dokploy Environment>"
NEW_RELIC_APP_NAME="Open Book Map (Prod)"
NEW_RELIC_ENVIRONMENT=production
NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true
NEW_RELIC_LOG=error
NEW_RELIC_MONITOR_MODE=true
NEW_RELIC_DEVELOPER_MODE=false

NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY="<NRBR browser key from Dokploy Environment>"
NEXT_PUBLIC_NEW_RELIC_APP_ID=<app-id>
NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID=<account-id>
```

Notes:
- `NEW_RELIC_APP_NAME` set to `"Open Book Map (Prod)"`; the worker gets its own name from Compose
  (`Open Book Map Worker`). Compose defaults are `Open Book Map` / `Open Book Map Worker`.
- Keep `NEW_RELIC_ENVIRONMENT=production`, `NEW_RELIC_LOG=error`, `NEW_RELIC_MONITOR_MODE=true`,
  `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true`, `NEW_RELIC_DEVELOPER_MODE=false`.
- Plain-text comment lines must not sit inside the key block (an earlier draft had one uncommented;
  Compose would break parsing). Keep them prefixed with `#`.

### 5. Deploy (Dokploy — source of truth is the Environment tab, not the file)

`.env.production` in the repo is a local reference; **Dokploy → service → Environment** is what the
deploy actually reads.

1. Paste the same block into Dokploy → service → **Environment** tab.
2. **Deploy** (rebuild). This is what makes the frontend build args pick up the values.
3. Wait a few minutes, then verify (see below).

## Verification checklist

```bash
# Browser snippet present on the live site (should be a populated NREUM.info object,
# not the <!-- NREUM: (4) --> placeholder):
curl -s https://openbookmap.oki-india.org | grep -o 'NREUM.info={[^}]*}'
```

- **APM & Services → Installed**: `Open Book Map (Prod)` appears; worker under
  `Open Book Map Worker`.
- **Browser**: the `Open Book Map (Prod)` browser app shows page loads / Core Web Vitals.
- **Traces**: distributed traces link frontend → backend → worker.
- Container logs should show no `license key` / `app name` errors from either agent.

## Rollback

Set `NEW_RELIC_ENABLED=false` (and comment the browser `NEXT_PUBLIC_*` block) in the Dokploy
Environment tab and redeploy. The agents no-op when disabled; nothing else changes.

## Open items / follow-ups

- **Infra agent not in prod.** `docker-compose.production.yml` has no `newrelic-infra` sidecar, so
  the Infrastructure section of New Relic stays empty for production until one is added (dev-only
  `monitoring` profile today). See `docker-compose.yml`.
- **Keys are account-scoped, not team-scoped.** The ingest/browser keys are org-wide; consider
  scoping them to a prod team via "Assign team" on each key in API Keys.
- **Optional browser↔APM linking.** After the first deploy (once the APM entity exists), you can
  link browser data to the APM app from the APM app's settings for unified traces.

## Credential summary (for audit)

| Purpose | Key type | Value / identifier |
| --- | --- | --- |
| APM ingest (backend + worker) | INGEST - LICENSE | (masked; full value in Dokploy → Environment) |
| Browser ingest (frontend) | BROWSER (NRBR) | (masked; full value in Dokploy → Environment) |
| Browser Application ID | — | (in Dokploy → Environment) |
| Account ID | — | (in Dokploy → Environment) |
| Dev APM key (deleted) | INGEST - LICENSE | (removed) |
| Account-original browser key (undeletable) | INGEST - BROWSER | (left in place; undeletable) |
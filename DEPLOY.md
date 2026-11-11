# Deploying to Dokploy

## One-Time Setup (5 minutes)

### 1. Create Dokploy Compose Service

```
Dokploy Dashboard
  → Projects → Create Project → Name: "Indic Book Extractor"
  → Add Service → Docker Compose
    → Name: indic-books
    → Source: Git Repository
    → Repository URL: https://github.com/YOUR_USER/Indic-Book-Metadata-Extractor.git
    → Branch: main
    → Compose Path: docker-compose.production.yml     ← IMPORTANT: use this file
```

### 2. Set Environment Variables

In the service → **Environment** tab, add these variables:

| Variable | Value | Required |
|----------|-------|----------|
| `POSTGRES_PASSWORD` | `<strong-random-password>` | ✅ Yes |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` | ✅ Yes |
| `FRONTEND_URL` | `https://YOUR_DOMAIN` (used in email links) | ✅ Yes |
| `NEXT_PUBLIC_API_URL` | `/api` — relative, one public origin | ✅ Yes |
| `CORS_ORIGINS` | `https://YOUR_DOMAIN` | Recommended |
| `FLOWER_BASIC_AUTH` | `admin:<password>` | Recommended |
| `SMTP_ENABLED` | `true` (required for account emails in production) | ✅ Yes (accounts) |
| `SMTP_HOST` | e.g. `mx.msgwing.com` | ✅ Yes (accounts) |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (SSL) | ✅ Yes (accounts) |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP login credentials | ✅ Yes (accounts) |
| `SMTP_FROM` | e.g. `northcay@msgwing.com` | ✅ Yes (accounts) |
| `PASSWORD_MIN_LENGTH` | Default `10` | Optional |

`POSTGRES_PASSWORD`, `JWT_SECRET_KEY` and `FRONTEND_URL` are declared with
`:?` in `docker-compose.production.yml`, so a deploy **aborts at interpolation**
if any is missing — with no containers replaced.

SMTP is required for the email-verification and password-reset emails that
account registration depends on. Keep the real credentials in the
git-ignored `.env` (or the Dokploy environment tab) — never commit them.

Everything else has working defaults.

### 3. Configure Domains

The frontend domain is the **only** public entry point. Internal services
(postgres, redis, ollama, worker, flower, mysql, elasticsearch, backup) have
**no** domains — they communicate over the Docker network by service name.

In the service → **Domains** tab:

| Service | Domain | Path | Port |
|---------|--------|------|------|
| `frontend` | `YOUR_DOMAIN` | `/` | 3000 |
| `backend` | `YOUR_DOMAIN` | `/api` | 8000 |
| `openrefine` | `openrefine.YOUR_DOMAIN` (operator tool) | `/` | 3333 |
| `wikibase` | `wikibase.YOUR_DOMAIN` (publish target) | `/` | 80 |

Leave **Strip Path** off for the backend so `/api/...` reaches the app unchanged.
Enable HTTPS (Let's Encrypt) for each.

Do **not** give the backend its own hostname (e.g. `api.YOUR_DOMAIN`): the CSRF
cookie is host-only, so a split origin makes the frontend unable to read it and
every mutation fails with `403 CSRF validation failed`.

Dokploy's own panel (port 3000) and Traefik's API (port 8080) are published on
the host by Dokploy itself. Keep them off the public internet — reach them over
an SSH tunnel (`ssh -L 3000:localhost:3000 oki`) or firewall them.

### 4. Deploy

Click **Deploy**. First deploy takes ~15 min (Ollama downloads the Airavata 7B model).

### 5. Create the first admin

Registration is open but new accounts must verify their email, and nobody can
self-register as an admin. Create the first administrator once, from the
server, after the stack is up:

```bash
make create-admin EMAIL=admin@YOUR_DOMAIN DISPLAY_NAME="Admin"
# Password is prompted for when omitted (or pass PASSWORD=...).
```

That account is created verified and active — log in at the frontend and use
**Admin → Users** to create or promote further admins.

> Note: migration `012` (users/roles/ownership) refuses to run on a database
> that already contains books — the production DB is reset on this deploy, so
> books are re-uploaded under their owners afterwards.

---

## Deploying Updates (after initial setup)

### Option A: Auto-deploy on git push

Enable **Auto Deploy** in Dokploy service settings. Every `git push origin main` triggers a rebuild.

### Option B: Manual deploy via script

```bash
# First time: set these once
export DOKPLOY_URL=https://dokploy.YOUR_DOMAIN
export DOKPLOY_TOKEN=dp_xxxxx            # Settings → API Keys
export DOKPLOY_COMPOSE_ID=abc123         # from URL bar when viewing the service

# Deploy
./scripts/dokploy-deploy.sh              # push + deploy
./scripts/dokploy-deploy.sh --no-push    # deploy without pushing
./scripts/dokploy-deploy.sh --status     # check status
```

### Option C: Manual deploy in UI

Go to Dokploy → Service → click **Deploy**.

---

## Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| CPU | 2 cores | 4 cores |
| Disk | 40 GB | 80 GB |

> **Why so much RAM?** Ollama + Airavata 7B needs ~5GB, plus Postgres, Redis, backend, frontend, and Celery worker.

---

## How Each Container is Handled

```
┌──────────────────────────────────────────────────────────────┐
│                    Dokploy Host                              │
│                                                              │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────────────┐│
│  │  postgres    │  │  redis   │  │  ollama (Airavata 7B)    ││
│  │  pgvector:16 │  │  7-alpine│  │  ~5GB RAM                ││
│  │  port 5432   │  │  6379    │  │  11434                   ││
│  └──────┬───────┘  └────┬─────┘  └───────────┬──────────────┘│
│         │               │                    │               │
│         └───────────────┼────────────────────┘               │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────────┐│
│  │  backend (FastAPI)                worker (Celery)        ││
│  │  → runs Alembic migrations       → OCR + LLM tasks       ││
│  │  → serves REST API               → shares storage volume ││
│  │  → exposed via Dokploy proxy                             ││
│  └──────────────────────┬───────────────────────────────────┘│
│                         │                                    │
│  ┌──────────────────────┴──────┐  ┌─────────┐  ┌──────────┐  │
│  │  frontend (Next.js)         │  │  flower │  │  backup  │  │
│  │  → standalone mode          │  │  :5555  │  │  daily   │  │
│  │  → exposed via Dokploy proxy│  └─────────┘  └──────────┘  │
│  └─────────────────────────────┘                             │
└──────────────────────────────────────────────────────────────┘

Volumes (persisted across deploys):
  pgdata       → PostgreSQL data
  redis_data   → Redis AOF
  ollama_data  → Model weights (~4GB)
  storage_data → Uploaded PDFs, thumbnails, OCR pages
  backup_data  → DB dump backups (last 7 retained)
```

---

## Running Production + Staging on the Same Host

You can host both environments on a single Dokploy server using **two full standalone compose files + per-env env file**. Each compose is self-contained and reviewable in one read — no merge semantics, no override surprises.

### File layout

```
docker-compose.yml                # dev / ad-hoc local stack
docker-compose.production.yml     # full standalone, production-tuned
docker-compose.staging.yml        # full standalone, staging-tuned
.env.production.example           # production env template
.env.staging.example              # staging env template
.env.production                   # real secrets (gitignored)
.env.staging                      # real secrets (gitignored)
```

The two environments that run on Dokploy are the standalone files (`docker-compose.production.yml`
and `docker-compose.staging.yml`); `docker-compose.yml` is the local dev stack. QuickStatements is
`expose: 80` in all of them so Traefik routes it — the old `9191:80` host-port binding would have
prevented a second environment from starting.

### Step 1 — Create two Dokploy Compose services

```
Dokploy Dashboard
  → Projects → "Indic Book Extractor"
  → Add Service → Docker Compose     (production)
    → Name: indic-books-prod
    → Compose Path: docker-compose.production.yml
    → Project Name: indic-books-prod

  → Add Service → Docker Compose     (staging)
    → Name: indic-books-staging
    → Compose Path: docker-compose.staging.yml
    → Project Name: indic-books-staging
```

The **Project Name** is critical. If both services use the same project name, they fight over Docker volume names (`pgdata`, `redis_data`, etc.) and one will silently corrupt the other's database.

### Step 2 — Use distinct domains

The frontend host is the only public entry point in each environment; the API
is a path on that same host (`/api`), never its own subdomain.

| Service | Production | Staging |
|---------|------------|---------|
| Frontend | `YOUR_DOMAIN` `/` | `staging.YOUR_DOMAIN` `/` |
| Backend | `YOUR_DOMAIN` `/api` | `staging.YOUR_DOMAIN` `/api` |
| OpenRefine | `openrefine.YOUR_DOMAIN` | `staging-openrefine.YOUR_DOMAIN` |
| Wikibase | `wikibase.YOUR_DOMAIN` | `staging-wikibase.YOUR_DOMAIN` |
| QuickStatements | *(internal unless you use its UI)* | *(internal)* |
| Flower | *(internal)* | *(internal)* |

**Never reuse a production domain on staging.** Traefik routes by hostname and Let's Encrypt will refuse to issue a duplicate cert.

### Step 3 — Distinct secrets per environment

Generate fresh secrets for staging — never copy production values:

```bash
openssl rand -hex 32   # run 4× for POSTGRES_PASSWORD, WIKIBASE_ADMIN_PASS,
                       # MW_SECRET_KEY, MW_UPGRADE_KEY
```

Paste them into the staging service's Environment tab. Use `.env.staging.example` as the starting template.

### Step 4 — Drift check

Because the two compose files are full copies, edits to one can silently drift from the other. To catch this:

```bash
make check-compose-drift
```

This diffs the two files and fails if it sees changes outside an allowlist (DEBUG flag, New Relic env labels, memory limits, URL schemes, worker concurrency, comments). Run it in CI on every PR that touches either compose file.

### Step 5 — Deploy

Deploy each service in any order. To keep them in sync, the recommended workflow is:

1. Edit `docker-compose.production.yml` first (treat it as the source of truth)
2. Mirror the change into `docker-compose.staging.yml` (keep allowlisted differences)
3. `make check-compose-drift` — must pass before push
4. Push to `main`; both Dokploy services redeploy

### What differs between the two files

| Setting | Production | Staging |
|---------|------------|---------|
| `DEBUG` | `false` | `true` |
| `NEW_RELIC_ENVIRONMENT` | `production` | `staging` |
| `APP_NAME` | `…Extractor` | `…Extractor (staging)` |
| Backend memory limit | 2 GB | 1 GB |
| Worker memory limit | 4 GB | 2 GB |
| Worker concurrency | 8 | 4 |
| Ollama memory limit | 8 GB | 6 GB |
| Wikibase `MW_WG_SERVER` | `https://...` | `http://...` |
| Backup memory limit | (none) | 128 MB |

Everything else (service definitions, image tags, volumes, healthchecks, depends_on, build contexts) is byte-identical. If you need to change a service definition, change it in both files in the same commit.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Ollama health check fails | Wait 2-3 min. Model download on first boot takes time. Check Ollama logs. |
| Backend can't connect to DB | Verify `POSTGRES_PASSWORD` is set in Dokploy env. Check postgres logs. |
| Frontend shows wrong API URL | Rebuild frontend after changing `NEXT_PUBLIC_API_URL` (it's baked at build time). |
| Worker not processing tasks | Check worker logs in Dokploy. Ensure Redis and Ollama are healthy. |
| Out of memory | Upgrade server to 16GB, or host Ollama on a separate machine and set `OLLAMA_URL`. |
| CORS errors | Set `CORS_ORIGINS` to your exact domain in Dokploy env, then redeploy backend. |

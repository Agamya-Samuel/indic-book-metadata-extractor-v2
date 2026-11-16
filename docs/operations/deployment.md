# Deployment

Production runs on **Dokploy** as a self-contained Docker Compose stack. This document is the
canonical deployment reference; `DEPLOY.md` at the repository root is a pointer to it.

- Production compose: `docker-compose.production.yml`
- Staging compose: `docker-compose.staging.yml`
- Helpers: `Makefile`, `scripts/dokploy-deploy.sh`
- Environment contract: [configuration](../development/configuration.md)

> Host addresses, node names and panel ports are deliberately **not** recorded here. This repository
> is public; operational specifics live in a gitignored `infra/local/`.

---

## 1. Topology

```text
Cloudflare (DNS, TLS)
        │
    Traefik (Dokploy)
        ├── /      → frontend  :3000
        └── /api   → backend   :8000
                        │
        ┌───────────────┼───────────────┬──────────────┐
     postgres        redis           ollama        worker
     (pgvector)      (broker)        (gemma4)      (celery)

  internal only: flower, backup, wikibase*, quickstatements, mysql, elasticsearch, openrefine
```

**The frontend and backend must share one host.** The session cookie is host-only and `SameSite=Lax`;
giving the API its own subdomain makes the CSRF cookie unreadable and every mutation fails with
`403 CSRF validation failed`.

---

## 2. First-time setup

### 2.1 Create the compose service

```text
Dokploy → Projects → Create Project → "Indic Book Extractor"
  → Add Service → Docker Compose
    → Name:            indic-books-prod
    → Source:          Git Repository
    → Branch:          main
    → Compose Path:    docker-compose.production.yml    ← must be this file
    → Project Name:    indic-books-prod
```

The **Project Name** is critical. Two environments sharing a project name collide on volume names
(`pgdata`, `redis_data`, …) and one silently corrupts the other's database.

### 2.2 Set environment variables

In the service → **Environment** tab. `.env.production.example` is the template.

Required (Compose declares these with `:?`, so a missing value aborts the deploy **before** replacing
containers):

| Variable | Generation |
| --- | --- |
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` (≥32 chars enforced) |
| `FRONTEND_URL` | `https://<your-domain>` — used in email links |

Strongly recommended:

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `/api` (relative — keeps one origin) |
| `CORS_ORIGINS` | `https://<your-domain>` |
| `FLOWER_BASIC_AUTH` | `admin:<password>` |
| `COOKIE_SECURE` | `true` |
| `SMTP_*` | Required for verification and reset email |

Everything else has a working default. See [configuration](../development/configuration.md).

### 2.3 Configure domains

| Service | Path | Port | Exposed? |
| --- | --- | --- | --- |
| `frontend` | `/` | 3000 | **yes** |
| `backend` | `/api` | 8000 | **yes** |
| `wikibase` | `/` | 80 | optional |
| `openrefine` | `/` | 3333 | optional, operator tool |
| everything else | — | — | internal only |

- Leave **Strip Path** off for the backend so `/api/...` arrives unchanged.
- Enable HTTPS for each.
- One environment must never reuse another environment's hostname: Traefik routes by host and
  Let's Encrypt refuses duplicate certificates.

### 2.4 Deploy

Press **Deploy**. The first deploy takes a while:

- Ollama pulls `gemma4:e4b` (~6.6 GB).
- The worker image bakes CPU torch/transformers plus the Telugu OCR model, gated behind the
  `OCR_LINE=true` build arg. Weights are baked in and never downloaded at runtime
  (`HF_HUB_OFFLINE=1`). The backend image is built **without** the extra, so it stays small.
- The backend entrypoint runs `alembic upgrade head` before starting.

### 2.5 Create the first administrator

Registration is open but new accounts must verify email, and nobody can self-register as admin:

```bash
make create-admin EMAIL=admin@<your-domain> DISPLAY_NAME="Admin"
```

The account is created verified and active. Further admins are managed in **Admin → Users**.

> Migration `012` (users/roles/ownership) refuses to run against a database that already contains
> books. A database from before auth existed must be reset; books are re-uploaded under their owners.

---

## 3. Updating a deployment

| Method | How |
| --- | --- |
| Auto-deploy | Enable in Dokploy; every push to `main` rebuilds |
| Script | `./scripts/dokploy-deploy.sh` (push + deploy), `--no-push`, `--status` |
| Manual | Dokploy → Service → **Deploy** |

The script needs three environment variables:

```bash
export DOKPLOY_URL=https://<dokploy-host>
export DOKPLOY_TOKEN=dp_xxxxxxxx            # Settings → API Keys
export DOKPLOY_COMPOSE_ID=<service-id>      # from the service URL
```

Treat `DOKPLOY_TOKEN` as a live credential: keep it in `scripts/.env` (gitignored) and rotate it if it
is ever exposed.

---

## 4. Resources

| Resource | Minimum | Recommended |
| --- | --- | --- |
| RAM | 8 GB | 16 GB |
| CPU | 2 cores | 4 cores |
| Disk | 40 GB | 80 GB |

Why so much RAM: `gemma4:e4b` is ~6.7 GB resident idle and peaks near 7.9 GB during extraction, under
a 9 GB container cap. Postgres, Redis, backend, frontend, and the Celery worker add roughly 1.2 GiB.

The reference host is 4 vCPU / 16 GB with **no swap**, which is why the pipeline processes one book at
a time and Ollama is capped at one loaded model and one parallel request.

The optional stack adds ~2.5 GiB of idle memory and can be stopped without affecting the pipeline —
see [integrations](../architecture/integrations.md).

---

## 5. Persistence

| Volume | Contents |
| --- | --- |
| `pgdata` | PostgreSQL data |
| `redis_data` | Redis AOF |
| `ollama_data` | Model weights |
| `storage_data` | Uploaded PDFs, rendered pages, processed images, thumbnails, fine-tuned OCR model |
| `backup_data` | `pg_dump` archives, last 7 retained |
| `wikibase_config`, `wikibase_data`, `quickstatements_data`, `mysql_data`, `elasticsearch_data`, `openrefine_data` | Optional stack |

**Never run `docker compose down -v`** against an environment you want to keep. Stopping and starting
is safe; removing volumes is not.

---

## 6. Production vs staging

Both are full standalone compose files, deliberately duplicated rather than overlapping, so each is
reviewable in one read.

| Aspect | Production | Staging |
| --- | --- | --- |
| Compose | `docker-compose.production.yml` | `docker-compose.staging.yml` |
| Env template | `.env.production.example` | `.env.staging.example` |
| Real env | `.env.production` (gitignored) | `.env.staging` (gitignored) |
| `DEBUG` | `false` | differs (see drift report) |
| `NEW_RELIC_ENVIRONMENT` | `production` | `staging` |
| `APP_NAME` | app name | app name ` (staging)` |
| Worker | `--concurrency=1 -Q ocr,llm,default` | `--concurrency=1 -Q ocr,llm,default` |

Service definitions, volumes, healthchecks, `depends_on` and build contexts should be **byte-identical**.
Only the values above are expected to differ.

### Drift check

```bash
make check-compose-drift
```

Diffs production against staging, ignoring comments, `DEBUG`, `NEW_RELIC_*`, `APP_NAME`, memory
limits, `WIKIBASE_SCHEME`, worker concurrency and URL schemes. An unexpected diff means one file was
edited and the other was not.

### Environment sync workflow

1. Edit `docker-compose.production.yml` first (source of truth).
2. Mirror the change into `docker-compose.staging.yml`.
3. `make check-compose-drift` — must pass.
4. Push; both services redeploy.

Generate **fresh** secrets per environment. Never copy production values into staging.

---

## 7. Rollback

| Scenario | Action |
| --- | --- |
| Bad application code | Redeploy the previous commit from Dokploy (it rebuilds from git) |
| Bad migration | Restore the last `pg_dump` — see [backup-and-recovery](backup-and-recovery.md) |
| Bad environment variable | Fix in the Environment tab and redeploy |
| Model regression | Set `OLLAMA_PRELOAD_MODEL` back to `phi4-mini` and redeploy |

There is no automated migration rollback in the deploy path. Alembic downgrades exist but are not
exercised routinely; restoring a dump is the reliable path.

---

## 8. Security notes

- Only `frontend` and `backend` should have public domains. Everything else stays on the internal
  network.
- `COOKIE_SECURE=true` in any HTTPS deployment.
- `FLOWER_BASIC_AUTH` is mandatory if Flower is reachable at all.
- Dokploy's own panel and Traefik's API are published by Dokploy on the host. If you restrict them,
  use `DOCKER-USER` iptables, **not `ufw`** — Docker bypasses `ufw`. Keep an SSH tunnel open first;
  closing the panel port locks you out.
- Rate limiting lives in Redis. If Redis is down, limiting is skipped, not enforced.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Ollama health check fails | Model still downloading | Wait; check Ollama logs; `start_period` is 120 s |
| Backend cannot reach the database | `POSTGRES_PASSWORD` unset or changed | Set it in Dokploy and redeploy |
| Frontend calls the wrong API host | `NEXT_PUBLIC_API_URL` is baked at build time | Change it and **rebuild** |
| Every mutation returns 403 CSRF | Frontend and API on different origins | Serve both on one host with `/api` path |
| Worker idle, jobs queued | Redis or Ollama unhealthy | Check `make status`, worker logs |
| OOM kills | Model residency plus optional stack | Host Ollama separately or stop optional services |
| Stale jobs accumulate | Worker died mid-task | Reaper clears them after `STALE_JOB_MINUTES` (90); or cancel manually |
| Deploy aborts immediately | A `:?` variable is missing | Check the interpolation error in the deploy log |

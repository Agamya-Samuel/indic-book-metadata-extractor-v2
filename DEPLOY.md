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
    → Compose Path: docker-compose.dokploy.yml     ← IMPORTANT: use this file
```

### 2. Set Environment Variables

In the service → **Environment** tab, add these variables:

| Variable | Value | Required |
|----------|-------|----------|
| `POSTGRES_PASSWORD` | `<strong-random-password>` | ✅ Yes |
| `NEXT_PUBLIC_API_URL` | `https://YOUR_DOMAIN/api` | ✅ Yes |
| `CORS_ORIGINS` | `https://YOUR_DOMAIN` | Recommended |
| `FLOWER_BASIC_AUTH` | `admin:<password>` | Recommended |

Everything else has working defaults.

### 3. Configure Domains

In the service → **Domains** tab:

| Service | Domain | Port |
|---------|--------|------|
| `backend` | `YOUR_DOMAIN` | 8000 |
| `frontend` | `YOUR_DOMAIN` or `app.YOUR_DOMAIN` | 3000 |
| `flower` | `flower.YOUR_DOMAIN` (optional) | 5555 |

Enable HTTPS (Let's Encrypt) for each.

### 4. Deploy

Click **Deploy**. First deploy takes ~15 min (Ollama downloads the Airavata 7B model).

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

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Ollama health check fails | Wait 2-3 min. Model download on first boot takes time. Check Ollama logs. |
| Backend can't connect to DB | Verify `POSTGRES_PASSWORD` is set in Dokploy env. Check postgres logs. |
| Frontend shows wrong API URL | Rebuild frontend after changing `NEXT_PUBLIC_API_URL` (it's baked at build time). |
| Worker not processing tasks | Check worker logs in Dokploy. Ensure Redis and Ollama are healthy. |
| Out of memory | Upgrade server to 16GB, or host Ollama on a separate machine and set `OLLAMA_URL`. |
| CORS errors | Set `CORS_ORIGINS` to your exact domain in Dokploy env, then redeploy backend. |

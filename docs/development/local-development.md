# Local Development

Running the whole stack locally, and the day-to-day loop.

- Compose: `docker-compose.yml` (development)
- Task runner: `Makefile`
- Frontend: `frontend/` (Next.js 16)
- Backend: `backend/` (FastAPI, `uv`)

---

## 1. Prerequisites

| Tool | Why |
| --- | --- |
| Docker + Compose v2 | Everything runs in containers; no host Python/Node required |
| Make | The `Makefile` is the supported entry point |
| ~20 GB free disk | Images plus the model weights |
| 16 GB RAM recommended | `gemma4:e4b` is ~6.7 GB resident; Tesseract is CPU-hungry |

| Resource | Minimum | Notes |
| --- | --- | --- |
| RAM | 16 GB | 8 GB is the model alone; the rest is Postgres, Redis and the worker |
| CPU | 4 cores | CPU-only extraction takes tens of minutes per book |
| Disk | 20 GB | `gemma4:e4b` is ~6.6 GB; datasets add ~1.2 GB |

`uv` and Node are only needed if you run the backend or frontend **outside** Docker.

---

## 2. First run

```bash
cp .env.example .env          # then edit the required values
make up                       # build and start
make status                   # container health
make migrate                  # apply Alembic migrations
make create-admin             # first admin account
make download-model           # pull the Ollama model
```

Then open the frontend on `http://localhost:3000`.

`.env.example` is the template. At minimum set a real `POSTGRES_PASSWORD`, a ≥32-character
`JWT_SECRET_KEY`, and `FRONTEND_URL`. See [configuration](configuration.md) for every variable.

---

## 3. Development topology differs from production

This is the most common source of confusion. **Dev splits the workers; production does not.**

| | Development (`docker-compose.yml`) | Production (`docker-compose.production.yml`) |
| --- | --- | --- |
| OCR tasks | `worker-ocr`, `-Q ocr,default`, concurrency 1 | `worker`, `-Q ocr,llm,default`, concurrency 1 |
| LLM tasks | `worker-llm`, `-Q llm`, concurrency 1 | same single `worker` |
| New Relic infra agent | present under `profiles: [monitoring]` | absent |
| Debug | `DEBUG=true` | `DEBUG=false` |

So `make logs-worker-ocr` and `make logs-worker-llm` exist, but in production both queues are served by
one container. Queue names are identical either way.

---

## 4. Make targets

| Target | Purpose |
| --- | --- |
| `up` / `down` / `restart` | Compose lifecycle |
| `build` / `rebuild` | Build images |
| `status` / `logs` | Container health and logs |
| `logs-backend`, `logs-worker-ocr`, `logs-worker-llm` | Per-service logs |
| `migrate` | Run Alembic migrations |
| `create-admin` | Create/promote an admin (interactive) |
| `reset-db` | **Destructive** — drop and recreate the database |
| `download-model` | Pull the configured Ollama model |
| `test-e2e` | Run the end-to-end script against a running stack |
| `shell-backend` | Shell into the backend container |
| `clean` | Remove containers and volumes — **destructive** |
| `backup-db`, `backup-storage`, `backup`, `restore-db` | Backup and restore |
| `check-compose-drift` | Diff production vs staging compose, ignoring expected deltas |
| `deploy`, `deploy-status`, `deploy-env` | Dokploy helpers (see [deployment](../operations/deployment.md)) |
| `prompt-*` | Prompt evaluation harness (`corpus`, `mask`, `fewshot`, `bundles`, `eval`, `report`, …) |
| `wikibase-*` | Optional Wikibase stack helpers |

---

## 5. Native setup (without Docker)

For hot-reloading and faster iteration. You still need PostgreSQL, Redis and Ollama running.

### 5.1 Install system dependencies

**Ubuntu / Debian / WSL 2**

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y postgresql-16 postgresql-server-dev-16
sudo apt install -y redis-server
sudo apt install -y tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin tesseract-ocr-eng
curl -fsSL https://ollama.com/install.sh | sh
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
```

**macOS**

```bash
brew install postgresql@16 redis tesseract tesseract-lang ollama uv node@20
```

**Windows** — use WSL 2 with the Ubuntu steps (`wsl --install` from an elevated PowerShell).

#### OCR packages and the Telugu line model

System packages carry Tesseract (LSTM only) plus `tel`, `hin` and `eng` language data. Tesseract is
spawned as a subprocess per page — there is no OCR service.

Python dependencies come in two tiers:

```bash
cd backend
uv sync                  # Tesseract only
uv sync --extra ocr-line # adds torch + transformers for the Telugu line model
```

`transformers` is pinned to `4.46.*` because 5.x breaks the line model's custom code
(`all_tied_weights_keys`). Torch resolves through an explicit CPU-only index, so CUDA wheels are never
pulled:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

The line-model weights (~310 MB) are baked into the **worker** image only, behind the `OCR_LINE=true`
build arg, and are never downloaded at runtime (`HF_HUB_OFFLINE=1`). Setting
`OCR_TEL_ENGINE=line_model` locally without torch or the weights makes every Telugu page fall back to
Tesseract and record `pages.ocr_error` — useful to know before debugging accuracy.

### 5.2 Start the dependencies

```bash
sudo service postgresql start     # macOS: brew services start postgresql@16
sudo service redis-server start   # macOS: brew services start redis

createdb indic_books
psql -d indic_books -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql -d indic_books -c "\dx"      # confirm pg_trgm

redis-cli ping                    # → PONG

ollama serve &
ollama pull gemma4:e4b            # ~6.6 GB
ollama list
```

### 5.3 Backend

```bash
cd backend
uv sync
cp ../.env.example .env
```

Point the env file at **localhost**, replacing the Docker service names:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books
REDIS_URL=redis://localhost:6379/0
OLLAMA_URL=http://localhost:11434
STORAGE_PATH=./storage
```

```bash
mkdir -p storage/uploads storage/thumbnails storage/pages storage/processed
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

### 5.4 Frontend

```bash
cd frontend
npm install
# only if the API is not on the default port:
# echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev            # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` must point at the backend origin, and that origin must appear in `CORS_ORIGINS`.
Cookies are `SameSite=Lax`, so a cross-origin setup breaks sessions — prefer keeping everything on
`localhost:3000` via the Docker frontend.

### 5.5 Verify

```bash
curl http://localhost:8000/health          # {"status":"ok",...}
curl http://localhost:11434/api/tags       # should list gemma4:e4b
tesseract --list-langs                     # should include tel, hin, eng
```

Test commands live in [running-tests](../testing/running-tests.md).

---

## 6. Port reference

| Service | Port | URL |
| --- | --- | --- |
| Next.js frontend | 3000 | `http://localhost:3000` |
| FastAPI backend | 8000 | `http://localhost:8000` (docs at `/docs` when `DEBUG=true`) |
| PostgreSQL | 5432 | `postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books` |
| Redis | 6379 | `redis://localhost:6379/0` |
| Ollama | 11434 | `http://localhost:11434` |
| Flower | 5555 | `http://localhost:5555` (dev compose only) |
| Wikibase | 8181 | `http://localhost:8181` (optional) |
| OpenRefine | 3333 | `http://localhost:3333` (optional) |
| MySQL / MariaDB | internal | Wikibase database, not published |
| Elasticsearch | internal | Wikibase search index, not published |

In production only the frontend and backend are published; both sit behind one host with the API on
`/api`. See [deployment](../operations/deployment.md).

---

## 7. Day-to-day loop

1. `make logs-worker-ocr` (or `-llm`) in one terminal.
2. Upload a small PDF and drive one stage at a time.
3. For OCR changes, run the OCR evaluation harness rather than eyeballing one page — see
   [evaluation](../testing/evaluation.md).
4. Run `npm run lint`, `npm test` (frontend) and the backend unit suite before pushing.
5. `make check-compose-drift` if you touched either compose file.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Backend exits: `JWT_SECRET_KEY must be at least 32 characters` | Non-debug mode with a short key | Set a 64-char hex value |
| Upload returns 413 | `MAX_UPLOAD_SIZE_MB` too low | Raise it in `.env` and restart |
| OCR returns empty text | Language data missing | Check `TESSERACT_TESSDATA_DIR`; see [ocr](../processing/ocr.md) |
| `tesseract --list-langs` lacks `tel`/`hin` | Language packs not installed | Ubuntu: `tesseract-ocr-tel tesseract-ocr-hin`; macOS: `tesseract-lang` |
| Extraction returns all nulls | Model not pulled, or wrong endpoint | `make download-model`; check `LLM_NATIVE_ENDPOINT` |
| `model not found` from Ollama | Model absent | `ollama pull gemma4:e4b`, then `ollama list` |
| First start is slow | Model download and image build | One-time; cached in `ollama_data` or `~/.ollama/models` |
| Emails not sent | `SMTP_ENABLED=false` (the default) | Set SMTP variables, or accept in-app notifications only |
| Book stuck at `ocr_running` | A worker died | Wait for the reaper (90 min) or cancel the job |
| Port already in use | Another process holds it | `lsof -i :<PORT>` then `kill -9 <PID>`; Windows: `netstat -ano` + `taskkill` |
| `CREATE EXTENSION pg_trgm` fails | The `postgresql-contrib` package is missing | Install `postgresql-contrib` for your PG16 package, or use the `postgres:16-bookworm` image |
| Celery: `Cannot connect to redis://…` | Redis down or wrong URL | `redis-cli ping`; check `REDIS_URL` points at localhost for native runs |
| SQLAlchemy: `cannot connect to server` | Postgres down, or URL still points at the `postgres` container name | `pg_isready -U postgres`; set `DATABASE_URL` to localhost |
| Migrations out of sync | Diverged database | `uv run alembic current`; reset with `downgrade base && upgrade head` (destroys data) |
| Frontend cannot reach the backend | CORS or wrong URL | Check `CORS_ORIGINS`; set `NEXT_PUBLIC_API_URL` and restart the dev server |
| New Relic shows no data | Disabled or no key | See [monitoring](../operations/monitoring.md#35-troubleshooting) |

## 9. Notes

- **Never `make clean` on a machine with data you want** — it removes volumes.
- **`make reset-db` is destructive** and does not touch the storage volume, so file/row references
  will dangle afterwards.
- **The `.env` file is gitignored.** Only `.env.example` and the per-environment examples are tracked.

# Local Development Guide — Indic Book Metadata Extractor

Complete guide for setting up and running the Indic Book Metadata Extractor on your local machine. Covers **Docker Compose** (fastest) and **native installation** (best for active development) across **Windows (WSL2)**, **macOS**, and **Linux**.

---

## Table of Contents

1. [Overview](#overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Option A — Docker Compose Setup](#option-a--docker-compose-setup-recommended)
4. [Option B — Native Local Development](#option-b--native-local-development)
5. [Running Tests](#running-tests)
6. [Common Development Tasks](#common-development-tasks)
7. [Port Reference](#port-reference)
8. [Troubleshooting](#troubleshooting)
9. [Architecture Quick Reference](#architecture-quick-reference)

---

## Overview

The Indic Book Metadata Extractor is a full-stack web application that extracts bibliographic metadata from scanned Indic language book PDFs. It combines OCR (Tesseract) with LLM-based extraction (Airavata 7B via Ollama) to identify 52 metadata fields through a guided 7-step workflow:

1. **Upload** — Drag-and-drop PDF with language selection (Telugu/Hindi)
2. **Page Selection** — Choose pages for processing via thumbnail grid
3. **Preprocessing** — Tune image settings (grayscale, brightness, contrast, binarization, deskew)
4. **OCR Review** — Side-by-side view with bounding box overlay and text correction
5. **LLM Configuration** — Select model, tune parameters, run batched extraction
6. **Metadata Review** — Review and edit 52 extracted bibliographic fields
7. **Library** — Browse, search, and filter all processed books

The stack consists of **10+ services**: PostgreSQL (pgvector), Redis, Ollama, FastAPI backend, Celery worker, Next.js frontend, Flower (Celery monitoring), Wikibase (structured data store), MariaDB, Elasticsearch, and OpenRefine (bulk data cleaning).

---

## Hardware Requirements

| Resource | Minimum | Notes |
|----------|---------|-------|
| RAM | 16 GB | LLM inference requires ~8 GB for Airavata 7B |
| Disk | 10 GB | Docker images + Ollama model weights (~4 GB) |
| CPU | Multi-core | CPU-only inference takes 10–20 min/book; GPU speeds this up |

---

## Option A — Docker Compose Setup (Recommended)

The fastest way to get the entire stack running. All 7 services are orchestrated via Docker Compose.

### Step 1: Install Docker Desktop

| Platform | Instructions |
|----------|-------------|
| **Windows** | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) with **WSL 2 backend** enabled. Ensure WSL 2 is installed: `wsl --install` in an elevated PowerShell, then restart. |
| **macOS** | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for Mac (Intel or Apple Silicon). |
| **Linux** | Install [Docker Engine](https://docs.docker.com/engine/install/) and [Docker Compose](https://docs.docker.com/compose/install/) via your package manager. |

Verify installation:

```bash
docker --version
docker compose version
```

### Step 2: Clone the Repository

```bash
git clone <repo-url>
cd Indic-Book-Metadata-Extractor
```

### Step 3: Configure Environment

```bash
cp .env.example .env
```

The default `.env` values are configured for Docker Compose and work out of the box. No edits required.

### Step 4: Start All Services

```bash
make up
```

This starts all Docker containers: `postgres`, `redis`, `ollama`, `backend`, `worker`, `frontend`, `flower`, `wikibase`, `mysql`, `elasticsearch`, and `openrefine`.

### Step 5: Wait for Services to Be Healthy

```bash
make status
```

On the **first run**, the Ollama container will automatically download the Airavata 7B model (~4 GB). This takes 1–3 minutes depending on your connection. All services should show `healthy` or `running`.

You can watch progress with:

```bash
make logs
```

### Step 6: Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API docs (Swagger) | http://localhost:8000/docs |
| Flower (Celery monitoring) | http://localhost:5555 |

### Useful Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services (detached) |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make build` | Build all Docker images |
| `make rebuild` | Rebuild images (no cache) and restart |
| `make status` | Show status of all services |
| `make logs` | Tail logs for all services |
| `make logs-backend` | Tail backend logs only |
| `make logs-worker` | Tail worker logs only |
| `make migrate` | Run database migrations |
| `make reset-db` | Reset database (destroys all data) |
| `make download-model` | Re-download Airavata model |
| `make test-e2e` | Run E2E smoke test |
| `make shell-backend` | Open a shell in the backend container |
| `make clean` | Remove containers, volumes, and local images |

---

## Option B — Native Local Development

Run each service directly on your machine for hot-reloading and faster iteration. Best for active development.

### Step 1: Install System Dependencies

Choose your platform below.

#### Windows (via WSL 2)

All commands run inside a WSL 2 Ubuntu terminal.

```bash
# Ensure WSL 2 and Ubuntu are installed
# Run in elevated PowerShell: wsl --install

# Inside WSL 2 Ubuntu:

# Update packages
sudo apt update && sudo apt upgrade -y

# PostgreSQL 16
sudo apt install -y postgresql-16 postgresql-server-dev-16

# Redis
sudo apt install -y redis-server

# Tesseract OCR with Indic language packs
sudo apt install -y tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin tesseract-ocr-eng

# Ollama
curl -fsSL https://ollama.com/install.sh | sh

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Node.js 20 (via nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20

# pgvector extension
sudo apt install -y postgresql-16-pgvector
# If not available via apt, build from source:
# git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
# cd pgvector && make && sudo make install
```

#### macOS

```bash
# Install Homebrew if not already installed: https://brew.sh

# PostgreSQL 16 + pgvector
brew install postgresql@16
brew install pgvector

# Redis
brew install redis

# Tesseract with all language packs
brew install tesseract tesseract-lang

# Ollama
brew install ollama

# uv
brew install uv

# Node.js 20
brew install node@20
```

#### Linux (Ubuntu/Debian)

```bash
# PostgreSQL 16
sudo apt install -y postgresql-16 postgresql-server-dev-16

# pgvector extension
sudo apt install -y postgresql-16-pgvector

# Redis
sudo apt install -y redis-server

# Tesseract OCR with Indic language packs
sudo apt install -y tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin tesseract-ocr-eng

# Ollama
curl -fsSL https://ollama.com/install.sh | sh

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Node.js 20 (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### Step 2: Set Up PostgreSQL

```bash
# Start PostgreSQL service
# Linux/WSL:
sudo service postgresql start
# macOS:
brew services start postgresql@16

# Create the database
createdb indic_books

# Enable required extensions
psql -d indic_books -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d indic_books -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Verify
psql -d indic_books -c "\dx"
```

### Step 3: Set Up Redis

```bash
# Start Redis
# Linux/WSL:
sudo service redis-server start
# macOS:
brew services start redis

# Verify
redis-cli ping
# Expected output: PONG
```

### Step 4: Set Up Ollama

```bash
# Start the Ollama server (run in background or separate terminal)
ollama serve &

# Pull the Airavata 7B model (~4 GB download)
ollama pull airavata

# Verify the model is available
ollama list
# Should show "airavata" in the list
```

### Step 5: Set Up the Backend

Open a terminal in the project root:

```bash
cd backend

# Install Python dependencies
uv sync

# Configure environment
cp ../.env.example .env
```

Edit `backend/.env` to point to **localhost** services (replace the Docker service names):

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books
REDIS_URL=redis://localhost:6379/0
OLLAMA_URL=http://localhost:11434
STORAGE_PATH=./storage
```

Then run migrations and start the server:

```bash
# Create storage directories
mkdir -p storage/uploads storage/thumbnails storage/pages storage/processed

# Run database migrations
uv run alembic upgrade head

# Start the FastAPI server (with auto-reload)
uv run uvicorn app.main:app --reload --port 8000
```

In a **separate terminal**, start the Celery worker:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

### Step 6: Set Up the Frontend

Open another terminal:

```bash
cd frontend

# Install Node.js dependencies
npm install

# (Optional) Create .env.local if your API is on a non-default port
# echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start the development server
npm run dev
```

### Step 7: Verify Everything Works

Run these checks in order:

```bash
# 1. Backend health check
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 2. Open the frontend
# Navigate to http://localhost:3000 in your browser

# 3. Check Swagger API docs
# Navigate to http://localhost:8000/docs in your browser

# 4. Verify Tesseract has Indic language packs
tesseract --list-langs
# Should include: tel, hin, eng

# 5. Verify Ollama model is loaded
curl http://localhost:11434/api/tags
# Should list "airavata"
```

---

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest tests/ -v

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests
uv run pytest tests/integration/ -v

# Run a specific test file
uv run pytest tests/unit/test_ocr_service.py -v

# Run with coverage report
uv run pytest tests/ -v --cov=app --cov-report=html
# Open htmlcov/index.html in a browser for detailed coverage

# Run with coverage (terminal summary)
uv run pytest tests/ -v --cov=app
```

**Notes:**
- Tests use SQLite in-memory with JSONB patched to JSON (no PostgreSQL needed).
- Celery tasks are mocked in tests.
- 1 test (`test_get_filter_options`) is skipped because it requires PostgreSQL's JSONB `.astext` operator. Run against the Docker stack for full validation.

### Frontend Tests

```bash
cd frontend

# Run unit/component tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests (requires the full stack running)
npm run test:e2e

# Run E2E tests with interactive UI
npm run test:e2e:ui
```

### E2E Smoke Test (Docker)

```bash
make test-e2e PDF=path/to/test.pdf
```

---

## Common Development Tasks

### Database Migrations

```bash
# Docker
make migrate

# Native
cd backend
uv run alembic upgrade head
```

### Reset the Database

```bash
# Docker (destroys all data)
make reset-db

# Native
cd backend
uv run alembic downgrade base
uv run alembic upgrade head
```

### Download / Re-download the LLM Model

```bash
# Docker
make download-model

# Native
ollama pull airavata
```

### View Logs

```bash
# Docker — all services
make logs

# Docker — backend only
make logs-backend

# Docker — worker only
make logs-worker

# Native — check terminal where uvicorn or celery worker is running
```

### Lint and Format

```bash
# Backend linting
cd backend
uv run ruff check .

# Backend formatting
cd backend
uv run black .

# Frontend linting
cd frontend
npm run lint
```

### Open a Shell in the Backend Container (Docker)

```bash
make shell-backend
```

### Scale Celery Workers (Docker)

```bash
docker compose up -d --scale worker=3
```

---

## Port Reference

| Service | Port | URL / Connection |
|---------|------|------------------|
| Next.js Frontend | 3000 | http://localhost:3000 |
| FastAPI Backend | 8000 | http://localhost:8000 (API docs at `/docs`) |
| PostgreSQL | 5432 | `postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books` |
| Redis | 6379 | `redis://localhost:6379/0` |
| Ollama | 11434 | http://localhost:11434 |
| Flower | 5555 | http://localhost:5555 |
| Wikibase | 8181 | http://localhost:8181 (MediaWiki + Wikibase extension) |
| OpenRefine | 3333 | http://localhost:3333 (bulk data cleaning GUI) |
| MySQL (MariaDB) | (internal) | Wikibase database — not exposed to host |
| Elasticsearch | (internal) | Wikibase search index — not exposed to host |

---

## Troubleshooting

### Port Already in Use

Find and stop the process using the port:

```bash
# Linux/macOS/WSL
lsof -i :<PORT>
kill -9 <PID>

# Alternative
fuser -k <PORT>/tcp
```

```powershell
# Windows (PowerShell, outside WSL)
netstat -ano | findstr :<PORT>
taskkill /PID <PID> /F
```

### pgvector Extension Missing

The PostgreSQL `vector` extension is required. Install it per platform:

| Platform | Command |
|----------|---------|
| Ubuntu/Debian | `sudo apt install postgresql-16-pgvector` |
| macOS | `brew install pgvector` |
| Docker | Already included in `pgvector/pgvector:pg16` image |

If building from source:

```bash
git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

Then enable in the database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Ollama Model Not Found

If the Airavata model is missing (errors about model not found):

```bash
ollama pull airavata
```

Verify it's available:

```bash
ollama list
```

On **first run** via Docker, the Ollama container auto-pulls the model. This takes 1–3 minutes. Check progress with `make logs`.

### Tesseract Language Packs Missing

Verify installed languages:

```bash
tesseract --list-langs
```

If `tel` or `hin` are missing:

| Platform | Command |
|----------|---------|
| Ubuntu/Debian/WSL | `sudo apt install tesseract-ocr-tel tesseract-ocr-hin` |
| macOS | `brew install tesseract-lang` |

### Celery Worker Cannot Connect to Redis

```
Error: Cannot connect to redis://localhost:6379/0
```

1. Verify Redis is running: `redis-cli ping` → should return `PONG`
2. Start Redis if not running:
   - Linux/WSL: `sudo service redis-server start`
   - macOS: `brew services start redis`
3. Check the `REDIS_URL` in your `.env` file

### Database Migration Errors

If migrations fail or are out of sync:

```bash
# Check current migration state
cd backend
uv run alembic current

# Reset to clean state (destroys data)
uv run alembic downgrade base
uv run alembic upgrade head
```

### Frontend Cannot Connect to Backend

1. Verify the backend is running: `curl http://localhost:8000/health`
2. Check CORS — the backend allows `http://localhost:3000` by default (configured in `backend/app/main.py`)
3. If using a custom API URL, create `frontend/.env.local`:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
4. Restart the frontend dev server after changing environment variables

### First Run Is Slow

On first startup (Docker or native), Ollama downloads the Airavata 7B model (~4 GB). This is a one-time operation. The model is cached:
- **Docker**: in the `ollama_data` Docker volume
- **Native**: in `~/.ollama/models`

Subsequent starts are fast.

### New Relic — No Data in Dashboard

| Cause | Fix |
|-------|-----|
| `NEW_RELIC_ENABLED=false` | Set `NEW_RELIC_ENABLED=true` in `.env` |
| Missing license key | Set `NEW_RELIC_LICENSE_KEY` in `.env` (get from [one.newrelic.com](https://one.newrelic.com)) |
| Infra agent crash loop | Ensure `/var/run/docker.sock` is mounted — check `docker compose logs newrelic-infra` |
| Browser agent not injecting | Set `NEW_RELIC_ENABLED=true` and `NEW_RELIC_LICENSE_KEY` in `.env`, restart frontend |

For local development, New Relic is **disabled by default** to avoid sending test data. Set `NEW_RELIC_ENVIRONMENT=local` to use a separate "dev" application in NR dashboard. See [monitoring.md](monitoring.md) for the full setup.

### SQLAlchemy / asyncpg Connection Errors

```
sqlalchemy.exc.InterfaceError: cannot connect to server
```

1. Verify PostgreSQL is running: `pg_isready -U postgres`
2. Check `DATABASE_URL` in `.env` — ensure it points to `localhost` (not `postgres` container name) for native development
3. Verify the `indic_books` database exists: `psql -l | grep indic_books`

---

## Architecture Quick Reference

```
┌─────────────────────────────────────────────────┐
│              Next.js Frontend (:3000)           │
│     Upload → Page Select → Preprocessing →      │
│     OCR Review → LLM Config → Metadata Review   │
│     Bulk Operations (OpenRefine + Wikibase)     │
└──────────────────────┬──────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────┐
│             FastAPI Backend (:8000)             │
│     File handling, Job management, API          │
└──────┬──────────────────────────────┬───────────┘
       │                              │
┌──────▼──────┐              ┌────────▼─────────┐
│ Celery +    │              │  Ollama (:11434) │
│ Redis Queue │              │  Airavata 7B LLM │
└──────┬──────┘              └──────────────────┘
       │
┌──────▼───────────────────────────────────────────┐
│          PostgreSQL + pgvector (:5432)           │
│   Books, Pages, OCR Text, Metadata, Jobs         │
└──────────────────────────────────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│  OpenRefine (:3333) │────→│  Wikibase (:8181)    │
│  Bulk data cleaning │     │  MediaWiki + WB ext  │
│  CSV → reconcile    │     │  MariaDB + Elastic   │
└─────────────────────┘     └──────────────────────┘
```

### Service Descriptions

| Service | Role |
|---------|------|
| **Frontend** (Next.js) | Web UI with 7-step guided workflow, React Query for server state, Zustand for client state |
| **Backend** (FastAPI) | REST API, file upload handling, job dispatch, database queries |
| **Worker** (Celery) | Background processing — OCR pipeline (Tesseract + OpenCV) and LLM extraction (Ollama + Instructor) |
| **PostgreSQL** | Primary database with pgvector (future semantic search) and pg_trgm (fuzzy text search) |
| **Redis** | Celery message broker and result backend |
| **Ollama** | Local LLM inference server running Airavata 7B for structured metadata extraction |
| **Flower** | Web dashboard for monitoring Celery task queues and worker status |
| **Wikibase** | Structured data store — MediaWiki + Wikibase extension bundled in a single Docker image (`wikibase/wikibase:mw1.44.0`). Stores bibliographic metadata as linked entities. Backed by MariaDB and Elasticsearch. See [bulk-operations.md](bulk-operations.md) |
| **OpenRefine** | Web-based bulk data cleaning tool. Export metadata from the backend, clean/normalise it, reconcile against Wikibase, then upload via QuickStatements. See [bulk-operations.md](bulk-operations.md) |
| **New Relic** | APM + Browser + Infrastructure monitoring (SaaS). See [monitoring.md](monitoring.md) |

### Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Task Queue | Celery 5, Redis 7 |
| PDF Processing | PyMuPDF |
| Image Preprocessing | OpenCV, Pillow |
| OCR Engine | Tesseract 5+ (with Indic language packs) |
| LLM Inference | Ollama, Instructor (structured output) |
| Database | PostgreSQL 16, pgvector, pg_trgm |
| Search | pg_trgm (server) + Fuse.js (client) |
| Structured Data | Wikibase (MediaWiki + Wikibase extension), MariaDB, Elasticsearch |
| Bulk Operations | OpenRefine (data cleaning), QuickStatements (Wikibase upload) |
| Monitoring | New Relic (APM + Browser + Infrastructure), Flower |

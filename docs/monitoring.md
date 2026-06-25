# Monitoring — New Relic APM Setup

Comprehensive guide to the New Relic monitoring setup in this project. Covers the 3-agent architecture, environment configuration, what each agent collects, and how to access telemetry data.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [The 3 New Relic Agents](#the-3-new-relic-agents)
3. [Environment Variables](#environment-variables)
4. [Docker Compose Configuration](#docker-compose-configuration)
5. [What Gets Tracked](#what-gets-tracked)
6. [Local Development](#local-development)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

This project uses **New Relic Cloud (SaaS)** for observability. There are **no self-hosted New Relic components** — all agents send telemetry data to New Relic's cloud endpoints (`collector.newrelic.com`, `bam.nr-data.net`).

Four complementary agents cover the full stack:

```
┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────────────┐
│    APM Agent          │  │    Browser Agent       │  │    Infra Agent        │
│    (Python)           │  │    (JS snippet in HTML)│  │    (Docker sidecar)   │
│                       │  │                        │  │                       │
│    → App performance  │  │    → Page loads, AJAX  │  │    → Host/container   │
│    → DB queries       │  │    → JS errors         │  │    → CPU/mem/disk     │
│    → External calls   │  │    → Session traces    │  │    → Docker events    │
└──────────┬────────────┘  └──────────┬─────────────┘  └──────────┬────────────┘
           │                          │                           │
           └──────────────────────────┼───────────────────────────┘
                                      ▼
                          New Relic Cloud (SaaS)
                          One dashboard, unified view
```

Additionally, the **Node.js APM agent** runs in the Next.js server process to provide server-side tracing and inject the browser snippet.

---

## The 3 New Relic Agents

### 1. APM Agent (Application Performance Monitoring)

#### Backend (Python)

Lives **inside the FastAPI application**. Instruments HTTP requests, database queries, external API calls, and Celery background tasks.

| Service | Instrumentation | Key Details |
|---------|----------------|-------------|
| **FastAPI backend** | `newrelic` Python agent via `newrelic-admin run-program` | Auto-instruments FastAPI routes, SQLAlchemy queries, HTTP client calls, Redis operations. Initialized in `backend/app/main.py`. |
| **Celery workers** | `newrelic` Python agent via `newrelic-admin run-program` | Instruments OCR and LLM extraction tasks. Worker init hook in `backend/app/tasks/celery_app.py` ensures agent is loaded. |

**Config file:** `backend/newrelic.ini` — controls transaction tracing, error collection, distributed tracing, and log forwarding.

#### Frontend (Node.js)

The `newrelic` Node.js agent runs in the Next.js server process in **hybrid OTel mode**. It provides:
- Server-side APM tracing (SSR performance, API routes)
- Browser monitoring snippet injection via `getBrowserTimingHeader()`

**Key files:**

| File | Purpose |
|------|---------|
| `frontend/newrelic.cjs` | Agent configuration (hybrid OTel mode, logging to stdout) |
| `frontend/src/instrumentation.ts` | Next.js instrumentation hook — loads the agent on server startup |
| `frontend/src/lib/agent.ts` | Agent loader with collector connection waiting |
| `frontend/src/app/layout.tsx` | Injects browser snippet (server-side with fallback) |

### 2. Browser Agent (Real User Monitoring — RUM)

The browser monitoring snippet is injected using a **hybrid approach**:

1. **Primary:** Server-side injection via the Node.js APM agent's `getBrowserTimingHeader()` — this generates the browser JS dynamically with the correct transaction context.
2. **Fallback:** If the APM agent hasn't connected to the collector yet (returns `<!-- NREUM: (4) -->`), a static snippet is injected from `NEXT_PUBLIC_*` env vars.

This fallback was added because the APM agent's `getBrowserTimingHeader()` may return a placeholder if called before the agent has received the browser monitoring JavaScript payload from the collector.

| Feature | What It Captures |
|---------|-----------------|
| **Page load timing** | DNS, TCP, TLS, TTFB, DOM ready, full page load |
| **AJAX calls** | XHR/fetch request timing and errors to your API |
| **JavaScript errors** | Uncaught exceptions with stack traces and source line |
| **Session traces** | Full interaction waterfall for debugging slow sessions |
| **Core Web Vitals** | LCP, FID/INP, CLS scores |

**How it's enabled:**
The `newrelic` Node.js agent loads on the server via `src/instrumentation.ts` when `NEW_RELIC_ENABLED=true`. The root layout (`src/app/layout.tsx`) calls `getBrowserTimingHeader()` first. If that returns a placeholder, it falls back to building the snippet from `NEXT_PUBLIC_NEW_RELIC_*` env vars.

### 3. Infrastructure Agent (Docker Sidecar)

Runs as a **separate Docker container** (`newrelic/newrelic-infra:latest`) in `docker-compose.yml`. It is **not** a self-hosted New Relic instance — it's a lightweight metrics collector that reports to New Relic's cloud.

| Capability | What It Collects |
|-----------|-----------------|
| **Container metrics** | CPU usage, memory usage, network I/O per running container |
| **Docker events** | Container starts, stops, restarts, health check failures |
| **Host metrics** | Disk usage, system load, process counts, uptime |
| **Log forwarding** (optional) | Forward container stdout/stderr to New Relic Logs |

**Why a separate container?**

The APM agent and browser agent only see **their own process**. Neither can answer:

- "Is the **Postgres** container running hot on CPU?"
- "Did the **Redis** container restart 3 times in the last hour?"
- "Is the **disk** on this host about to fill up?"

The infra agent fills that gap by monitoring **everything on the host** from a privileged sidecar position (`pid: host`, `cap_add: SYS_PTRACE`, `/proc` and `/var/run/docker.sock` mounted).

---

## Environment Variables

All New Relic configuration is managed via environment variables in `.env`. Copy from `.env.example` and set your license key.

### Shared (in root `.env`)

| Variable | Description | Default | Wired to |
|----------|-------------|---------|----------|
| `NEW_RELIC_ENABLED` | Master toggle for all agents | `false` | backend, worker, frontend |
| `NEW_RELIC_LICENSE_KEY` | New Relic ingest license key | — | backend, worker, infra |
| `NEW_RELIC_APP_NAME` | Application name shown in NR dashboard | `Indic Book Metadata Extractor` | backend, worker, frontend |
| `NEW_RELIC_ENVIRONMENT` | Environment label (`production`, `staging`, `local`) | `production` | backend, worker |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | Enable cross-service trace correlation | `true` | backend, worker |
| `NEW_RELIC_LOG` | Agent log level (`off`, `error`, `warning`, `info`, `debug`) | `error` | backend, worker, frontend |
| `NEW_RELIC_CONFIG_FILE` | Path to `newrelic.ini` | `newrelic.ini` | backend, worker |
| `NEW_RELIC_MONITOR_MODE` | Enable/disable the APM agent process | `true` | backend, worker |
| `NEW_RELIC_DEVELOPER_MODE` | Reduced overhead for dev (no data sent) | `false` | backend, worker |

### Frontend Browser Agent (fallback snippet)

These vars are used to build a static browser monitoring snippet when the APM agent's `getBrowserTimingHeader()` returns a placeholder. They're passed as Docker build args so Next.js bakes them into the server bundle.

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY` | Browser app license key (from NR Browser app settings) | — |
| `NEXT_PUBLIC_NEW_RELIC_APP_ID` | Browser application ID (from NR Browser app settings) | — |
| `NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID` | New Relic account ID | — |

> **Note:** These are `NEXT_PUBLIC_*` vars but they're only used server-side in `layout.tsx` (not bundled for the client). The "NEXT_PUBLIC_" prefix is a Next.js convention for build-time env vars.

### Infrastructure Agent (in root `.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NRIA_LICENSE_KEY` | Infra agent license key (falls back to `NEW_RELIC_LICENSE_KEY`) | — |
| `NRIA_DISPLAY_NAME` | Host display name in NR dashboard | `indic-book-extractor-host` |
| `NRIA_LOG` | Agent log level | `info` |

---

## Docker Compose Configuration

New Relic env vars are wired to four services in `docker-compose.yml`:

### Backend (FastAPI)

```yaml
backend:
  environment:
    - NEW_RELIC_ENABLED=${NEW_RELIC_ENABLED:-false}
    - NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}
    - NEW_RELIC_APP_NAME=${NEW_RELIC_APP_NAME:-Indic Book Metadata Extractor}
    - NEW_RELIC_ENVIRONMENT=${NEW_RELIC_ENVIRONMENT:-production}
    - NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=${NEW_RELIC_DISTRIBUTED_TRACING_ENABLED:-true}
    - NEW_RELIC_LOG=${NEW_RELIC_LOG:-error}
    - NEW_RELIC_CONFIG_FILE=/app/newrelic.ini
    - NEW_RELIC_MONITOR_MODE=${NEW_RELIC_MONITOR_MODE:-true}
    - NEW_RELIC_DEVELOPER_MODE=${NEW_RELIC_DEVELOPER_MODE:-false}
```

### Worker (Celery)

Same env vars as backend. The worker command uses `newrelic-admin run-program` to bootstrap the agent:

```yaml
worker:
  command: ["uv", "run", "newrelic-admin", "run-program", "celery", ...]
  environment:
    # Same NEW_RELIC_* vars as backend
```

### Frontend (Next.js)

The frontend receives both APM agent vars (for server-side tracing) and browser agent vars (for the fallback snippet):

```yaml
frontend:
  build:
    args:
      # Browser agent fallback (baked into server bundle)
      - NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY=${NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY:-}
      - NEXT_PUBLIC_NEW_RELIC_APP_ID=${NEXT_PUBLIC_NEW_RELIC_APP_ID:-}
      - NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID=${NEXT_PUBLIC_NEW_RELIC_ACCOUNT_ID:-}
      # APM agent config (build-time)
      - NEW_RELIC_ENABLED=${NEW_RELIC_ENABLED:-false}
      - NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY:-}
      - NEW_RELIC_APP_NAME=${NEW_RELIC_APP_NAME:-Indic Book Metadata Extractor}
  environment:
    # APM agent config (runtime)
    - NEW_RELIC_ENABLED=${NEW_RELIC_ENABLED:-false}
    - NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY:-}
    - NEW_RELIC_APP_NAME=${NEW_RELIC_APP_NAME:-Indic Book Metadata Extractor}
```

The `Dockerfile.frontend` accepts all vars as `ARG` and sets them as `ENV` before `npm run build`. It also copies `newrelic.cjs` (agent config) into the standalone output and creates the log file with proper permissions.

### Infrastructure Agent (Sidecar)

```yaml
newrelic-infra:
  image: newrelic/newrelic-infra:latest
  container_name: newrelic-infra
  restart: unless-stopped
  privileged: true
  pid: host
  network_mode: host
  cap_add:
    - SYS_PTRACE
  volumes:
    - "/:/host:ro"
    - "/var/run/docker.sock:/var/run/docker.sock:ro"
    - "/proc:/host/proc:ro"
    - "/sys:/host/sys:ro"
  environment:
    - NRIA_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}
    - NRIA_DISPLAY_NAME=${NRIA_DISPLAY_NAME:-indic-book-extractor-host}
    - NRIA_LOG=${NRIA_LOG:-info}
```

**Key configuration choices:**

| Setting | Why |
|---------|-----|
| `privileged: true` | Required for host-level metrics collection |
| `pid: host` | See all host processes, not just the container's own PID namespace |
| `SYS_PTRACE` capability | Allow process inspection for CPU/memory metrics |
| `/ :/host:ro` | Mount host filesystem read-only for disk metrics |
| `/var/run/docker.sock` | Query Docker daemon for container stats and events |
| `network_mode: host` | Avoid NAT overhead; infra agent talks directly to host network |

---

## What Gets Tracked

### Across All Services

| Signal | FastAPI | Celery Worker | Next.js (server) | Next.js (browser) | Postgres | Redis | Ollama |
|--------|:-------:|:------------:|:----------------:|:-----------------:|:--------:|:-----:|:------:|
| APM traces | ✅ | ✅ | ✅ | — | via APM | via APM | via APM |
| Browser RUM | — | — | — | ✅ | — | — | — |
| Container metrics | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Custom attributes | ✅ | ✅ | ✅ | — | — | — | — |
| Error tracking | ✅ | ✅ | ✅ | ✅ | via APM | via APM | via APM |

### Custom Business Events

Custom events are emitted via helpers in `backend/app/services/metrics.py`. Each function safely no-ops if the `newrelic` package is not installed.

| Event Type | Attributes | Emitted From |
|------------|-----------|--------------|
| `BookUpload` | `book_id`, `language`, `total_pages` | `metrics.record_book_upload()` |
| `OCRComplete` | `book_id`, `avg_confidence`, `pages_processed`, `duration_sec` | `metrics.record_ocr_completion()` |
| `LLMExtraction` | `book_id`, `model`, `batches`, `errors`, `duration_sec` | `metrics.record_llm_extraction()` |

---

## Local Development

For local development, New Relic is **disabled by default** to avoid sending test data to your production dashboard.

### Quick disable/enable

```bash
# .env
NEW_RELIC_ENABLED=false    # Disable all agents
NEW_RELIC_ENABLED=true     # Enable all agents
```

### Development-only config

For testing the NR integration locally without polluting production data:

```bash
# .env (local)
NEW_RELIC_ENABLED=true
NEW_RELIC_ENVIRONMENT=local
NEW_RELIC_APP_NAME=Indic Book Metadata Extractor (Local)
NRIA_DISPLAY_NAME=local-dev-machine
```

Create a separate "dev" application in your New Relic dashboard to keep local telemetry isolated.

### Verifying the integration

```bash
# Check APM agent is loaded (FastAPI)
docker compose logs backend | grep -i "newrelic"

# Check Node.js APM agent is connected (Next.js)
docker compose logs frontend | grep -i "newrelic"

# Check infra agent is running
docker compose logs newrelic-infra

# Check browser agent snippet is injected
curl -s http://localhost:3000 | grep -o 'NREUM.info={[^}]*}'

# Generate traffic to verify APM data
curl http://localhost:8000/health
curl http://localhost:3000
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No data in NR dashboard | `NEW_RELIC_ENABLED=false` or missing license key | Set `NEW_RELIC_ENABLED=true` and verify `NEW_RELIC_LICENSE_KEY` in `.env` |
| Infra agent crash loop | Docker socket not mounted | Ensure `/var/run/docker.sock` is mounted read-only |
| Browser snippet shows `<!-- NREUM: (4) -->` | APM agent hasn't received browser JS from collector | This is expected on first load. The fallback snippet from `NEXT_PUBLIC_*` vars should kick in. If not, verify those vars are set. |
| `Cannot find module 'meriyah'` in frontend | Missing dependency in standalone build | Add `meriyah` to `outputFileTracingIncludes` and `serverExternalPackages` in `next.config.ts` |
| `dotenv` error in frontend | `newrelic.cjs` tries to load `dotenv` | Remove `require("dotenv").config()` from `newrelic.cjs` — env vars are injected by Docker Compose |
| `EACCES: permission denied` for log file | Next.js user can't write to log file | Add `RUN touch /app/newrelic_agent.log && chown nextjs:nodejs /app/newrelic_agent.log` to Dockerfile, or set `filepath: "stdout"` in `newrelic.cjs` |
| Missing Celery task traces | Worker not instrumented | Ensure `newrelic-admin run-program` prefix is in the Celery start command |
| High overhead / latency | Running with production config in dev | Set `NEW_RELIC_ENVIRONMENT=local` and `NEW_RELIC_DEVELOPER_MODE=true` |
| Distributed traces not linking | DT disabled on one agent | Ensure `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true` on **all** services |
| No container metrics | Infra agent can't access Docker socket | Check `docker compose logs newrelic-infra` for permission errors |
| APM agent double-wrapping | Both `newrelic-admin` and `main.py` initialize the agent | The `main.py` code is idempotent — safe to call twice. If you see duplicate traces, remove the `initialize()` call from `main.py` |

---

## Further Reading

- [New Relic APM Python Agent Docs](https://docs.newrelic.com/docs/apm/agents/python-agent/)
- [New Relic Node.js Agent — Next.js](https://github.com/newrelic/newrelic-node-examples/tree/main/nextjs/nextjs-app-router)
- [New Relic Infrastructure Agent](https://docs.newrelic.com/docs/infrastructure/)
- [Distributed Tracing](https://docs.newrelic.com/docs/distributed-tracing/)
- [Browser Monitoring](https://docs.newrelic.com/docs/browser/new-relic-browser/getting-started/introduction-new-relic-browser/)

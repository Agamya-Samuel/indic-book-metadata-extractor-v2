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

This project uses **New Relic Cloud (SaaS)** for observability. There are **no self-hosted New Relic components** — all agents send telemetry data to New Relic's cloud endpoints (`otlp.nr-data.net`, `aws-api.newrelic.com`).

Three complementary agents cover the full stack:

```
┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────────────┐
│    APM Agent          │  │    Browser Agent       │  │    Infra Agent        │
│    (in Python/JS code)│  │    (JS snippet in HTML)│  │    (Docker sidecar)   │
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

---

## The 3 New Relic Agents

### 1. APM Agent (Application Performance Monitoring)

Lives **inside the application code** (Python and Next.js). Instruments HTTP requests, database queries, external API calls, and Celery background tasks.

| Service | Instrumentation | Key Details |
|---------|----------------|-------------|
| **FastAPI backend** | `newrelic` Python agent via `NEW_RELIC_CONFIG_FILE` env var | Auto-instruments FastAPI routes, SQLAlchemy queries, HTTP client calls, Redis operations |
| **Celery workers** | `newrelic` Python agent with custom background task naming | Instruments OCR and LLM extraction tasks; uses `@newrelic.agent.background_task()` decorator |
| **Next.js frontend** | `@newrelic/next` package + custom `newrelic.ts` config | Captures server-side rendering performance, API route timing, and browser-side page loads |

**What it collects:**
- Request/response times per endpoint
- Database query durations and slow query detection
- External HTTP call latency (Ollama, S3, etc.)
- Error rates and stack traces
- Custom attributes (`book_id`, `language`, `extraction_model`, etc.)
- Celery task execution times and success/failure rates

### 2. Browser Agent (Real User Monitoring — RUM)

Injected as a **JavaScript snippet** into the HTML `<head>` of every page rendered by Next.js. Tracks real user experience in the browser.

| Feature | What It Captures |
|---------|-----------------|
| **Page load timing** | DNS, TCP, TLS, TTFB, DOM ready, full page load |
| **AJAX calls** | XHR/fetch request timing and errors to your API |
| **JavaScript errors** | Uncaught exceptions with stack traces and source line |
| **Session traces** | Full interaction waterfall for debugging slow sessions |
| **Core Web Vitals** | LCP, FID/INP, CLS scores |

**How it's enabled:**
The `@newrelic/next` package handles browser agent injection. In production, the agent script is automatically prepended to the HTML response. The `newrelic.ts` config at `frontend/src/lib/newrelic.ts` controls feature toggles (AJAX tracking, error collection, distributed tracing).

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

### Shared

| Variable | Description | Example |
|----------|-------------|---------|
| `NEW_RELIC_ENABLED` | Master toggle for all agents | `true` / `false` |
| `NEW_RELIC_LICENSE_KEY` | Your New Relic ingest license key | `eu01xx...` |
| `NEW_RELIC_APP_NAME` | Application name shown in NR dashboard | `indic-book-metadata-extractor` |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | Enable cross-service trace correlation | `true` |
| `NEW_RELIC_LOG` | Agent log level | `stdout` / `stderr` / `error` |

### APM Agent (Python — FastAPI + Celery)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEW_RELIC_CONFIG_FILE` | Path to `newrelic.ini` (auto-generated by the agent) | `newrelic.ini` |
| `NEW_RELIC_ENVIRONMENT` | Environment label (`production`, `staging`, `local`) | `production` |
| `NEW_RELIC_MONITOR_MODE` | Enable/disable the agent process | `true` |
| `NEW_RELIC_DEVELOPER_MODE` | Reduced overhead for dev (no data sent) | `false` |

### APM Agent (Next.js)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEW_RELIC_APP_NAME` | Next.js app name in NR dashboard | `indic-book-metadata-extractor-frontend` |
| `NEW_RELIC_BROWSER_AGENT_ENABLED` | Toggle browser JS agent injection | `true` |
| `NEW_RELIC_BROWSER_AUTO_INSTRUMENT` | Auto-inject browser snippet into HTML | `true` |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | Link browser traces to backend traces | `true` |

### Infrastructure Agent

| Variable | Description | Default |
|----------|-------------|---------|
| `NRIA_LICENSE_KEY` | Infra agent license key (same as `NEW_RELIC_LICENSE_KEY`) | — |
| `NRIA_DISPLAY_NAME` | Host display name in NR dashboard | `indic-book-extractor-host` |
| `NRIA_LOG` | Agent log level | `info` |

---

## Docker Compose Configuration

The `newrelic-infra` service in `docker-compose.yml`:

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
    - NRIA_LOG=${NEW_RELIC_LOG:-info}
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

| Signal | FastAPI | Celery Worker | Next.js | Postgres | Redis | Ollama |
|--------|:-------:|:------------:|:-------:|:--------:|:-----:|:------:|
| APM traces | ✅ | ✅ | ✅ | via APM | via APM | via APM |
| Browser RUM | — | — | ✅ | — | — | — |
| Container metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Custom attributes | ✅ | ✅ | ✅ | — | — | — |
| Error tracking | ✅ | ✅ | ✅ | via APM | via APM | via APM |

### Custom Business Events

The Celery tasks report custom attributes to New Relic for filtering and alerting:

| Event | Attributes | Where |
|-------|-----------|-------|
| OCR extraction started | `book_id`, `page_count`, `language` | `ocr_tasks.py` |
| OCR extraction completed | `book_id`, `pages_processed`, `duration_ms` | `ocr_tasks.py` |
| LLM extraction started | `book_id`, `model`, `field_count` | `llm_tasks.py` |
| LLM extraction completed | `book_id`, `fields_extracted`, `confidence_avg`, `duration_ms` | `llm_tasks.py` |
| PDF upload | `file_size`, `page_count`, `language` | `books.py` |

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
NEW_RELIC_APP_NAME=indic-book-metadata-extractor-local
NRIA_DISPLAY_NAME=local-dev-machine
```

Create a separate "dev" application in your New Relic dashboard to keep local telemetry isolated.

### Verifying the integration

```bash
# Check APM agent is loaded (FastAPI)
docker compose logs backend | grep -i "newrelic"

# Check infra agent is running
docker compose logs newrelic-infra

# Check browser agent is injected
curl -s http://localhost:3000 | grep -i "newrelic"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No data in NR dashboard | `NEW_RELIC_ENABLED=false` or missing license key | Set `NEW_RELIC_ENABLED=true` and verify `NEW_RELIC_LICENSE_KEY` in `.env` |
| Infra agent crash loop | Docker socket not mounted | Ensure `/var/run/docker.sock` is mounted read-only |
| Browser agent not appearing | `NEW_RELIC_BROWSER_AGENT_ENABLED=false` | Set to `true` in `.env` and restart frontend |
| Missing Celery task traces | Worker not instrumented | Ensure `newrelic-admin run-program` prefix is in the Celery start command |
| High overhead / latency | `NEW_RELIC_DEVELOPER_MODE=false` in dev | Set `NEW_RELIC_ENVIRONMENT=local` or `NEW_RELIC_DEVELOPER_MODE=true` |
| Distributed traces not linking | DT disabled on one agent | Ensure `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true` on **all** services |
| No container metrics | Infra agent can't access Docker socket | Check `docker compose logs newrelic-infra` for permission errors |

---

## Further Reading

- [New Relic APM Python Agent Docs](https://docs.newrelic.com/docs/apm/agents/python-agent/)
- [New Relic Next.js Integration](https://docs.newrelic.com/docs/apm/agents/nodejs-agent/getting-started/nextjs/)
- [New Relic Infrastructure Agent](https://docs.newrelic.com/docs/infrastructure/)
- [Distributed Tracing](https://docs.newrelic.com/docs/distributed-tracing/)

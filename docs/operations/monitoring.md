# Monitoring

Three layers: an HTTP health endpoint, New Relic APM/custom events, and admin-facing metrics. Flower
covers Celery specifically.

- Health: `backend/app/main.py` (`/health`)
- Custom events: `backend/app/services/metrics.py`
- System metrics: `backend/app/services/system_metrics_service.py`

---

## 1. Health endpoint

`GET /health` (and `/api/health`) is deliberately unauthenticated so an external monitor can poll it.

```json
{
  "status": "ok",
  "checks": {"postgres": "ok", "redis": "ok", "ollama": "ok"}
}
```

| Condition | Status code | Body |
| --- | --- | --- |
| All checks ok | 200 | `status: "ok"` |
| Any check fails | 503 | `status: "degraded"`, failing check carries `error: …` |

| Check | Method |
| --- | --- |
| `postgres` | `SELECT 1` over the async engine |
| `redis` | `PING` on the shared pool |
| `ollama` | `GET /api/tags` with a 5 s timeout |

`/api/status` is a lighter endpoint for uptime probes.

**What it does not check:** the worker, Tesseract, disk space, or queue depth. A green `/health` means
the API can serve requests — not that books are progressing.

---

## 2. Composable health vs real health

Container healthchecks (Compose) and application health answer different questions:

| Layer | Checks | Consequence of failure |
| --- | --- | --- |
| `postgres` healthcheck | `pg_isready` | `backend` and `worker` will not start |
| `redis` healthcheck | `redis-cli ping` | Same |
| `ollama` healthcheck | `ollama list` | Same; `start_period` is 120 s because of model load |
| `wikibase` healthcheck | `/w/api.php` returns 200 | Optional stack only |
| `/health` | Live dependency reachability | Monitoring/alerting signal |

Because `depends_on: condition: service_healthy` gates startup, a stuck Ollama download blocks the
backend and worker from starting at all. That is the most common "deploy looks dead" cause.

---

## 3. New Relic

New Relic Cloud (SaaS) — there are no self-hosted New Relic components. Four agents cover the stack:

| Agent | Runs in | Collects |
| --- | --- | --- |
| **Python APM** | FastAPI backend and Celery worker | Routes, SQLAlchemy queries, HTTP clients, Redis, Celery tasks |
| **Node APM** | Next.js server process (hybrid OTel mode) | SSR timings, API routes, browser snippet injection |
| **Browser (RUM)** | User's browser | Page loads, AJAX, JS errors, session traces, Core Web Vitals |
| **Infrastructure** | Separate sidecar container | Container CPU/memory/network, Docker events, host disk and load |

Key files:

| File | Purpose |
| --- | --- |
| `backend/newrelic.ini` | Python agent configuration |
| `backend/app/main.py` | Idempotent `initialize()` fallback for local runs |
| `backend/app/tasks/celery_app.py` | `worker_init` hook, safety net when `sitecustomize` is absent |
| `frontend/newrelic.cjs` | Node agent configuration |
| `frontend/src/instrumentation.ts` | Loads the agent on server startup |
| `frontend/src/app/layout.tsx` | Injects the browser snippet, with a static fallback |

**Browser snippet fallback.** `getBrowserTimingHeader()` returns a placeholder
(`<!-- NREUM: (4) -->`) if called before the agent has received the browser payload from the
collector. The root layout detects that and builds a static snippet from `NEXT_PUBLIC_NEW_RELIC_*`
instead. That is why those variables exist despite being used only server-side.

**Do not double-wrap.** Production runs under `newrelic-admin run-program`, which auto-instruments via
`sitecustomize`. Wrapping the ASGI app again in `main.py` produces duplicate traces. `initialize()` is
kept only as an idempotent fallback for local development.

### 3.1 Environment variables

| Variable | Purpose | Default | Services |
| --- | --- | --- | --- |
| `NEW_RELIC_ENABLED` | Master toggle | `false` | backend, worker, frontend |
| `NEW_RELIC_LICENSE_KEY` | Ingest key | — | backend, worker, infra |
| `NEW_RELIC_APP_NAME` | Dashboard name | app name | backend, worker, frontend |
| `NEW_RELIC_ENVIRONMENT` | Environment label | `production` | backend, worker |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | Cross-service traces | `true` | backend, worker |
| `NEW_RELIC_LOG` | Agent log level | `error` | all |
| `NEW_RELIC_CONFIG_FILE` | Path to `newrelic.ini` | `newrelic.ini` | backend, worker |
| `NEW_RELIC_MONITOR_MODE` | Run the APM agent process | `true` | backend, worker |
| `NEW_RELIC_DEVELOPER_MODE` | Low-overhead dev mode | `false` | backend, worker |
| `NEXT_PUBLIC_NEW_RELIC_LICENSE_KEY` / `_APP_ID` / `_ACCOUNT_ID` | Browser fallback snippet | — | frontend **build args** |
| `NRIA_LICENSE_KEY` | Infra agent key (falls back to the shared key) | — | infra |
| `NRIA_DISPLAY_NAME` | Host label | — | infra |
| `NRIA_LOG` | Infra log level | `info` | infra |

### 3.2 Compose wiring

| Service | Wiring |
| --- | --- |
| `backend` | `NEW_RELIC_*` env; `newrelic-admin run-program` in the image command |
| `worker` | Same env; `newrelic-admin run-program celery …` |
| `frontend` | `NEXT_PUBLIC_NEW_RELIC_*` and `NEW_RELIC_*` passed as **build args** (baked at build time) plus runtime env |
| `newrelic-infra` | `privileged: true`, `pid: host`, `network_mode: host`, `SYS_PTRACE`; mounts `/`, `/proc`, `/sys` read-only and `/var/run/docker.sock` |

The infra agent needs those privileges because the APM agents can only see their own process — they
cannot answer "is Postgres hot", "did Redis restart three times", or "is the disk filling".

The infra sidecar exists only in `docker-compose.yml` (dev), under the `monitoring` profile. It is not
part of the production compose.

### 3.3 Custom events

`services/metrics.py` records domain events through `newrelic.agent.record_custom_event`, so they are
queryable in NRQL rather than being log lines:

| Function | Records |
| --- | --- |
| `record_book_upload(...)` | Upload volume/outcome |
| `record_ocr_completion(book_id, avg_confidence, pages_ok, duration)` | OCR run outcome, mean confidence, success count, wall-clock |
| `record_llm_extraction(...)` | Extraction outcome and timing |

These are no-ops when `NEW_RELIC_ENABLED=false`, so local runs are unaffected.

### 3.4 Local development

New Relic is disabled by default locally. To test the integration without polluting production:

```bash
NEW_RELIC_ENABLED=true
NEW_RELIC_ENVIRONMENT=local
NEW_RELIC_APP_NAME=Indic Book Metadata Extractor (Local)
NRIA_DISPLAY_NAME=local-dev-machine
```

Verify each agent:

```bash
docker compose logs backend  | grep -i newrelic     # Python APM
docker compose logs frontend | grep -i newrelic     # Node APM
docker compose logs newrelic-infra                  # infra sidecar
curl -s http://localhost:3000 | grep -o 'NREUM.info={[^}]*}'   # browser snippet
```

### 3.5 Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| No data in the dashboard | Disabled or missing key | `NEW_RELIC_ENABLED=true` and a valid `NEW_RELIC_LICENSE_KEY` |
| Infra agent crash loop | Docker socket not mounted | Mount `/var/run/docker.sock` read-only |
| Snippet is `<!-- NREUM: (4) -->` | Agent had not received browser JS | Expected on first load; the `NEXT_PUBLIC_*` fallback should cover it |
| `Cannot find module 'meriyah'` | Missing from standalone build | Keep it in `outputFileTracingIncludes` and `serverExternalPackages` |
| `dotenv` error in frontend | Agent config loads dotenv | Remove `require("dotenv").config()`; Compose injects env |
| `EACCES` on the log file | Next.js user cannot write it | `chown` the log file, or log to `stdout` |
| No Celery task traces | Worker not instrumented | Ensure the `newrelic-admin run-program` prefix is present |
| Duplicate traces | Agent wrapped twice | Do not wrap the ASGI app when `newrelic-admin` is used |
| Distributed traces not linking | DT off on one service | Enable on **all** services |

---

## 4. Admin system metrics

`GET /api/admin/system` returns a snapshot assembled by `system_metrics_service`:

| Section | Content |
| --- | --- |
| Server | CPU percent and count, memory, swap, disk, storage volume, uptime (via `psutil`) |
| Services | Per-container status |
| Tesseract | Binary presence and version |
| Workers | Registered Celery workers and queue names |
| Overall | Rolled-up status |

The service caches results and serialises refreshes with an async lock, so a dashboard poll does not
hammer the host. If `psutil` is unavailable the server section degrades rather than erroring.

Required in practice: host metrics need `/proc`, so the container must not be stripped of procfs.

---

## 5. Celery visibility

Flower runs on the internal network at `:5555`, protected by `FLOWER_BASIC_AUTH`.

| Useful for | Not for |
| --- | --- |
| Live worker/task inspection | Historical accuracy (results expire in 1 hour) |
| Queue depth | Book-level state (use `jobs`) |
| Revoking a specific task | Long-term alerting |

Because `result_expires=3600`, do not build monitoring on Celery results. Poll `jobs`.

---

## 6. Logs

Structured logging via `core/logging_config.py`.

| Signal | Where |
| --- | --- |
| Unhandled exceptions | `generic_exception_handler` logs full trace, returns a generic body |
| Stale-job reaping | `WARNING Stale-job sweep reaped N job(s)` |
| Task failures | Celery `task_failure` handler |
| OCR line-model fallback | `WARNING Telugu line OCR failed for …; falling back to Tesseract` |
| Script re-routes | `INFO Re-routed … (… share …, N→M chars)` |
| Individual page failures | `ERROR OCR failed for page …` |
| Hybrid tier counts | `INFO Hybrid tier1/tier2 resolved N field(s)` |

The hybrid tier logs are the fastest way to tell "OCR is bad" from "the LLM is bad".

---

## 7. What to alert on

| Alert | Threshold suggestion | Rationale |
| --- | --- | --- |
| `/health` non-200 | 2 consecutive failures | Dependency outage |
| `jobs` stuck `running` | older than `STALE_JOB_MINUTES` (90) | Reaper will clear it, but it means lost work |
| Queue depth growing | sustained > 5 for 30 min | Worker wedged or Ollama degraded |
| Disk usage | > 85% | Storage grows with pages and previews |
| Ollama latency | p95 rising | CPU contention |
| OCR mean confidence | sudden drop | Preprocessing or language regression |
| Hallucination rate | rising in evaluation | Prompt or model regression |

---

## 8. What is not instrumented

1. **No Prometheus/metrics endpoint.** New Relic custom events are the only structured telemetry.
2. **No per-page timing histogram** for OCR.
3. **No alerting definitions in the repository.** Alert policies live in New Relic, not here.
4. **No worker-level health endpoint.**
5. **No cost tracking** for the (optional) hosted model experiments.

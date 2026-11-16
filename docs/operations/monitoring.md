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

## 3. Custom events (New Relic)

`services/metrics.py` records domain events through `newrelic.agent.record_custom_event`, so they are
queryable in NRQL rather than being log lines:

| Function | Records |
| --- | --- |
| `record_book_upload(...)` | Upload volume/outcome |
| `record_ocr_completion(book_id, avg_confidence, pages_ok, duration)` | OCR run outcome, mean confidence, success count, wall-clock |
| `record_llm_extraction(...)` | Extraction outcome and timing |

These are no-ops when `NEW_RELIC_ENABLED=false`, so local runs are unaffected.

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

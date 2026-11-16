# Backend Architecture

The backend is a FastAPI application backed by SQLAlchemy 2.x (async, `asyncpg`) and PostgreSQL, with
Celery for background work. It owns authentication, authorisation, job orchestration, the SSE hub, and
all pipeline stages.

- Entry point: `backend/app/main.py`
- Router root: `backend/app/api/router.py`
- Settings: `backend/app/core/config.py`
- Task app: `backend/app/tasks/celery_app.py`

---

## 1. Module layout

```text
backend/app/
├── main.py                 FastAPI app, middleware, lifespan loops, health, error handlers
├── api/                    HTTP layer — one module per resource
│   ├── router.py           composition + auth dependencies (order matters)
│   ├── deps.py             auth dependencies, pagination, ownership helpers
│   ├── admin.py  auth.py  books.py  bulk.py  dashboard.py  extraction.py
│   ├── health.py  jobs.py  media.py  metadata.py  notifications.py
│   ├── pages.py  sse.py  stages.py
├── core/
│   ├── config.py           Pydantic settings (env-driven)
│   ├── database.py         async engine + session factory
│   ├── security.py         Argon2, JWT, opaque tokens
│   ├── media_tokens.py     signed, scoped, TTL-limited image URLs
│   ├── maintenance_middleware.py
│   ├── errors.py           JobCancelled and cross-module exceptions
│   ├── logging_config.py
│   └── redis.py            shared async Redis pool
├── models/                 SQLAlchemy ORM — see data-model.md
├── schemas/                Pydantic request/response and LLM batch models
├── services/               Business logic, framework-agnostic where possible
│   ├── ocr_service.py  ocr_line_model.py  ocr_postprocess.py  ocr_dictionaries.py
│   ├── preprocessing.py  page_classifier.py  pdf_service.py  storage.py
│   ├── llm_service.py  prompts.py  prompt_profiles.py  extraction_validator.py
│   ├── extractors/         regex_registry, dictionary_registry, hybrid orchestrator
│   ├── stage_manager.py  page_selection.py  batch_routing.py
│   ├── auth_service.py  notification_service.py  email_service.py
│   ├── job_reaper.py  maintenance_service.py  admin_service.py  dashboard_service.py
│   ├── search_service.py  pagination.py  metrics.py  sse_service.py
└── tasks/                  Celery
    ├── celery_app.py       app, routes, signal handlers
    ├── page_tasks.py       render_pages_for_book, apply_preprocessing_bulk
    ├── ocr_tasks.py        preprocess_pages_for_book, run_ocr_for_book
    ├── llm_tasks.py        run_llm_extraction
    ├── pipeline_lock.py    per-book Redis lock (@single_book_task)
    ├── cancellation.py     cancel / supersede checks
    └── async_utils.py      sync→async bridges (run_async, run_async_threadsafe)
```

Layering rule: `api → services → models`. Tasks call services. Services never import from `api`.
`core` knows nothing about either.

---

## 2. Adding an endpoint

1. Put the route in the module that owns the resource under `app/api/`.
2. Declare request/response models in `app/schemas/`.
3. Put logic that is more than trivial CRUD in `app/services/`.
4. If the router is new, mount it in `router.py` with `dependencies=[Depends(require_approved_user)]`.
5. If it exposes static sub-paths under `/api/books`, mount it **before** the `books` router.
6. Update [api.md](../reference/api.md) and, if state changed, [data-model.md](data-model.md).

---

## 3. Error contract

Every error response is JSON with a stable `type` discriminator:

| Type | Produced by | Shape |
| --- | --- | --- |
| `validation_error` | `RequestValidationError` handler | `{detail: [{loc, msg, type, …}], type}` — `ctx` is stripped because it can hold a non-serialisable exception |
| `http_error` | `StarletteHTTPException` handler | `{detail, type}` |
| `internal_error` | catch-all handler | `{detail: "An internal server error occurred.", type}` — the real exception is logged, never returned |

Domain errors inside services raise `AuthError(detail, status_code, code)`, which the API layer
converts to an `HTTPException`. Tasks raise `JobCancelled` to signal "stop quietly, do not mark
failed".

Ownership failures deliberately return **404**, not 403.

---

## 4. Pagination

A single dependency is used everywhere:

```python
async def get_pagination(page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=100)) -> PaginationParams
```

`PaginationParams.offset` is derived. Responses use a shared envelope (`Page[T]`) carrying items plus
total count, which the frontend consumes as `Page<T>`. Page size is capped at 100.

---

## 5. Configuration

`Settings` is a `pydantic_settings.BaseSettings` subclass reading environment variables and an
optional `.env`. `_validate_security_settings()` refuses to start in non-debug mode when
`JWT_SECRET_KEY` is shorter than 32 characters, and warns when `CORS_ORIGINS` contains `*`.

Every variable and default is documented in [configuration](../development/configuration.md).

---

## 6. Lifespan

On startup:

1. Configure logging.
2. Validate security settings.
3. Connect Redis (degrade gracefully if absent).
4. Start the SSE subscriber.
5. Load maintenance state.
6. Start the job reaper loop (300 s) and maintenance refresh loop (10 s).

On shutdown everything is cancelled and closed in reverse order, including the shared
`llm_service` HTTP client.

---

## 7. Background work

Celery is configured with `acks_late`, `task_reject_on_worker_lost`, `worker_prefetch_multiplier=1`,
and `task_track_started`. Task routes:

| Task | Queue |
| --- | --- |
| `render_pages_for_book` | `ocr` |
| `apply_preprocessing_bulk` | `ocr` |
| `preprocess_pages_for_book` | `ocr` |
| `run_ocr_for_book` | `ocr` |
| `run_llm_extraction` | `llm` |

Signal handlers reconcile the database when Celery reports `task_failure` (job → failed, stage →
failed, notification + SSE) or `task_revoked` (job → cancelled). See
[jobs-and-queues](../processing/jobs-and-queues.md).

---

## 8. Concurrency and consistency rules

These are load-bearing and easy to break:

1. **Never open a second session for stage transitions.** The writing transaction already holds a
   `KEY SHARE` lock on the book row; a second session asking `FOR UPDATE` blocks, and because the
   first coroutine awaits it, the two deadlock. `StageManager` calls always take the *current*
   session.
2. **Lock before progressing.** `jobs.progress` updates use `SELECT … FOR UPDATE` and refuse to go
   backwards.
3. **Check supersede before writing.** Every terminal path calls `is_superseded_async()` so a stale
   task cannot overwrite a newer run's results.
4. **`BookMetadata` writes take `FOR UPDATE`** so a worker never clobbers a user edit made during
   extraction. Custom fields survive re-runs; standard fields do not.
5. **Stage transitions may legitimately fail.** `StageTransitionError` is caught and logged where the
   job result is still worth keeping.

---

## 9. Observability hooks

| Hook | Location |
| --- | --- |
| New Relic background tasks | `@newrelic.agent.background_task(...)` on every Celery task, plus custom attributes for `book_id`, `job_id`, `model`, `language` |
| Metrics | `services/metrics.py` — OCR completion count, average confidence, duration |
| Structured logging | `core/logging_config.py`, `logger.exception` in every handler |
| Health | `GET /health` (unprefixed, unauthenticated) and `/api/health` |

---

## 10. Testing seams

The backend is written so these are testable in isolation:

- `services/` contains pure functions where possible (`preprocessing`, `page_selection`,
  `batch_routing`, `ocr_outcome`).
- `tasks/async_utils.py` provides `run_async` / `run_async_threadsafe` so sync Celery code can be
  driven deterministically.
- The LLM is injectable into the hybrid orchestrator (`llm_fill_remaining` callback), so extraction
  tiering can be tested without Ollama.

See [running tests](../testing/running-tests.md).


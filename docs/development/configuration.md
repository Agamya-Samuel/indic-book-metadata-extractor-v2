# Configuration

Every backend setting is a field on `Settings` (`backend/app/core/config.py`), read from environment
variables or an optional `.env`. Compose files add a few variables of their own that the application
never sees.

Defaults shown are the **local development** defaults. Production overrides several in
`docker-compose.production.yml`.

---

## Required in production

These abort the deploy at Compose interpolation if unset:

| Variable | Notes |
| --- | --- |
| `POSTGRES_PASSWORD` | Also embedded in `DATABASE_URL` |
| `JWT_SECRET_KEY` | 32+ characters enforced at startup |
| `FRONTEND_URL` | Used in email links |

---

## Application

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Indic Book Metadata Extractor` | Display name |
| `DEBUG` | `false` | Enables `/docs`, `/redoc`, `/openapi.json`; relaxes JWT length check |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated; `*` logs a warning |
| `MAX_UPLOAD_SIZE_MB` | `200` | Enforced by middleware before spooling |
| `STORAGE_PATH` | `/app/storage` | Root for all file paths |
| `FRONTEND_URL` | `http://localhost:3000` | Base URL for links in email |

---

## Database and cache

| Variable | Default |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` |

Redis db 0 is the broker, db 1 the result backend. Rate limiting, SSE and the pipeline lock share
db 0.

---

## Jobs

| Variable | Default | Purpose |
| --- | --- | --- |
| `STALE_JOB_MINUTES` | `90` | Age at which the reaper fails a `running` job |
| `STALE_JOB_REAPER_ENABLED` | `true` | Disable to stop the reaper loop |

---

## LLM

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | Inference endpoint |
| `LLM_NATIVE_ENDPOINT` | `false` | Force `/api/chat` for all models. Thinking models use it regardless |
| `LOW_CONFIDENCE_THRESHOLD` | `0.55` | Below this, the UI shows "review needed" |

The default model is not an environment variable — it is `DEFAULT_LLM_MODEL` in `config.py`
(`gemma4:e4b`), passable per request.

---

## Authentication

| Variable | Default | Purpose |
| --- | --- | --- |
| `JWT_SECRET_KEY` | `dev-insecure-change-me` | **Must be ≥32 chars outside debug** |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `EMAIL_VERIFICATION_EXPIRE_HOURS` | `24` | |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `60` | |
| `PASSWORD_MIN_LENGTH` | `10` | |
| `COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `COOKIE_DOMAIN` | `""` | Leave empty for host-only cookies |
| `REGISTRATION_REQUIRES_APPROVAL` | `true` | When `false`, signups are auto-approved |

---

## Email

| Variable | Default | Purpose |
| --- | --- | --- |
| `SMTP_ENABLED` | `false` | Master switch; local default sends nothing |
| `SMTP_HOST` | `""` | |
| `SMTP_PORT` | `587` | |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | `""` | |
| `SMTP_FROM` | `""` | |
| `SMTP_STARTTLS` | `true` | |
| `SMTP_USE_TLS` | `false` | Implicit TLS (port 465) |
| `SMTP_TIMEOUT` | `15` | Seconds |

In-app notifications are never gated by these; only alert email is.

---

## OCR

| Variable | Default | Purpose |
| --- | --- | --- |
| `TESSERACT_CMD` | `tesseract` | Binary |
| `TESSERACT_OEM` | `1` | LSTM engine only |
| `TESSERACT_TESSDATA_DIR` | `""` | Custom tessdata directory |
| `OCR_RENDER_DPI` | `300` | PDF render DPI **and** Tesseract `--dpi` |
| `OCR_BATCH_SIZE` | `10` | Worker batch hint |
| `OCR_THREAD_WORKERS` | `4` | Thread pool size |
| `OCR_BINARIZATION` | `sauvola` | Configured method (binarization is off unless a page enables it) |
| `OCR_DENOISE_STRENGTH` | `7` | |
| `OCR_UPSCALE_DPI` | `300` | |
| `OCR_TEL_ENGINE` | `tesseract` | `tesseract` or `line_model` |
| `OCR_LINE_MODEL_NAME` | `harsha-desaraju/telugu-ocr-model` | |
| `OCR_LINE_MODEL_FALLBACK_NAME` | `/app/ocr_models/telugu-ocr-model` | Used when the fine-tuned path is absent |
| `OCR_LINE_MODEL_DECODE` | `ctc` | |
| `OCR_LINE_MODEL_CONFIDENCE` | `50.0` | Stand-in confidence (model emits none) |
| `OCR_USE_DICTIONARY` | `""` | Comma-separated language codes, e.g. `hin,tel` |
| `OCR_SCRIPT_ROUTING` | `true` | Enable both re-route rules |
| `OCR_POSTPROCESS` | `true` | NFC / danda / ZWJ normalisation |
| `OCR_LOW_CONF_RETRY` | `true` | Per-word `--psm 8` retry |
| `OCR_LOW_CONF_THRESHOLD` | `40` | Retry below this confidence |

Production sets `OCR_TEL_ENGINE=line_model` for the worker and points
`OCR_LINE_MODEL_NAME` at `/app/storage/models/telugu-ocr-ft`.

---

## New Relic

| Variable | Default |
| --- | --- |
| `NEW_RELIC_ENABLED` | `false` |
| `NEW_RELIC_LICENSE_KEY` | `""` |
| `NEW_RELIC_APP_NAME` | `Indic Book Metadata Extractor` |
| `NEW_RELIC_ENVIRONMENT` | `production` |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | `true` |
| `NEW_RELIC_LOG` | `error` |
| `NEW_RELIC_CONFIG_FILE` | `newrelic.ini` |
| `NEW_RELIC_MONITOR_MODE` | `true` |
| `NEW_RELIC_DEVELOPER_MODE` | `false` |

Frontend needs the matching `NEXT_PUBLIC_NEW_RELIC_*` values at **build** time.

---

## Wikibase

| Variable | Default |
| --- | --- |
| `PROPERTY_MAPPING_PATH` | `/app/storage/property-mapping.json` |

`wikibase-init` writes this file to both `/config/property-mapping.json` and the mounted backend
storage volume, so the backend loads it on startup. Restart the backend after re-running the init
container.

---

## Compose-only variables

Read by `docker-compose*.yml`, never by the app:

| Variable | Purpose |
| --- | --- |
| `COMPOSE_PROFILES` | Would gate optional services — **not yet applied** to production compose |
| `NEXT_PUBLIC_API_URL` | Frontend API base, default `/api` |
| `NEXT_PUBLIC_OPENREFINE_URL`, `NEXT_PUBLIC_WIKIBASE_URL` | Baked into the client bundle at build time |
| `FLOWER_BASIC_AUTH` | Required for Flower |
| `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `WIKIBASE_ADMIN_PASS`, `WIKIBASE_HOST`, `WIKIBASE_SCHEME`, `QUICKSTATEMENTS_PUBLIC_URL` | Optional Wikibase stack |
| `BACKUP_PATH`, `BACKUP_KEEP` | `backup-db.sh` output directory and retention (default 7) |

---

## Precedence

1. Environment variables (Compose `environment:` block, or the shell).
2. `.env` file in the backend working directory.
3. Field defaults in `Settings`.

Compose `environment:` always wins, which is why `.env.production` and `.env.staging` exist as complete
templates rather than partial overrides.

---

## Validation performed at startup

| Check | Behaviour |
| --- | --- |
| `JWT_SECRET_KEY` length | `RuntimeError` when `< 32` and `DEBUG=false` |
| `CORS_ORIGINS` contains `*` | Warning (credentialed wildcard) |
| Redis reachable | Warning; rate limiting and SSE degrade |
| Ollama reachable | Reported by `/health` as `degraded` |

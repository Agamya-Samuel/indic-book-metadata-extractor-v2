# Known Issues — Indic Book Metadata Extractor

## Integration Test Limitations

### Skipped Test: Library Filter Options

**Test**: `test_admin_books.py::TestAdminFilterOptions::test_get_filter_options`

**Status**: Skipped

**Reason**: The `get_filter_options` endpoint in `SearchService` uses PostgreSQL-specific JSONB `.astext` operator to query genre and publisher values from the `metadata.fields` JSONB column. The test suite uses SQLite in-memory databases, which do not support this operator.

**Workaround**: This test runs successfully against a live PostgreSQL instance (Docker stack). To validate:
```bash
make up
# Wait for services to be healthy
docker compose exec backend uv run pytest tests/integration/test_admin_books.py -v -k "test_get_filter_options" --no-header
```

**Resolution**: Would require either a PostgreSQL test container or refactoring the query to use SQLAlchemy JSON rendering that works across both SQLite and PostgreSQL.

---

## Performance

### CPU-Only LLM Inference

LLM metadata extraction runs entirely on CPU via Ollama. A full 52-field extraction (8 batches) takes approximately 10-20 minutes per book depending on CPU speed and OCR text length.

**Mitigation**: The job runs in the background. Users can leave and return — progress streams over SSE (with polling fallback) and the job can be cancelled.

### One book is processed at a time

A global Redis lock plus worker concurrency 1 means a second book queues until
the first book's OCR and extraction finish. This is deliberate (4 vCPU / 16 GB,
no swap) and keeps a single book's latency predictable; concurrent users should
expect a queue. The dashboard shows queue position.

### Large PDF Rendering

Rendering all pages of a 500+ page PDF at 300 DPI simultaneously may consume significant memory.

**Mitigation**: Only selected pages are rendered. The page selection step limits rendering to relevant pages only.

---

## OCR Accuracy

### Indic Script Recognition

Tesseract OCR accuracy on Telugu and Hindi scripts varies significantly depending on scan quality. Clean, modern prints typically achieve 70-85% accuracy; degraded or old scans may fall below 60%.

**Mitigation**: The preprocessing step (binarization, deskew, denoise) improves results. The OCR review step is essential for correcting errors before LLM extraction.

### Bilingual Pages

Pages containing mixed languages (e.g., Telugu + English) use multi-language OCR mode (`tel+eng` or `hin+eng`). Accuracy may decrease on pages with heavy code-switching.

### Telugu OCR is the accuracy ceiling (engine wired, activation blocked)

Measured on our verified scans ([learnings/020](../learnings/020-ocr-engine-benchmark.md)): Tesseract Telugu leaves ~40 % of characters wrong (median CER 0.40) — the dominant pipeline error. A Telugu-specific line model (`harsha-desaraju/telugu-ocr-model`) more than halves it (median CER 0.16) and is the **chosen** Telugu engine.

**Status (2026-11-15):** wired and active in production compose (`OCR_TEL_ENGINE=line_model`, `ocr_line_model.py`, Telugu only). The worker image bakes CPU `torch`/`transformers` plus the **310 MB** weights (not 1.7 GB), so nothing is downloaded at runtime; any load/inference error falls back to Tesseract per page. The host's egress is now fast enough (PyPI ~32 MB/s, Hugging Face ~1.1 MB/s) that the old artifact blocker is gone.

**Mitigation when the model cannot load:** the per-page Tesseract fallback plus the OCR review step; optionally switch Telugu back to `tessdata_best`. Preprocessing (binarization/denoise) did **not** help Telugu and is disabled by default.

**Integration plan and next steps:** [plans/017](../plans/017-telugu-ocr-engine-integration.md), [todos/012](../todos/012-ocr-engine-integration-handoff.md). The worker build bakes the artifact (build arg `OCR_LINE=true`); verify CER on one Telugu book after the deploy.

### IndicOCR (Hindi step-change) is gated and not CPU-viable

`bodhan-ai/indic-ocr` (0.8 B VLM, currently the best published Hindi accuracy) needs Python ≥3.11, `device="cpu"`, and a Hugging Face licence + token; on the 4-vCPU CPU box it did **not** complete a page in >12 min → **excluded**. Hindi therefore stays on Tesseract (median CER 0.07). Full engine requirements and environment gotchas: [learnings/021](../learnings/021-ocr-engine-operational-requirements.md).

---

## Feature Gaps

### No Semantic Search

The `embeddings` table with pgvector(768) exists in the schema, but no service populates or queries it. Semantic/similarity search is not implemented.

### Authentication

The application has email+password authentication with two roles (`user`,
`admin`), email verification, **admin-approved registration**, and per-user book
ownership. There is no anonymous or guest access: every page and API except the
signup/login/verify/reset endpoints requires a session, and `pending`/`rejected`
accounts reach only the `/pending-approval` holding screen. The Library is
admin-only; regular users use the owner-scoped Dashboard. The first admin must
be created via `make create-admin` (admin-created and CLI accounts are
`approved`). See [api-reference.md](api-reference.md) for the auth endpoints.

### Notification emails depend on a working SMTP configuration

In-app notifications are always written, independently of mail delivery. Their
email mirror is only attempted when the recipient has `email_notifications_enabled`
and the backend has SMTP configured (`SMTP_*`). When SMTP is unset or failing,
the send is logged and skipped; the request or job that produced the event still
succeeds, and the notification stays visible in the app.

Production is configured for Resend's raw SMTP endpoint and a live signup +
password-reset round trip succeeded on 2026-11-14.

### Landing page model label

The home page now says **"Local LLM"** instead of naming a specific model, so
the copy does not go stale between `gemma4:e4b` (the default, native `/api/chat`
path) and `phi4-mini` (rollback). Fixed 2026-11-15; see
`plans/012-llm-service-native-endpoint.md` and the model evaluation reports. The
model remains selectable per run on the LLM configuration page.

### Server-Sent Events fall back to polling

Job status updates stream over SSE (`/api/sse/books/{id}/events`). If the
stream drops or goes silent for ~25 seconds, the UI falls back to HTTP polling
and shows a "using polling fallback" notice. This is intentional, but progress
can lag by the polling interval until the stream reconnects.

### Page extraction runs as a background job

Selected pages are rendered by a `PAGE_EXTRACTION` Celery job with per-page
progress, cancellation and a dedicated `/extracting-pages` screen. It shares
the single-book lock with OCR and extraction.

---

## Deployment and operations

### Mail and media delivery are configured

Production uses Resend's raw SMTP endpoint (`smtp.resend.com`, user `resend`,
the API key from the gitignored `.env`), verified with a real signup and
password reset. Page images and thumbnails carry six-hour signed URLs scoped to
one page or one book, so they keep loading after the access cookie expires.

### The origin is reachable without Cloudflare

`https://indic-book-metadata-extractor.agamya.us.kg/` resolves to the origin
`<origin-ip>` and answers **200** with the real Host header, so Cloudflare's
WAF and rate rules can be bypassed by connecting to the IP, and the proxy
headers the app trusts (`CF-Connecting-IP`, the last `X-Forwarded-For` hop) can
be forged that way. Dokploy `:3000` and Traefik `:8080` also stay published.
Closing ingress to Cloudflare ranges (or moving to a Cloudflare Tunnel) is an
operator action on the Cloudflare side; see `docs/runbook.md`.

**Egress is no longer a problem (measured 2026-11-15):** PyPI ~32 MB/s,
Cloudflare ~20 MB/s, Hugging Face ~1.1–2.3 MB/s, Docker/Ollama registry pulls
work. The old ~40–60 KB/s figure is stale ([learnings/024](../learnings/024-host-network-and-gemma-resource-reality.md)).

### Public launch is gated on operator actions

The application code and deployment are complete (CI green, Resend mail live,
signed media URLs, single-book pipeline, guarded inputs). Before opening to the
public, the operator still has to:

1. close origin ingress so only Cloudflare reaches the host (the raw IP bypasses
   WAF/rate rules today);
2. copy backups off-host and complete one restore drill from that copy;
3. configure alerting (site, worker, stuck job, disk, backup age);
4. perform launch hygiene: remove/rotate the QA accounts and the pending signup,
   decide the 3 sample books, rotate `reference/oki-qa-accounts`, and confirm the
   real first admin's password;
5. ~~confirm the landing-page copy~~ — fixed 2026-11-15: the page says
   "Local LLM" and carries the Telugu/Hindi OCR expectation note. Still open:
   confirm the pilot-phase/approval-based signup wording.

The full checklist, owners and expectation-setting live in
[plans/011-launch-readiness.md](../plans/011-launch-readiness.md).

### Backups have no offsite copy

Daily `pg_dump -Fc` backups are kept (newest 7) and a restore drill succeeded on
2026-11-14, but they live in a Docker volume on the same host and disk as the
database. A host or disk loss loses both. Copying the dumps off-host needs a
destination and credentials.

### No APM or alerting

`NEW_RELIC_ENABLED=false` and logs are local (`json-file`, 3 × 10 MB per
container). There is no alert when the site, worker or a backup fails. The
minimum alert set is in `docs/runbook.md`.

### Ollama memory cap has killed the model mid-run

`phi4-mini` measured ~6.15 GB resident, above the old 6 GB cap, and was
OOM-killed twice on 2026-11-13 (the host has no swap). `gemma4:e4b` is larger:
**6.6 GB on disk, ~6.7 GiB idle and ~7.9 GiB during a real extraction**, so the
cap is now **9 GB**. `phi4-mini` stays installed as the rollback model. An
extraction that starts while the model is restarting fails its batches and
reports "All batches failed".

## Platform-Specific

### Docker on Windows

Docker Desktop on Windows may experience slower file I/O with bind-mounted volumes compared to Linux or macOS.

**Mitigation**: Use WSL2 backend for Docker Desktop. Named volumes (used for postgres, redis, ollama) avoid this issue.

### First Run Model Download

On first startup, Ollama downloads the default model (`gemma4:e4b`, ~6.6 GB). On the current host this takes ~1–2 minutes (registry throughput is high); on a slower link it can take much longer. The `ollama` health check has a 120-second start period to accommodate it.

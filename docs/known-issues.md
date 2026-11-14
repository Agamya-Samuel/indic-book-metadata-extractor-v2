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

### Telugu OCR is the accuracy ceiling (engine selected, not yet wired)

Measured on our verified scans ([learnings/020](../learnings/020-ocr-engine-benchmark.md)): Tesseract Telugu leaves ~40 % of characters wrong (median CER 0.40) — the dominant pipeline error. A Telugu-specific line model (`harsha-desaraju/telugu-ocr-model`) more than halves it (median CER 0.16) and is the **chosen** Telugu engine, but it is **not yet integrated** into `ocr_service.py`.

**Mitigation (until integrated):** the OCR review step; optionally switch Telugu to `tessdata_best`. Preprocessing (binarization/denoise) did **not** help Telugu and is disabled by default.

**Integration plan and blocker:** [plans/017](../plans/017-telugu-ocr-engine-integration.md). The model needs `torch`/`transformers` and weights fetched from Hugging Face; the production host's egress (~40–60 KB/s) makes an image build or first-boot download impractical. Build and measure on a GCP node, then bake the artifact into the image or a volume.

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

`https://187.127.174.246/` answers directly, so Cloudflare's WAF and rate rules
can be bypassed by connecting to the IP, and the proxy headers the app trusts
(`CF-Connecting-IP`, the last `X-Forwarded-For` hop) can be forged that way.
Closing ingress to Cloudflare ranges (or moving to a Cloudflare Tunnel) is an
operator action on the Cloudflare side; see `docs/runbook.md`.

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

`llama-server` measured ~6.15 GB resident, above the previous 6 GB container cap,
and was OOM-killed twice on 2026-11-13 (the host has no swap). The cap is now
7 GB. An extraction that starts while the model is being restarted fails its
batches and reports "All batches failed".

## Platform-Specific

### Docker on Windows

Docker Desktop on Windows may experience slower file I/O with bind-mounted volumes compared to Linux or macOS.

**Mitigation**: Use WSL2 backend for Docker Desktop. Named volumes (used for postgres, redis, ollama) avoid this issue.

### First Run Model Download

On first startup, Ollama downloads the default model (`phi4-mini`, ~2.5 GB). This can take several minutes depending on network speed. The `ollama` health check has a 60-second start period to accommodate it.

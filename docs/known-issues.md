# Known Issues — Indic Book Metadata Extractor

## Integration Test Limitations

### Skipped Test: Library Filter Options

**Test**: `test_api_library.py::TestGetFilterOptions::test_get_filter_options`

**Status**: Skipped

**Reason**: The `get_filter_options` endpoint in `SearchService` uses PostgreSQL-specific JSONB `.astext` operator to query genre and publisher values from the `metadata.fields` JSONB column. The test suite uses SQLite in-memory databases, which do not support this operator.

**Workaround**: This test runs successfully against a live PostgreSQL instance (Docker stack). To validate:
```bash
make up
# Wait for services to be healthy
docker compose exec backend uv run pytest tests/integration/test_api_library.py -v -k "test_get_filter_options" --no-header
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

---

## Feature Gaps

### No Semantic Search

The `embeddings` table with pgvector(768) exists in the schema, but no service populates or queries it. Semantic/similarity search is not implemented.

### No Dark Mode Toggle

CSS classes support dark mode theming, but there is no UI toggle to switch between light and dark themes.

### Authentication

The application has email+password authentication with two roles (`user`,
`admin`), email verification, and per-user book ownership. Anonymous visitors
can browse the public catalog; owners and admins manage everything else. The
first admin must be created via `make create-admin`. See
[api-reference.md](api-reference.md) for the auth endpoints.

### Server-Sent Events fall back to polling

Job status updates stream over SSE (`/api/sse/books/{id}/events`). If the
stream drops or goes silent for ~25 seconds, the UI falls back to HTTP polling
and shows a "using polling fallback" notice. This is intentional, but progress
can lag by the polling interval until the stream reconnects.

### Page extraction is still synchronous

Page image rendering for the selected pages currently happens inside the
`POST /books/{id}/pages` request. A Celery-backed page-extraction job with
per-page progress and cancel is planned (see
`plans/006-ui-ux-workflow-admin.md`, Phase 3.7) but not implemented yet.

---

## Platform-Specific

### Docker on Windows

Docker Desktop on Windows may experience slower file I/O with bind-mounted volumes compared to Linux or macOS.

**Mitigation**: Use WSL2 backend for Docker Desktop. Named volumes (used for postgres, redis, ollama) avoid this issue.

### First Run Model Download

On first startup, Ollama downloads the Qwen2.5 7B model (~4 GB). This can take several minutes depending on network speed. The `ollama` health check has a 60-second start period to accommodate this.

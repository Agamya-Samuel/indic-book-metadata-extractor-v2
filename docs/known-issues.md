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

**Mitigation**: The job runs in the background. Users can leave and return — progress is tracked via polling.

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

### No Book Deletion

There is no `DELETE /api/books/{book_id}` endpoint. Books cannot be removed from the library through the UI or API.

**Workaround**: Delete directly from the database or use `make reset-db` to clear all data.

### No Semantic Search

The `embeddings` table with pgvector(768) exists in the schema, but no service populates or queries it. Semantic/similarity search is not implemented.

### No Dark Mode Toggle

CSS classes support dark mode theming, but there is no UI toggle to switch between light and dark themes.

### No Authentication

The application has no authentication or authorization system. It is designed for single-user local deployment.

### No WebSocket/SSE

Job status updates use HTTP polling (every 2 seconds) rather than WebSocket or Server-Sent Events. This creates unnecessary network traffic but is simpler to implement and debug.

---

## Platform-Specific

### Docker on Windows

Docker Desktop on Windows may experience slower file I/O with bind-mounted volumes compared to Linux or macOS.

**Mitigation**: Use WSL2 backend for Docker Desktop. Named volumes (used for postgres, redis, ollama) avoid this issue.

### First Run Model Download

On first startup, Ollama downloads the Airavata model (~4 GB). This can take several minutes depending on network speed. The `ollama` health check has a 60-second start period to accommodate this.

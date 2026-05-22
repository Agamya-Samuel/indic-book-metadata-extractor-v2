# Indic Book Metadata Extractor — 12-Week Implementation Plan

## Context

This is a **greenfield project** — only specification documents exist ([indic_book_metadata_extractor.md](d:/WikiProjects/OKI/Indic-Book-Metadata-Extractor/docs/indic_book_metadata_extractor.md), [tech_stack.md](d:/WikiProjects/OKI/Indic-Book-Metadata-Extractor/docs/tech_stack.md)). No code has been written yet. The goal is to build a full-stack web application for OCR-powered metadata extraction from Telugu and Hindi scanned book PDFs.

**Project Scope**: A 7-step guided workflow (upload → page select → preprocessing → OCR review → LLM config → metadata review → library/search) that extracts 52 bibliographic fields per book using Tesseract OCR and Airavata 7B LLM.

**Constraints**: Solo developer, local/Docker Compose deployment only, CPU-only with 16GB RAM (limiting LLM to 7B models), MVP languages are Telugu + Hindi.

---

## Strategic Approach

1. **Vertical slice first**: Get a single PDF through the entire pipeline before polishing any individual step
2. **Front-load risk**: Test Tesseract OCR accuracy on Indic scripts early — this determines if preprocessing R&D needs more time
3. **Infrastructure before features**: Docker Compose, database, Celery, and Ollama must be stable before feature work
4. **Realistic pacing**: Budget 70% new development, 15% debugging/integration, 15% testing per week

---

## Month 1: Foundation and Vertical Slice

**Milestone**: End-to-end flow working — upload Telugu PDF → select pages → run OCR → review bounding boxes → invoke Airavata for subset of metadata fields → see results in database. UI is crude but functional.

### Week 1: Project Scaffolding & Infrastructure

**Deliverables**:
- Monorepo structure: `frontend/`, `backend/`, `docker/`
- Docker Compose with 7 services: postgres, redis, backend (FastAPI), worker (Celery), ollama, flower, frontend
- Dockerfiles for backend, worker, frontend (multi-stage)
- Backend skeleton: FastAPI health-check, Celery app, SQLAlchemy async engine
- Database schema v1 via Alembic (7 tables: books, pages, ocr_results, jobs, metadata, llm_runs, embeddings)

**Key files**:
- `docker-compose.yml`
- `docker/Dockerfile.backend`, `docker/Dockerfile.worker`, `docker/Dockerfile.frontend`
- `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/database.py`
- `backend/app/models/` (SQLAlchemy ORM models)
- `backend/app/tasks/celery_app.py`
- `backend/alembic/versions/001_initial_schema.py`
- `backend/pyproject.toml`

**Risks**:
- Ollama Airavata model pull is ~4GB, slow on first run
- Tesseract must be installed in Docker image (tesseract-ocr, tesseract-ocr-tel, tesseract-ocr-hin packages)
- pgvector extension requires `pgvector/pgvector:pg16` image

---

### Week 2: PDF Upload & Page Extraction

**Deliverables**:
- `POST /api/books/upload` — multipart upload, saves PDF to `storage/uploads/`, creates `books` record
- PDF service using PyMuPDF: count pages, render 300 DPI thumbnails, render full-resolution images for selected pages
- `POST /api/books/{book_id}/pages` — accepts front_pages/back_pages counts, creates `pages` records, renders selected pages
- Frontend: Upload page with react-dropzone, redirects to page selection
- Frontend: Page selection view with thumbnail grid, front/back spinners, "Confirm Selection" button

**Key files**:
- `backend/app/api/books.py`
- `backend/app/schemas/book.py`
- `backend/app/services/pdf_service.py`
- `backend/app/core/storage.py`
- `frontend/src/app/upload/page.tsx`
- `frontend/src/app/books/[bookId]/select-pages/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/stores/book-store.ts` (Zustand)

**Risks**:
- 300 DPI images can be 30MB+ per page — use JPEG for thumbnails, PNG for processing only
- Rendering 500-page PDF all at once will OOM — lazy thumbnail generation or batching

---

### Week 3: Image Preprocessing & OCR Pipeline (HIGHEST RISK)

**Deliverables**:
- Image preprocessing service: grayscale, brightness/contrast, binarization (Otsu/adaptive), deskew — all configurable via OpenCV/Pillow
- `PUT /api/pages/{page_id}/preprocessing` — saves per-page settings, returns processed image for preview
- OCR Celery task: loads preprocessed image, runs `pytesseract.image_to_data()` with tel/hin language, parses to bounding box JSON, stores in `ocr_results`
- `POST /api/books/{book_id}/run-ocr` — creates job, dispatches Celery group with one task per page
- Manual OCR test harness: standalone script to test preprocessing + OCR on sample images

**Key files**:
- `backend/app/services/preprocessing.py`
- `backend/app/services/ocr_service.py`
- `backend/app/tasks/ocr_tasks.py`
- `backend/app/api/pages.py`
- `scripts/test_ocr_pipeline.py`

**Risks**:
- **Tesseract accuracy on Telugu/Hindi may be poor** — this is THE critical risk. Budget extra time for preprocessing iteration.
- Deskew accuracy is crucial for Indic connected-character scripts
- Bilingual pages need `tel+eng` or `hin+eng` language parameter
- `image_to_data()` returns empty blocks — filter logic needed

---

### Week 4: OCR Review UI & End-to-End Skeleton

**Deliverables**:
- `GET /api/pages/{page_id}/ocr` — returns OCR result (text, bounding boxes, confidence)
- `PUT /api/pages/{page_id}/ocr` — saves user corrections
- Frontend: Preprocessing tuning page — per-page sliders (grayscale, brightness, contrast, binarization, deskew), preview before/after, "Apply to All", "Run OCR"
- Frontend: OCR Review page — side-by-side image (react-konva bounding boxes) and editable text, click-to-highlight, Previous/Next navigation
- Frontend: Job polling with React Query — checks status every 2s, shows progress, navigates on completion
- End-to-end smoke test: upload Telugu PDF, select pages, run OCR, review, verify database

**Key files**:
- `frontend/src/app/books/[bookId]/preprocessing/page.tsx`
- `frontend/src/app/books/[bookId]/ocr-review/page.tsx`
- `frontend/src/components/ocr/bounding-box-canvas.tsx`
- `frontend/src/components/ocr/text-editor.tsx`
- `frontend/src/hooks/use-job-polling.ts`

**Risks**:
- Bounding box coordinate mapping between Tesseract output and canvas display size requires scaling logic
- This is a buffer week — if Week 3 OCR quality was poor, reallocate time to preprocessing iteration

---

## Month 2: LLM Integration & Feature Completion

**Milestone**: Full pipeline functional — all 52 metadata fields extractable in batches, complete UI workflow, searchable library page.

### Week 5: LLM Infrastructure & Batched Extraction Prototype

**Deliverables**:
- LLM service wrapping Ollama API with Instructor for structured output
- Pydantic schema for 52 metadata fields (`backend/app/schemas/metadata.py`) grouped into extraction batches
- LLM Celery task: loads OCR text, runs batched extraction (sequential calls per field group), validates via Pydantic, merges results, stores in `metadata` and `llm_runs`
- `POST /api/books/{book_id}/run-extraction` — accepts model selection, temperature, batch config, creates job, dispatches task
- Prompt template system with Jinja2 for system prompt and extraction prompt
- Standalone test script for LLM extraction against sample OCR text

**Key files**:
- `backend/app/services/llm_service.py`
- `backend/app/services/prompts.py`
- `backend/app/schemas/metadata.py` (52 fields + batch groups)
- `backend/app/tasks/llm_tasks.py`
- `backend/app/api/extraction.py`
- `scripts/test_llm_extraction.py`

**Risks**:
- **Airavata 7B on CPU**: 5-15 tokens/sec means 10-20 minutes per full extraction — must handle gracefully with polling
- Instructor + Ollama compatibility — verify or use Ollama native JSON schema + manual Pydantic validation
- **Airavata structured output quality** — 7B models may struggle with strict JSON in Indic languages
- Prompt engineering for Indic OCR text is non-trivial

---

### Week 6: LLM Config UI & Metadata Review UI

**Deliverables**:
- Frontend: LLM Configuration page — model dropdown, temperature/max_tokens/top_p sliders, fields-per-batch slider, editable prompts, list of 52 fields by batch, custom field support, "Run Extraction"
- Frontend: Job Queue Dashboard — list of all jobs with status badges, color-coded, refresh/retry for failed, auto-refresh
- Frontend: Metadata Review page — 52 fields grouped by category, pre-filled with LLM values, low-confidence fields highlighted, inline-editable, page image viewer at top (reuse bounding box component), click-to-copy, "Save Metadata"
- `GET/PUT /api/books/{book_id}/metadata` — returns/updates full metadata record
- Custom field support in metadata JSONB column

**Key files**:
- `frontend/src/app/books/[bookId]/llm-config/page.tsx`
- `frontend/src/app/books/[bookId]/metadata-review/page.tsx`
- `frontend/src/app/books/[bookId]/jobs/page.tsx`
- `frontend/src/components/metadata/metadata-form.tsx`
- `frontend/src/components/jobs/job-list.tsx`
- `backend/app/api/metadata.py`

**Risks**:
- 52-field form needs careful UX — grouping and collapsible sections essential
- Bounding box component must be properly abstracted for reuse between OCR review and metadata review

---

### Week 7: Library Page, Search & Book Management

**Deliverables**:
- `GET /api/books` — paginated list with finalized metadata, supports query params (search, language, genre, year, publisher)
- `GET /api/books/search?q=...` — pg_trgm fuzzy search across title, author, publisher, description, JSONB fields
- Frontend: Library page — card grid with thumbnail/title/author/language/year, pagination, search bar (debounced React Query)
- Frontend: Client-side Fuse.js search for instant "search as you type" before server-side fallback
- Frontend: Book detail view — read-only display of all metadata, all page images with OCR text, LLM run history, "Edit Metadata" button

**Key files**:
- `backend/app/api/library.py`
- `backend/app/services/search_service.py`
- `frontend/src/app/library/page.tsx`
- `frontend/src/app/books/[bookId]/detail/page.tsx`
- `frontend/src/components/library/book-card.tsx`
- `frontend/src/lib/fuse-config.ts`

**Risks**:
- pg_trgm requires GIN indexes on searchable columns — Alembic migration needed
- JSONB field extraction for search is complex — consider generated column or materialized view
- Fuse.js scales to a few hundred books — server-side becomes primary beyond that

---

### Week 8: Polish, Bug Fixes & Integration Hardening

**Deliverables**:
- Workflow navigation with persistent state — stepper/breadcrumb component, Zustand store hydrates from backend (book status determines step), "leave and return" support
- Comprehensive error handling — toast notifications, inline validation, error boundaries, job error logs in dashboard
- Docker Compose hardening — health checks for postgres/redis/ollama, Ollama pre-loads Airavata on startup, restart policies
- Makefile or shell scripts: start, stop, rebuild, reset-database, download-model
- OCR accuracy iteration — test 5+ PDFs of varying quality, tune preprocessing defaults
- Resumable workflow validation test

**Key files**:
- `frontend/src/components/shared/workflow-stepper.tsx`
- `frontend/src/stores/workflow-store.ts`
- `frontend/src/lib/error-handler.ts`
- `docker-compose.yml` (health checks)
- `Makefile` or `scripts/dev.sh`

**Risks**:
- Buffer week — if Week 5 LLM extraction had issues, time goes to fixing those
- Workflow state machine edge cases: re-selecting pages after OCR completes, failed LLM extractions

---

## Month 3: Production Readiness, Testing & Polish

**Milestone**: Application tested, documented, and ready for real use. All features polished, known limitations documented.

### Week 9: Backend Tests (Unit & Integration)

**Deliverables**:
- pytest infrastructure with async support, test database, fixtures
- Unit tests: preprocessing service (verify outputs), OCR service (verify structure), LLM service (mocked Ollama, verify batching/schema validation)
- Integration tests: all API endpoints (upload, page select, OCR, LLM, metadata, library search)
- PDF service tests with real PDFs: page count, thumbnail generation, edge cases (corrupted, password-protected, single-page)
- Test fixtures: 3 sample PDFs (clean Telugu, clean Hindi, degraded), expected OCR outputs

**Key files**:
- `backend/tests/conftest.py`
- `backend/tests/test_api_*.py`
- `backend/tests/test_services_*.py`
- `backend/tests/test_tasks.py`
- `backend/tests/fixtures/`

**Risks**:
- OCR is non-deterministic — tests should verify structure, not exact text (unless controlled test image)
- Async SQLAlchemy testing requires careful session management in fixtures

---

### Week 10: Frontend Tests & E2E

**Deliverables**:
- Vitest configuration, component tests for key UI (upload dropzone, page grid, sliders, metadata form)
- Playwright E2E test: full workflow from upload to library
- Component tests: bounding-box-canvas (verify positions), metadata-form (52 fields, edits, save), search-bar (Fuse.js filtering)
- Hook/store tests: use-job-polling (polling start/stop), workflow store (state transitions)
- Visual regression baseline (optional): screenshots of 7 workflow pages

**Key files**:
- `frontend/vitest.config.ts`
- `frontend/playwright.config.ts`
- `frontend/tests/components/*.test.tsx`
- `frontend/tests/e2e/full-workflow.spec.ts`

**Risks**:
- E2E requires full Docker stack + Ollama with model — slow, consider mock Ollama for tests
- Playwright on Windows works but requires browser installation

---

### Week 11: UX Polish & Performance

**Deliverables**:
- Responsive layout pass (1280px-1920px, tablet/landscape OK)
- Loading states/skeleton screens for all data-fetching views
- Performance: DB indexes, SQLAlchemy connection pooling, lazy-load bounding box canvas, image lazy loading, React Query stale-while-revalidate, Celery task_acks_late
- Keyboard accessibility: tab order follows workflow, proper labels
- Dark mode support (if time permits)

**Key files**:
- All frontend components (iterative polish)
- `backend/app/core/database.py` (connection pool)
- `backend/alembic/versions/` (performance index migration)
- `frontend/src/components/shared/skeleton.tsx`

**Risks**:
- Bounding box rendering for pages with hundreds of words may be sluggish — consider SVG overlay or viewport-only rendering

---

### Week 12: Integration Testing, Documentation & Release

**Deliverables**:
- Full test suite run against Docker Compose stack, fix failures, document known issues
- User documentation: README with quickstart, architecture diagram, Ollama setup, workflow walkthrough with screenshots, troubleshooting
- Developer documentation: architecture overview, local dev setup, how to add metadata field/language, DB schema diagram, API reference
- Sample dataset: 5-10 PDFs with expected outputs (3 Telugu, 3 Hindi, varying quality)
- Release v0.1.0: tag, cleanup TODOs, verify docker-compose works from clean clone, CHANGELOG

**Key files**:
- `docs/README.md`
- `docs/user-guide.md`
- `docs/developer-guide.md`
- `docs/api-reference.md`
- `docs/changelog.md`
- `docker-compose.yml` (final tested version)

**Risks**:
- Documentation always takes longer than expected
- Significant bugs from integration testing take priority over doc polish

---

## Critical Path

```
Week 1 (infra) → Week 2 (upload/pages) → Week 3 (OCR) → Week 5 (LLM) → Week 6 (metadata UI) → Week 8 (integration) → Week 12 (release)
```

The frontend and backend testing can absorb schedule variance, but OCR and LLM pipelines are serial dependencies.

---

## Biggest Risks

1. **Tesseract OCR accuracy on Indic scripts** (Week 3, ongoing) — THE critical risk. Below ~70% accuracy makes downstream LLM extraction suffer. Mitigation: invest in preprocessing R&D, accept that OCR correction is a core workflow step, not nice-to-have.

2. **LLM structured output reliability** (Week 5) — Airavata 7B must produce valid JSON conforming to Pydantic schema for Indic content. Mitigation: Instructor for retry/validation, fallback to Kan-Llama, careful prompt design with examples.

3. **CPU inference speed** (Weeks 5-6) — 10-20 minutes per extraction. Users must understand this is background. Mitigation: clear progress indication, notification on complete.

4. **Docker on Windows performance** (Week 1) — Docker Desktop has issues with bind-mounted volumes. Mitigation: named volumes, .dockerignore, WSL2 backend.

5. **Scope creep on metadata fields** (Week 5) — Some fields (dedications, foreword authors) are very hard to extract automatically. Mitigation: design UI for easy manual fill, don't treat LLM nulls as failures.

---

## Critical Files for Implementation

- `backend/app/services/ocr_service.py` — Highest-risk component, accuracy determines system usefulness
- `backend/app/services/llm_service.py` — Most architecturally complex (batched extraction, validation)
- `backend/app/schemas/metadata.py` — Defines data contract for entire LLM pipeline
- `frontend/src/components/ocr/bounding-box-canvas.tsx` — Most complex frontend component
- `docker-compose.yml` — Foundation everything depends on (7 services orchestrated)

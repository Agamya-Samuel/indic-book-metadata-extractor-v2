# Changelog — Indic Book Metadata Extractor

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] — 2026-05-29

### Added

**Core Infrastructure**
- Docker Compose stack with 7 services (PostgreSQL, Redis, Ollama, FastAPI, Celery worker, Next.js, Flower)
- FastAPI backend with async SQLAlchemy and Pydantic v2 validation
- Celery task queue with Redis broker for background OCR and LLM processing
- Alembic database migrations (5 migrations: initial schema, indexes, pg_trgm GIN)
- PostgreSQL with pgvector extension and pg_trgm for fuzzy search
- Health checks for all services, Ollama auto-pull of Airavata model on startup

**7-Step Guided Workflow**
- Step 1: PDF upload with drag-and-drop, language selection (Telugu/Hindi), file validation
- Step 2: Page selection with thumbnail grid, front/back page picker, select all
- Step 3: Image preprocessing with per-page sliders (grayscale, brightness, contrast, binarization, deskew, denoise)
- Step 4: OCR review with Konva.js bounding box overlay, inline text editor, confidence-colored boxes
- Step 5: LLM configuration with model selection, temperature/max_tokens sliders, editable prompts, batch field list
- Step 6: Metadata review with 52-field form grouped by 8 batches, confidence indicators, inline editing
- Step 7: Library with card grid, Fuse.js instant search, server-side pg_trgm search, filters, pagination

**Backend Services**
- PDF service: PyMuPDF page counting, thumbnail rendering (180px), full-page rendering (300 DPI)
- Preprocessing service: OpenCV pipeline (grayscale, brightness/contrast, Otsu/adaptive binarization, deskew, denoise)
- OCR service: Tesseract with Telugu and Hindi language packs, word-level bounding boxes, confidence scoring, language detection
- LLM service: Ollama + Instructor batched extraction (8 batches of ~6 fields), retry logic, model listing
- Search service: pg_trgm fuzzy search across title, filename, and JSONB metadata fields
- Storage service: Organized file path management for uploads, thumbnails, pages, processed images

**Frontend**
- Next.js 16 with App Router, React 19, TypeScript, Tailwind CSS
- React Query for server state management with job polling (2s interval)
- Zustand for client state with persist middleware (workflow survives page refresh)
- Konva.js bounding box canvas with click-to-select and confidence coloring
- Fuse.js client-side fuzzy search for instant filtering
- Workflow stepper component with navigation state
- Loading skeletons for all data-fetching views
- Error boundary and toast notifications

**Database Schema (7 tables)**
- `books`: UUID PK, status enum (6 states), relationships
- `pages`: Per-page images, preprocessing config (JSONB)
- `ocr_results`: Raw text, bounding boxes (JSONB), corrected text, confidence
- `jobs`: Type/status enums, progress tracking, error logs
- `metadata`: 52+ fields as JSONB
- `llm_runs`: Prompts, batch config, raw/parsed responses
- `embeddings`: pgvector(768) for future semantic search

**Testing**
- Backend: 115 tests (unit + integration) using pytest, SQLite in-memory, mocked Celery
- Frontend: 14 component tests + 12 E2E tests (Playwright with MSW mocking)
- Operational scripts: E2E smoke test, OCR accuracy, LLM extraction, resumable workflow

**Documentation**
- README with 5-step quickstart
- User guide with workflow walkthrough
- Developer guide with architecture, extending, testing
- API reference for all endpoints

**Developer Tooling**
- Makefile with 14 development commands
- uv for Python dependency management
- Ruff + Black for Python linting/formatting
- ESLint + Prettier for frontend linting
- .env.example with all configuration variables

### Known Limitations

- CPU-only LLM inference (10-20 minutes per book, no GPU support)
- Telugu and Hindi only (MVP); additional languages require Tesseract pack installation
- No authentication or authorization (single-user local deployment)
- pgvector embeddings table exists but semantic search is not implemented
- 1 integration test skipped (requires PostgreSQL JSONB `.astext` operator)
- No book deletion endpoint
- No WebSocket/SSE support (polling only)

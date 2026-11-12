# Changelog — Indic Book Metadata Extractor

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

**Authentication & Roles**
- Email + password accounts with open self-registration, email verification (24 h token), and self-service password reset (1 h single-use token)
- Two roles (`user` / `admin`) with backend-enforced authorization on every book/page/job endpoint (owner or admin); first admin via `make create-admin`
- Personal dashboard (`/dashboard`): own books, own jobs, queue position (`queue_ahead`), cancel own queued/running jobs
- Admin user management (`/admin/users`): create, change role, activate/deactivate, reset password, delete — with self/last-admin/owns-books protections
- Admin books/jobs pages gained owner columns and a free-text owner filter; global stats include user counts
- Public catalog gating: anonymous and non-owner users see metadata-only book detail (`can_view_full`); only `complete`/`awaiting_review` books are listed; uploader display name is public, email is admin-only *(superseded by Moderated signup below — the public catalog was removed)*
- Job cancellation endpoint with owner/admin rules; book delete/reset/re-run endpoints now owner-scoped

**Moderated signup & access hardening**
- Approval-based registration: new accounts start `pending` and need admin approval; `REGISTRATION_REQUIRES_APPROVAL=false` re-enables open registration
- `POST /api/admin/users/{id}/approve` and `/reject` endpoints (reject accepts an optional reason, shown to the user); `account_status` filter on `GET /api/admin/users`; `pending_user_count` in `GET /api/admin/stats`
- Global `require_approved_user` gate on every application router; pending/rejected accounts get `403` (`account_pending` / `account_rejected`) and only `/api/auth/*` stays reachable
- `/pending-approval` holding screen and an admin pending-count badge in the nav

**Infrastructure**
- Alembic migration `012_auth_rbac`: `users` table, session refresh-token table, `books.owner_id` (non-nullable — refuses to run on databases that already contain books)
- Alembic migration `013_user_approval`: `users.account_status` (+ `status_reviewed_at`/`by_id`, `rejection_reason`); additive, backfills all existing rows to `approved`
- SMTP transactional email service (verification, password reset); with `SMTP_ENABLED=false` links are logged instead of sent
- Rate limiting on auth endpoints; CSRF (`X-CSRF-Token`) required on state-changing requests

### Changed
- **Breaking:** no anonymous or guest access — every page and API except `/api/auth/*` and `/health` now requires authentication, and the public catalog (anonymous `/library` and `/api/library/*`) is gone
- **Breaking:** registration is moderated by default (`REGISTRATION_REQUIRES_APPROVAL=true`). Deployments that do not set this variable will send new signups to a pending queue until an admin approves them; set it explicitly to `false` to keep open registration
- Library (`/library`) is admin-only and lists all books across users; regular users use the owner-scoped Dashboard
- Book detail and thumbnails are owner-or-admin only; a non-owner URL returns `404` (no metadata-only public view)
- Route convergence: the `/api/library/*` API is retired — the admin catalog is now `GET /api/admin/books` (+ `GET /api/admin/filters`) and book detail is `GET /api/books/{book_id}/detail`; dashboard/job routes are grouped under `/api/dashboard` (job cancellation is now `POST /api/dashboard/jobs/{job_id}/cancel`); the bulk-operations page moved from `/bulk-operations` to `/admin/bulk`

### Removed
- The public catalog: `PUBLIC_BOOK_STATUSES`, `get_visible_book_or_404`, and the anonymous metadata view are gone

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

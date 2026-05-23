# Developer Guide — Indic Book Metadata Extractor

## Architecture Overview

The application follows a 3-tier architecture with a background task processing layer:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                           │
│  Next.js 16 · React 19 · TypeScript · Tailwind CSS · shadcn/ui      │
│  React Query (server state) · Zustand (client state)                │
│  Konva.js (bounding boxes) · Fuse.js (client search)                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST API (Axios)
┌────────────────────────────────▼────────────────────────────────────┐
│                      Backend (FastAPI)                              │
│              Python 3.11 · Pydantic v2 · Uvicorn                    │
│              REST endpoints, file handling, job dispatch            │
└────────┬───────────────────────────────────────────┬────────────────┘
         │ Enqueue                                    │ Query / Write
┌────────▼────────┐                          ┌────────▼────────────────┐
│  Redis Broker   │                          │  PostgreSQL 16          │
│  + Result Store │                          │  pgvector · pg_trgm     │
└────────┬────────┘                          └─────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────────┐
│                       Celery Workers                                 │
│                                                                      │
│  ┌──────────────────┐         ┌─────────────────────────────────┐    │
│  │  OCR Pipeline    │         │       LLM Pipeline              │    │
│  │  PyMuPDF         │         │  Ollama (Airavata 7B)           │    │
│  │  OpenCV/Pillow   │         │  Instructor + Pydantic Schema   │    │
│  │  Tesseract 5+    │         │  Batched 52-field extraction    │    │
│  └──────────────────┘         └─────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │
┌────────▼────────┐
│  File Storage   │
│  (Local/S3)     │
└─────────────────┘
```

### Data Flow

```
PDF Upload → Save to disk → Create Book record
     → Page Selection → Render page images (PyMuPDF, 300 DPI)
     → Preprocessing → OpenCV pipeline (grayscale, binarize, deskew)
     → OCR (Tesseract) → Word-level bounding boxes + text
     → User corrections → Updated OCR text
     → LLM Extraction (Ollama/Instructor) → 8 batches × ~6 fields
     → Metadata Review → User edits → Final metadata record
     → Library (searchable via pg_trgm + Fuse.js)
```

---

## Local Development Setup (Without Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- Redis 7+
- Tesseract OCR with Indic language packs
- Ollama (for LLM inference)
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Backend Setup

```bash
cd backend

# Install Python dependencies
uv sync

# Set up environment variables
cp ../.env.example .env
# Edit .env to point to local services:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books
#   REDIS_URL=redis://localhost:6379/0
#   OLLAMA_URL=http://localhost:11434
#   STORAGE_PATH=./storage

# Run database migrations
uv run alembic upgrade head

# Start the backend server
uv run uvicorn app.main:app --reload --port 8000

# Start a Celery worker (separate terminal)
uv run celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

### Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install

# Configure API URL (defaults to http://localhost:8000)
# Create .env.local if needed:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the development server
npm run dev
```

### Installing Tesseract Language Packs

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin

# macOS
brew install tesseract tesseract-lang

# Verify installation
tesseract --list-langs
```

### Installing Ollama and Model

```bash
# Install Ollama (https://ollama.ai)
ollama pull airavata

# Verify
ollama list
```

---

## Project Structure

```
Indic-Book-Metadata-Extractor/
├── backend/                         # Python FastAPI backend
│   ├── alembic/                     # Database migrations
│   │   └── versions/                # Migration files (001-005)
│   ├── app/
│   │   ├── api/                     # REST API route handlers
│   │   │   ├── router.py            # API router aggregation
│   │   │   ├── books.py             # Book upload, pages, OCR dispatch
│   │   │   ├── pages.py             # Preprocessing, images, OCR CRUD
│   │   │   ├── extraction.py        # LLM extraction dispatch
│   │   │   ├── metadata.py          # Metadata CRUD, field definitions
│   │   │   └── library.py           # Search, filtering, book detail
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (env vars)
│   │   │   └── database.py          # Async SQLAlchemy engine
│   │   ├── models/                  # SQLAlchemy ORM models (7 tables)
│   │   │   ├── base.py              # Base, UUIDMixin, TimestampMixin
│   │   │   ├── book.py              # Book + BookStatus enum
│   │   │   ├── page.py              # Page (per-page images, config)
│   │   │   ├── ocr_result.py        # OcrResult (text, bounding boxes)
│   │   │   ├── job.py               # Job + JobType/JobStatus enums
│   │   │   ├── metadata.py          # BookMetadata (52 fields JSONB)
│   │   │   ├── llm_run.py           # LlmRun (prompts, responses)
│   │   │   └── embedding.py         # Embedding (pgvector, future)
│   │   ├── schemas/                 # Pydantic request/response models
│   │   │   ├── book.py              # Upload, page selection, list/detail
│   │   │   ├── page.py              # Preprocessing config, OCR results
│   │   │   ├── metadata.py          # 52 fields, 8 batches, extraction
│   │   │   └── job.py               # Job response
│   │   ├── services/                # Business logic layer
│   │   │   ├── pdf_service.py       # PyMuPDF: page count, render
│   │   │   ├── preprocessing.py     # OpenCV: grayscale, binarize, deskew
│   │   │   ├── ocr_service.py       # Tesseract: OCR with bounding boxes
│   │   │   ├── llm_service.py       # Ollama + Instructor: batched extraction
│   │   │   ├── search_service.py    # pg_trgm fuzzy search + filtering
│   │   │   ├── storage.py           # File path management
│   │   │   └── prompts.py           # Jinja2 prompt templates
│   │   └── tasks/                   # Celery background tasks
│   │       ├── celery_app.py        # Celery configuration
│   │       ├── ocr_tasks.py         # OCR pipeline tasks
│   │       └── llm_tasks.py         # LLM extraction tasks
│   ├── scripts/                     # Operational scripts
│   │   ├── e2e_smoke.py             # End-to-end smoke test
│   │   ├── test_ocr_pipeline.py     # OCR accuracy testing
│   │   ├── test_ocr_accuracy.py     # Batch OCR accuracy
│   │   ├── test_llm_extraction.py   # LLM extraction testing
│   │   └── test_resumable_workflow.py # Workflow state persistence
│   ├── storage/                     # File storage (uploads, pages, etc.)
│   ├── tests/                       # Test suite
│   │   ├── conftest.py              # Fixtures (SQLite test DB, mock Celery)
│   │   ├── unit/                    # Unit tests (services, schemas)
│   │   └── integration/             # Integration tests (API endpoints)
│   ├── pyproject.toml               # Python dependencies (uv)
│   └── alembic.ini                  # Alembic configuration
├── frontend/                        # Next.js frontend
│   ├── src/
│   │   ├── app/                     # Next.js App Router pages
│   │   │   ├── page.tsx             # Home page
│   │   │   ├── upload/              # Step 1: PDF Upload
│   │   │   ├── books/[bookId]/      # Steps 2-6: Workflow pages
│   │   │   │   ├── select-pages/
│   │   │   │   ├── preprocessing/
│   │   │   │   ├── ocr-review/
│   │   │   │   ├── llm-config/
│   │   │   │   ├── metadata-review/
│   │   │   │   └── jobs/
│   │   │   └── library/             # Step 7: Library & Search
│   │   ├── components/
│   │   │   ├── ocr/                 # Bounding box canvas, text editor
│   │   │   ├── metadata/            # 52-field metadata form
│   │   │   ├── library/             # Book card component
│   │   │   └── shared/              # Stepper, sliders, badges, skeletons
│   │   ├── hooks/                   # use-job-polling
│   │   ├── lib/                     # API client, Fuse.js, error handler
│   │   └── stores/                  # Zustand stores (workflow, book)
│   ├── tests/                       # Vitest component tests
│   ├── e2e/                         # Playwright E2E tests
│   └── package.json
├── docker/                          # Docker configurations
│   ├── Dockerfile.backend           # Backend + worker image
│   ├── Dockerfile.frontend          # Next.js production build
│   ├── Dockerfile.worker            # Celery worker (same as backend)
│   ├── ollama-entrypoint.sh         # Auto-pull Airavata on start
│   └── postgres/                    # Init SQL (pgvector extension)
├── docs/                            # Documentation
├── docker-compose.yml               # 7-service orchestration
├── Makefile                         # Development commands
├── .env.example                     # Environment template
└── .gitignore
```

---

## Database Schema

### Entity-Relationship Diagram

```
books ──1:N──> pages ──1:1──> ocr_results
  │
  ├──1:N──> jobs ──1:N──> llm_runs
  │
  ├──1:1──> metadata
  │
  └──1:N──> embeddings (future)
```

### Tables

#### `books`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| title | VARCHAR(500) | Optional user-provided title |
| filename | VARCHAR(500) | Original upload filename |
| language | VARCHAR(10) | "tel" or "hin" |
| status | VARCHAR(30) | uploaded → pages_selected → ocr_running → ocr_complete → llm_running → complete |
| total_pages | INTEGER | Page count from PyMuPDF |
| created_at | TIMESTAMPTZ | Auto-set |
| updated_at | TIMESTAMPTZ | Auto-updated |

#### `pages`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| book_id | UUID (FK → books) | Parent book |
| page_number | INTEGER | 1-indexed page number |
| image_path | VARCHAR(500) | Relative path to rendered page image |
| processed_image_path | VARCHAR(500) | Relative path to preprocessed image |
| preprocessing_config | JSONB | Per-page preprocessing settings |

#### `ocr_results`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| page_id | UUID (FK → pages, UNIQUE) | One OCR result per page |
| raw_text | TEXT | Raw Tesseract output |
| bounding_boxes | JSONB | `{words: [{text, confidence, bbox, block_num, line_num, word_num}]}` |
| corrected_text | TEXT | User-corrected text |
| confidence | FLOAT | Average confidence score |
| language_detected | VARCHAR(10) | Auto-detected language code |
| created_at | TIMESTAMPTZ | Auto-set |
| updated_at | TIMESTAMPTZ | Auto-updated |

#### `jobs`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| book_id | UUID (FK → books, nullable) | NULL if book deleted |
| job_type | VARCHAR(20) | "ocr", "llm", or "preprocessing" |
| status | VARCHAR(20) | queued → running → completed / failed / cancelled |
| progress | FLOAT | 0.0 to 1.0 |
| created_at | TIMESTAMPTZ | Auto-set |
| started_at | TIMESTAMPTZ | When processing began |
| completed_at | TIMESTAMPTZ | When processing finished |
| error_log | TEXT | Error details on failure |

#### `metadata`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| book_id | UUID (FK → books, UNIQUE) | One metadata record per book |
| fields | JSONB | All 52+ metadata key-value pairs |
| created_at | TIMESTAMPTZ | Auto-set |
| updated_at | TIMESTAMPTZ | Auto-updated |

#### `llm_runs`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| job_id | UUID (FK → jobs) | Parent job |
| model | VARCHAR(100) | Model name (e.g., "airavata") |
| prompt_template | TEXT | Prompt used for extraction |
| batch_config | JSONB | Batch configuration |
| raw_response | TEXT | Raw LLM output |
| parsed_fields | JSONB | Successfully parsed fields |
| created_at | TIMESTAMPTZ | Auto-set |

#### `embeddings`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| book_id | UUID (FK → books) | Parent book |
| embedding | VECTOR(768) | pgvector embedding (future use) |
| source_text | TEXT | Text used to generate embedding |
| created_at | TIMESTAMPTZ | Auto-set |

### Migrations

Run `make migrate` or `uv run alembic upgrade head`. Migrations:

| # | Description |
|---|-------------|
| 001 | Initial schema (7 tables, basic indexes) |
| 002 | Add `total_pages` column to books |
| 003 | LLM-related indexes (jobs, metadata, llm_runs, ocr_results) |
| 004 | pg_trgm GIN indexes for search (title, filename, JSONB fields) |
| 005 | Performance indexes (status, language, created_at, book_id) |

---

## How to Add a Metadata Field

1. **Define the field** in `backend/app/schemas/metadata.py`:
   - Add to the appropriate batch Pydantic model (e.g., `CoreIdentityBatch`)
   - Add to `FullMetadata`
   - Add to `FIELD_WIKIDATA` (with Wikidata property or `None`)
   - Add to `FIELD_DISPLAY_NAMES`

2. **Update prompts** in `backend/app/services/prompts.py`:
   - The field will automatically appear in batch extraction prompts via `METADATA_BATCHES`

3. **Update the frontend form** in `frontend/src/components/metadata/metadata-form.tsx`:
   - The field will automatically appear based on field definitions from the API

4. **No database migration needed** — metadata fields are stored in a JSONB column

---

## How to Add a Language

1. **Install Tesseract language pack** in `docker/Dockerfile.backend`:
   ```dockerfile
   RUN apt-get install -y tesseract-ocr-tam  # For Tamil
   ```

2. **Update OCR service** in `backend/app/services/ocr_service.py`:
   - Add the language code to `LANGUAGE_MAP`:
     ```python
     LANGUAGE_MAP = {
         "tel": "tel+eng",
         "hin": "hin+eng",
         "tam": "tam+eng",  # Add this
     }
     ```

3. **Update upload validation** in `backend/app/api/books.py`:
   - Add the language code to the accepted values:
     ```python
     if language not in ("tel", "hin", "tam"):
     ```

4. **Update prompts** in `backend/app/services/prompts.py`:
   - Add the language name to `LANGUAGE_NAMES`

5. **Update frontend** in `frontend/src/app/upload/page.tsx`:
   - Add the language option to the dropdown

---

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest tests/ -v

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests
uv run pytest tests/integration/ -v

# Run with coverage
uv run pytest tests/ -v --cov=app --cov-report=html

# Run a specific test file
uv run pytest tests/unit/test_ocr_service.py -v
```

**Test infrastructure**: Tests use SQLite in-memory with JSONB patched to JSON. Celery tasks are mocked. Fixtures in `conftest.py` provide test clients, sample PDFs, and helper factories.

**Note**: 1 test (`test_get_filter_options`) is skipped because it requires PostgreSQL's JSONB `.astext` operator. Run against the Docker stack for full validation.

### Frontend Tests

```bash
cd frontend

# Run component/unit tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests (requires full stack running)
npm run test:e2e

# Run E2E with UI
npm run test:e2e:ui
```

### Operational Scripts

```bash
# End-to-end smoke test
make test-e2e PDF=path/to/test.pdf

# OCR accuracy testing
docker compose exec backend uv run python scripts/test_ocr_pipeline.py --image path/to/image.png

# LLM extraction testing
docker compose exec backend uv run python scripts/test_llm_extraction.py --mode full

# Workflow resumability test
docker compose exec backend uv run python scripts/test_resumable_workflow.py
```

---

## Docker Compose Deep-Dive

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | pgvector/pgvector:pg16 | 5432 | Primary database with pgvector extension |
| `redis` | redis:7-alpine | 6379 | Celery message broker + result backend |
| `ollama` | ollama/ollama:latest | 11434 | LLM inference server (auto-pulls Airavata) |
| `backend` | Custom (backend/) | 8000 | FastAPI application |
| `worker` | Custom (backend/) | — | Celery worker (shares backend image) |
| `frontend` | Custom (frontend/) | 3000 | Next.js application |
| `flower` | mher/flower:latest | 5555 | Celery monitoring dashboard |

### Health Checks

- `postgres`: `pg_isready` every 5s
- `redis`: `redis-cli ping` every 5s
- `ollama`: `curl /api/tags` every 10s, 60s start period (model loading)
- `backend` and `worker` depend on all three being healthy

### Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| `pgdata` | `/var/lib/postgresql/data` | PostgreSQL data persistence |
| `redis_data` | `/data` | Redis persistence |
| `ollama_data` | `/root/.ollama` | Downloaded LLM models (~4 GB) |
| `./backend/storage` | `/app/storage` | Uploaded PDFs and rendered images |

### Scaling Workers

```bash
# Run 3 Celery workers
docker compose up -d --scale worker=3
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Celery over Dramatiq** | Mature ecosystem, better monitoring (Flower), Redis integration |
| **pg_trgm + Fuse.js** | Server-side fuzzy search (PostgreSQL) + instant client-side filtering (no network latency) |
| **Instructor for LLM output** | Guarantees Pydantic-validated JSON from Ollama, with automatic retries |
| **Batched field extraction** | 52 fields in one prompt degrades accuracy; 8 batches of ~6 fields each balances speed vs quality |
| **JSONB for metadata** | Flexible schema — no migration needed when adding/removing fields |
| **SQLite for unit tests** | Fast, no external dependency; JSONB→JSON patching handles compatibility |
| **Zustand with persist** | Workflow state survives page refreshes; server hydration on return |

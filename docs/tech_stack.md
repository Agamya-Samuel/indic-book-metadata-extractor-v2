# Tech Stack — Indic Book Metadata Extractor

---

## 1. Frontend

| Technology | Version | Role | Why |
|---|---|---|---|
| **Next.js** | 14+ (App Router) | UI Framework | SSR + SSG, file-based routing, API routes for lightweight BFF calls |
| **TypeScript** | 5+ | Language | Type safety across the entire frontend codebase |
| **Tailwind CSS** | 3+ | Styling | Utility-first; pairs perfectly with shadcn component system |
| **shadcn/ui** | Latest | Component Library | Unstyled, accessible, highly customizable Radix-based components |
| **React Query (TanStack)** | 5+ | Server State | Polling for job status updates; caching API responses |
| **Zustand** | 4+ | Client State | Lightweight global state for multi-step workflow (page selections, settings) |
| **React Dropzone** | Latest | File Upload UI | Drag-and-drop PDF upload with file validation |
| **Konva.js / react-konva** | Latest | Canvas / Bounding Boxes | Render bounding box overlays on page images (OCR review step) |
| **Fuse.js** | Latest | Client-side Fuzzy Search | Instant fuzzy search on the library page before hitting the DB |
| **Axios** | Latest | HTTP Client | API communication with FastAPI backend |

---

## 2. Backend

| Technology | Version | Role | Why |
|---|---|---|---|
| **Python** | 3.11 | Language | Dominant ecosystem for AI, OCR, and data processing |
| **FastAPI** | 0.111+ | Web Framework | Async-first, automatic OpenAPI docs, excellent file upload handling |
| **Pydantic** | v2 | Data Validation | Request/response schema enforcement; also used for LLM output parsing |
| **Uvicorn** | Latest | ASGI Server | High-performance async server for FastAPI |
| **Python-Multipart** | Latest | File Handling | Multipart form-data parsing for PDF uploads |
| **Instructor** | Latest | Structured LLM Output | Forces LLM to return valid, schema-compliant JSON every time |
| **python-dotenv** | Latest | Config Management | Environment variable loading for secrets and service URLs |

---

## 3. Task Queue & Background Processing

| Technology | Version | Role | Why |
|---|---|---|---|
| **Celery** | 5+ | Task Queue | Distributes OCR and LLM jobs across workers asynchronously |
| **Redis** | 7+ | Message Broker + Result Backend | Fast in-memory broker for Celery; stores job results and status |
| **Flower** | Latest | Celery Monitoring UI | Real-time dashboard to monitor task queues and worker health |

**Task Flow:**

```
PDF Upload → FastAPI → Redis Queue → Celery Worker
                                          │
                         ┌────────────────┼─────────────────┐
                         ▼                ▼                 ▼
                   Page Extraction    OCR (Tesseract)   LLM Inference (Ollama)
                         │                │                 │
                         └────────────────┴─────────────────┘
                                          │
                                    PostgreSQL
```

---

## 4. PDF Processing & Image Pre-processing

| Technology | Version | Role | Why |
|---|---|---|---|
| **PyMuPDF (fitz)** | 1.24+ | PDF Parsing | Fastest Python PDF library; extracts specific pages and renders them as images |
| **Pillow (PIL)** | 10+ | Image Manipulation | Brightness, contrast, grayscale, resize adjustments |
| **OpenCV (cv2)** | 4.9+ | Advanced Image Processing | Binarization (Otsu/adaptive), deskew, noise reduction for scanned images |
| **NumPy** | Latest | Array Operations | Underpins OpenCV operations |
| **img2pdf** | Latest | Image to PDF Round-trip | Re-packages processed images back to PDF if needed |

**Pre-processing Pipeline per Page:**

```
Raw PDF Page
    → PyMuPDF renders to high-DPI image (300 DPI recommended)
    → Pillow: grayscale conversion, brightness/contrast
    → OpenCV: adaptive binarization, deskew, denoise
    → Processed image saved to disk
    → Passed to Tesseract
```

---

## 5. OCR Engine

| Technology | Version | Role | Why |
|---|---|---|---|
| **Tesseract OCR** | 5+ | OCR Engine | Industry standard; supports 100+ languages including all major Indic scripts |
| **pytesseract** | Latest | Python Wrapper | Simple Python interface to Tesseract binary |

**Indic Language Packs (`.traineddata` files to install):**

| Language | Pack | Script |
|---|---|---|
| Hindi | `hin` | Devanagari |
| Tamil | `tam` | Tamil |
| Telugu | `tel` | Telugu |
| Kannada | `kan` | Kannada |
| Malayalam | `mal` | Malayalam |
| Marathi | `mar` | Devanagari |
| Bengali | `ben` | Bengali |
| Gujarati | `guj` | Gujarati |
| Punjabi | `pan` | Gurmukhi |
| Odia | `ori` | Odia |
| English | `eng` | Latin (for bilingual pages) |

**OCR Output:** `pytesseract.image_to_data()` returns word-level bounding boxes (x, y, w, h, confidence, text) as a structured dataframe — used directly to render the bounding box overlay in the UI.

---

## 6. LLM Inference

| Technology | Version | Role | Why |
|---|---|---|---|
| **Ollama** | Latest | Local LLM Inference Server | Exposes an OpenAI-compatible API; manages model loading, memory, and CPU inference |
| **Instructor** | Latest | Output Enforcement | Wraps Ollama's API to guarantee Pydantic-validated JSON output |
| **Pydantic** | v2 | Schema Definition | Defines the exact 52-field metadata schema the LLM must populate |

**Recommended Models (selectable per job):**

| Model | Parameters | Best For | RAM Required |
|---|---|---|---|
| **Airavata (AI4Bharat)** | 7B | All Indic languages — purpose-fine-tuned | ~8 GB |
| **Gemma-2-9B-Instruct** | 9B | Hindi, general multilingual | ~10 GB |
| **Llama-3-8B-Instruct** | 8B | Hindi, English, multilingual | ~8 GB |
| **Kan-Llama** | 7B | Low-RAM deployments | ~5 GB |

**Batched Field Extraction Strategy:**

Since extracting all 52 fields in a single prompt degrades accuracy, fields are grouped into configurable batches:

```
52 fields ÷ n fields per prompt = ceil(52/n) sequential LLM calls
```

Each call receives the same OCR text but targets a different subset of fields, then results are merged into a single metadata record.

---

## 7. Database

| Technology | Version | Role | Why |
|---|---|---|---|
| **PostgreSQL** | 16 | Primary Database | Robust relational DB for all structured data |
| **pgvector** | 0.7+ | Vector Search Extension | Stores text embeddings for future semantic/similarity search |
| **pg_trgm** | Built-in | Fuzzy Text Search | Trigram-based similarity for fuzzy search across metadata fields |
| **SQLAlchemy** | 2+ | ORM | Async-compatible Python ORM for database models |
| **Alembic** | Latest | Database Migrations | Schema versioning and migrations |

**Core Database Schema:**

```sql
books          -- One record per uploaded PDF
pages          -- One record per selected page (image path, pre-processing config)
ocr_results    -- Raw OCR text, bounding box JSON, user corrections, per page
jobs           -- Job ID, status, type (OCR/LLM), timestamps, error logs
metadata       -- All 52+ fields as JSONB + key columns indexed individually
llm_runs       -- Prompt used, model, batch config, raw response, per run
embeddings     -- pgvector: book description/text embeddings for semantic search
```

---

## 8. File Storage

| Technology | Role | Why |
|---|---|---|
| **Local Filesystem / S3-compatible** | Store uploaded PDFs, rendered page images, processed images | PDFs and images are large binary assets; keep out of the database |
| **MinIO** (self-hosted S3) | Object storage for cloud deployment | S3-compatible API; swap to AWS S3 without code changes |

---

## 9. Infrastructure & Deployment

| Technology | Role | Why |
|---|---|
| **Docker** | Containerisation | Each service (FastAPI, Celery Worker, Redis, PostgreSQL, Ollama) runs in its own container |
| **Docker Compose** | Local orchestration | Single `docker-compose.yml` to spin up the full stack locally |
| **uv** | Python environment management | Fast Python project and dependency management for local development |
| **Node.js + npm/pnpm** | Frontend environment | Package management for Next.js application |

**Docker Services:**

```yaml
services:
  frontend        # Next.js app
  backend         # FastAPI + Uvicorn
  worker          # Celery worker(s) — scale horizontally
  redis           # Message broker
  postgres        # Primary DB
  ollama          # LLM inference server
  flower          # Queue monitoring (optional)
  backup          # Daily PostgreSQL backups
  wikibase        # Structured data store (MediaWiki + Wikibase extension)
  mysql           # MariaDB — Wikibase database backend
  elasticsearch   # Wikibase search index (CirrusSearch)
  openrefine      # Bulk data cleaning GUI
```

---

## 10. Monitoring & Observability

| Technology | Role | Why |
|---|---|---|
| **New Relic APM** | Application performance monitoring | End-to-end distributed tracing across FastAPI, Celery, and Next.js |
| **New Relic Browser** | Real user monitoring (RUM) | Page load timing, Core Web Vitals, JS errors, session traces |
| **New Relic Infrastructure** | Host and container metrics | CPU, memory, disk, Docker events for all containers |
| **Flower** | Celery queue monitoring UI | Real-time dashboard for task queues and worker health |

**New Relic Architecture — 3 Agents:**

```
┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────────────┐
│    APM Agent          │  │    Browser Agent       │  │    Infra Agent        │
│    (in Python/JS code)│  │    (JS snippet in HTML)│  │    (Docker sidecar)   │
│                       │  │                        │  │                       │
│    → App performance  │  │    → Page loads, AJAX  │  │    → Host/container   │
│    → DB queries       │  │    → JS errors         │  │    → CPU/mem/disk     │
│    → External calls   │  │    → Session traces    │  │    → Docker events    │
└──────────┬────────────┘  └──────────┬─────────────┘  └──────────┬────────────┘
           │                          │                           │
           └──────────────────────────┼───────────────────────────┘
                                      ▼
                          New Relic Cloud (SaaS)
```

All telemetry is sent to **New Relic Cloud (SaaS)** — nothing is self-hosted. The `newrelic-infra` Docker container is a lightweight sidecar collector, not a self-hosted New Relic server. See [monitoring.md](monitoring.md) for the full setup guide.

---

## 11. Wikibase (Structured Data Store)

| Technology | Version | Role | Why |
|---|---|---|---|
| **Wikibase** | mw1.44.0 | Structured data store | The software behind Wikidata — stores bibliographic metadata as linked entities with properties |
| **MediaWiki** | 1.44.0 | Wiki engine (bundled with Wikibase) | Provides the web interface, API, user management, and extension framework |
| **MariaDB** | 10.11 | Wikibase database backend | MySQL-compatible DB for MediaWiki/Wikibase tables |
| **Elasticsearch** | 7.x | Search index | CirrusSearch extension for full-text search across Wikibase items |

**What is Wikibase?**

Wikibase is a MediaWiki extension that adds structured data capabilities on top of MediaWiki. The Docker image `wikibase/wikibase:mw1.44.0` bundles both MediaWiki and the Wikibase extension pre-installed and pre-configured. On container startup, the entrypoint script generates extension configs into `LocalSettings.d/` which are loaded by the glob in `LocalSettings.php`.

```
wikibase/wikibase Docker image
├── MediaWiki 1.44.0          (wiki engine)
├── Wikibase Extension         (structured data: items, properties, statements)
├── CirrusSearch               (Elasticsearch integration)
├── Other bundled extensions   (loaded from LocalSettings.d/*.php at runtime)
```

**Architecture:**

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────────┐
│  Wikibase       │────→│  MariaDB     │     │  Elasticsearch    │
│  (MediaWiki +   │     │  :3306       │     │  :9200            │
│   Wikibase ext) │     │  (wiki DB)   │     │  (search index)   │
│  :8181          │     └──────────────┘     └───────────────────┘
└─────────────────┘
```

**Configuration:**

| File | Purpose |
|---|---|
| `docker/wikibase/config/LocalSettings.php` | Base MediaWiki config (DB, site name, logging, Elasticsearch host) |
| `LocalSettings.d/*.php` | Extension configs — auto-generated by the Docker entrypoint at runtime |

---

## 12. OpenRefine (Bulk Data Cleaning)

| Technology | Version | Role | Why |
|---|---|---|---|
| **OpenRefine** | Latest | Bulk data cleaning GUI | Web-based tool for cleaning, transforming, and reconciling messy tabular data |
| **Custom Docker image** | — | Pre-configured OpenRefine | Built from `docker/openrefine/Dockerfile` with project-specific settings |

**Role in this project:**

OpenRefine sits between the backend database and Wikibase. After extracting metadata from books, users can:

1. Export metadata to OpenRefine for bulk cleaning (normalise authors, fix transliterations, deduplicate publishers)
2. Reconcile entities against Wikibase (match extracted names to existing items)
3. Export cleaned data as QuickStatements TSV for upload to Wikibase

**Data flow:**

```
PostgreSQL (books) → Export CSV → OpenRefine (clean/reconcile) → Wikibase (upload)
```

---

## 13. Developer Tooling

| Technology | Role |
|---|---|
| **uv** | Python project manager, package manager, and virtual environment manager (replaces pyenv + venv + pip) |
| **ESLint + Prettier** | Frontend linting and formatting |
| **Ruff** | Python linting (faster than flake8) |
| **Black** | Python code formatting |
| **pytest** | Backend unit and integration tests |
| **Vitest / Playwright** | Frontend unit and E2E tests |
| **pre-commit hooks** | Enforce linting/formatting before every commit |

**Python Environment Setup with uv:**

```bash
# Install uv (https://github.com/astral-sh/uv)
pip install uv

# Create Python 3.11 project with uv
uv init --python 3.11

# Add dependencies from pyproject.toml
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

---

## Summary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (User)                           │
│          Next.js 14 · TypeScript · Tailwind · shadcn/ui         │
│          React Query · Zustand · Konva.js · Fuse.js             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS via Nginx
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend                             │
│              Python 3.11 · Pydantic v2 · Uvicorn                │
└────────┬───────────────────────────────────────┬────────────────┘
         │ Enqueue Jobs                           │ Query / Write
┌────────▼────────┐                    ┌──────────▼──────────────┐
│  Redis Broker   │                    │  PostgreSQL 16          │
│  + Result Store │                    │  pgvector · pg_trgm     │
└────────┬────────┘                    └─────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                    Celery Workers                                │
│                                                                  │
│  ┌──────────────────┐    ┌────────────────────────────────────┐  │
│  │  OCR Pipeline    │    │       LLM Pipeline                 │  │
│  │  PyMuPDF         │    │  Ollama (Airavata / Gemma / LLaMA) │  │
│  │  OpenCV · Pillow │    │  Instructor · Pydantic Schema      │  │
│  │  Tesseract 5+    │    │  Batched 52-field extraction       │  │
│  └──────────────────┘    └────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
         │
┌────────▼────────┐        ┌─────────────────────┐
│  MinIO / S3     │        │  OpenRefine (:3333) │
│  (PDF + Images) │        │  Bulk data cleaning │
└─────────────────┘        └────────┬────────────┘
                                    │ Export/Reconcile
                           ┌────────▼─────────────┐
                           │  Wikibase (:8181)    │
                           │  MediaWiki + WB ext  │
                           │  MariaDB + Elastic   │
                           └──────────────────────┘
```

---

> **Local development target:** CPU-only local environment using Docker Compose for services and uv for Python environment management. Scale by adding more Celery worker replicas. Ollama handles CPU-based inference natively.

# Indic Book Metadata Extractor

A full-stack web application for OCR-powered metadata extraction from scanned Indic language book PDFs. Upload a PDF, run Tesseract OCR, extract 49 bibliographic fields using a locally-hosted LLM, and review/edit everything through a guided 7-step workflow.

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with WSL2 backend on Windows)
- **16 GB RAM** (LLM inference requires ~8 GB)
- **10 GB disk** (Docker images + model weights)
- OS: Windows 10/11, macOS, or Linux

### 5-Step Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd Indic-Book-Metadata-Extractor

# 2. Configure environment
cp .env.example .env

# 3. Start all services (7 Docker containers)
make up

# 4. Wait for services to be healthy (~60s on first run for Ollama model download)
make status

# 5. Open the application
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000/docs  (Swagger API docs)
# Flower:    http://localhost:5555       (Celery monitoring)
```

That's it. Upload a Telugu or Hindi PDF and follow the guided workflow.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Next.js Frontend (:3000)           │
│     Upload → Page Select → Preprocessing →      │
│     OCR Review → LLM Config → Metadata Review   │
└──────────────────────┬──────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────┐
│             FastAPI Backend (:8000)             │
│     File handling, Job management, API          │
└──────┬──────────────────────────────┬───────────┘
       │                              │
┌──────▼──────┐              ┌────────▼─────────┐
│ Celery +    │              │  Ollama (:11434) │
│ Redis Queue │              │  Airavata 7B LLM │
└──────┬──────┘              └──────────────────┘
       │
┌──────▼───────────────────────────────────────────┐
│          PostgreSQL + pgvector (:5432)           │
│   Books, Pages, OCR Text, Metadata, Jobs         │
└──────────────────────────────────────────────────┘
```

**8 Docker services**: `postgres`, `redis`, `backend`, `worker-ocr`, `worker-llm`, `frontend`, `ollama`, `flower`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Task Queue | Celery 5, Redis 7 |
| PDF Processing | PyMuPDF |
| Image Preprocessing | OpenCV, Pillow |
| OCR Engine | Tesseract 5+ (with Indic language packs) |
| LLM Inference | Ollama, Instructor (structured output) |
| Database | PostgreSQL 16, pgvector, pg_trgm |
| Search | pg_trgm (server) + Fuse.js (client) |

---

## Workflow

The application guides users through a 7-step pipeline:

1. **Upload** — Drag-and-drop PDF upload with language selection (Telugu/Hindi)
2. **Page Selection** — Choose front/back pages for processing via thumbnail grid
3. **Preprocessing** — Tune image settings (grayscale, brightness, contrast, binarization, deskew)
4. **OCR Review** — Side-by-side view with bounding box overlay and text correction editor
5. **LLM Configuration** — Select model, tune parameters, edit prompts, run batched extraction
6. **Metadata Review** — Review and edit 52 extracted bibliographic fields
7. **Library** (admin) — Browse, search, and filter all processed books across users

---

## Accounts & Access

The app requires authentication for every page and API except signup, login,
email verification, and password reset. There is **no anonymous or guest
access**. Cookie-based sessions with two roles:

- **Registration is moderated.** A new account must verify its email and then be
  **approved by an admin** before it can use the app. Until then the user can log
  in but only reaches an "awaiting approval" holding screen; a rejected account
  sees a "registration not approved" screen (with the reason, if any). Set
  `REGISTRATION_REQUIRES_APPROVAL=false` to re-enable open registration.
- **Users** see a personal dashboard (`/dashboard`) with their books, jobs, and
  queue position, and can only reach books they uploaded. Any other book URL,
  thumbnail, page, or metadata request returns 404.
- **Admins** additionally see the **Library** (`/library`), which lists all books
  from all users, plus all jobs with an owner filter. They approve/reject pending
  accounts at `/admin/users` (which shows an approval status filter and a
  pending-count badge in the nav), manage users (create, change role, activate/
  deactivate, reset password, delete), and can operate any book or job.
- **The first admin** is created via the CLI (no admin can self-register):

  ```sh
  make create-admin EMAIL=admin@example.com DISPLAY_NAME="Admin"
  # Password is prompted for when omitted.
  ```

  Run this once after the first `make up` / `make migrate`.

Email delivery (verification, password resets) requires SMTP configuration —
see [DEPLOY.md](DEPLOY.md) and `.env.example` for the variables.

---

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services (detached) |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make build` | Build all Docker images |
| `make rebuild` | Rebuild images (no cache) and restart |
| `make status` | Show status of all services |
| `make logs` | Tail logs for all services |
| `make logs-backend` | Tail backend logs |
| `make logs-worker-ocr` | Tail OCR worker logs |
| `make logs-worker-llm` | Tail LLM worker logs |
| `make migrate` | Run database migrations |
| `make reset-db` | Reset database (destroys data!) |
| `make create-admin` | Create the first administrator (`EMAIL=... DISPLAY_NAME=... [PASSWORD=...]`) |
| `make download-model` | Download Airavata model to Ollama |
| `make test-e2e` | Run E2E smoke test |
| `make shell-backend` | Open shell in backend container |
| `make clean` | Remove containers, volumes, and images |

---

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/user-guide.md) | Step-by-step walkthrough with screenshots |
| [Developer Guide](docs/developer-guide.md) | Architecture, local dev setup, extending the app |
| [API Reference](docs/api-reference.md) | Complete REST API documentation |
| [Changelog](docs/changelog.md) | Release notes and version history |
| [Implementation Plan](docs/implementation_plan.md) | Original 12-week development plan |
| [Tech Stack](docs/tech_stack.md) | Detailed technology choices and rationale |
| [Product Spec](docs/indic_book_metadata_extractor.md) | Full product specification |

---

## Metadata Fields (49)

The application extracts 49 bibliographic fields per book, grouped into 8 batches:

| Batch | Fields |
|-------|--------|
| Core Identity | Label, Author, Description (Work/Edition), Language, ISBN, Title, Subtitle |
| Contributors | Translator, Editor, Compiler, Cover Artist, Designer, Typesetter |
| Publication | Date, Publisher, Place, Printer, Distributor, Sponsor |
| Content Classification | Form, Genre, Subject, Inception, Context, Awards |
| Edition & Series | Volume, Edition Number, Series, Serial Number, Set |
| Relationships | Based On, Inspired By, First Published In |
| Ancillary Content | Dedication, Forewords, Abbreviations, Authors in Compilation |
| Physical & Extra | Pages, Illustrators, Custom Fields |

All fields are mapped to Wikidata properties where applicable.

---

## Known Limitations

- **CPU-only inference**: LLM extraction takes 10-20 minutes per book on CPU (no GPU required)
- **Languages**: MVP supports Telugu and Hindi; additional Indic languages require Tesseract packs
- **OCR accuracy**: Tesseract accuracy on Indic scripts varies; the OCR review step is essential
- **No per-user quotas**: any registered user can upload unlimited books and run unlimited jobs
- **SMTP dependency**: email verification and password resets need SMTP (`SMTP_ENABLED=true` + credentials in production). Without SMTP the links are logged to the backend log instead — workable locally, not for real users
- **Rate limiting**: request rate limits exist only on the auth endpoints, not on upload/job endpoints
- **pgvector embeddings**: Schema exists but semantic search is not yet implemented
- **1 test skipped**: Library filter options test requires PostgreSQL (not compatible with SQLite test runner)

---

## License

This project is developed for the Open Knowledge Institute (OKI).

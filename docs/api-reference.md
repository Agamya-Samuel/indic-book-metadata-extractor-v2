# API Reference — Indic Book Metadata Extractor

**Base URL**: `http://localhost:8000/api`

**Content-Type**: `application/json` (unless otherwise specified)

**Auto-generated docs**: Interactive Swagger UI available at `http://localhost:8000/docs`

---

## Overview

### Authentication

None. The application is designed for single-user local deployment.

### Pagination

List endpoints support pagination with these query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `page_size` | integer | 20 | Items per page (max: 100) |

### Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid state, missing data) |
| 404 | Resource not found |
| 409 | Conflict (duplicate operation) |
| 413 | File too large |
| 422 | Validation error |

---

## Health Check

### `GET /health`

Returns application health status.

**Response**:
```json
{
  "status": "ok"
}
```

---

## Books API

### Upload a PDF

```
POST /api/books/upload
```

Upload a PDF file for processing. Creates a book record and analyzes page count.

**Content-Type**: `multipart/form-data`

**Parameters**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | File | Yes | — | PDF file (max 200 MB) |
| `title` | string | No | null | Optional book title |
| `language` | string | No | "tel" | Language code: "tel" or "hin" |

**Response** (`201 Created`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "book.pdf",
  "title": "My Telugu Book",
  "language": "tel",
  "total_pages": 250,
  "status": "uploaded",
  "created_at": "2026-05-23T01:30:00Z"
}
```

---

### Get Book Details

```
GET /api/books/{book_id}
```

**Response** (`200 OK`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "book.pdf",
  "title": "My Telugu Book",
  "language": "tel",
  "total_pages": 250,
  "status": "pages_selected",
  "created_at": "2026-05-23T01:30:00Z",
  "updated_at": "2026-05-23T01:35:00Z"
}
```

---

### Get Page Thumbnail

```
GET /api/books/{book_id}/pages/{page_number}/thumbnail
```

Returns a JPEG thumbnail (180px wide) for the specified page. Generates on-demand if not cached.

**Response**: JPEG image file.

---

### Select Pages for Processing

```
POST /api/books/{book_id}/pages
```

Select which pages to process. Renders high-resolution images (300 DPI) for each selected page.

**Request Body**:
```json
{
  "selected_pages": [1, 2, 3, 4, 5, 248, 249, 250]
}
```

**Response** (`200 OK`):
```json
{
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "selected_count": 8,
  "status": "pages_selected"
}
```

---

### List Pages

```
GET /api/books/{book_id}/pages
```

**Response** (`200 OK`):
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "page_number": 1,
    "image_path": "pages/550e.../page_001.png",
    "preprocessing_config": null
  }
]
```

---

### Dispatch OCR Job

```
POST /api/books/{book_id}/run-ocr
```

Creates an OCR job and dispatches it to the Celery worker. Book status must be `pages_selected` or `ocr_complete`.

**Response** (`201 Created`):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_type": "ocr",
  "status": "queued",
  "progress": 0.0,
  "created_at": "2026-05-23T02:00:00Z",
  "started_at": null,
  "completed_at": null,
  "error_log": null
}
```

---

### Get OCR Status

```
GET /api/books/{book_id}/ocr-status
```

Returns per-page OCR completion status and average confidence.

**Response** (`200 OK`):
```json
{
  "total_pages": 8,
  "ocr_complete_count": 8,
  "ocr_pending_count": 0,
  "avg_confidence": 78.5,
  "pages": [
    {
      "page_number": 1,
      "page_id": "660e8400-...",
      "has_ocr": true,
      "confidence": 82.0
    }
  ]
}
```

---

### List Jobs for a Book

```
GET /api/books/{book_id}/jobs
```

**Response** (`200 OK`):
```json
[
  {
    "id": "770e8400-...",
    "book_id": "550e8400-...",
    "job_type": "ocr",
    "status": "completed",
    "progress": 1.0,
    "created_at": "2026-05-23T02:00:00Z",
    "started_at": "2026-05-23T02:00:01Z",
    "completed_at": "2026-05-23T02:01:30Z",
    "error_log": null
  }
]
```

---

## Pages API

### Update Preprocessing Settings

```
PUT /api/pages/{page_id}/preprocessing
```

Apply image preprocessing settings to a page and get the processed image URL.

**Request Body**:
```json
{
  "grayscale": true,
  "brightness": 10,
  "contrast": 20,
  "binarization": "otsu",
  "adaptive_block_size": 11,
  "adaptive_c": 2,
  "deskew": true,
  "denoise": false,
  "denoise_strength": 10
}
```

**Response** (`200 OK`):
```json
{
  "page_id": "660e8400-...",
  "processed_image_url": "/api/pages/660e8400-.../image",
  "config_applied": {
    "grayscale": true,
    "brightness": 10,
    "contrast": 20,
    "binarization": "otsu",
    "adaptive_block_size": 11,
    "adaptive_c": 2,
    "deskew": true,
    "denoise": false,
    "denoise_strength": 10
  }
}
```

---

### Get Page Image

```
GET /api/pages/{page_id}/image
```

Returns the page image. Serves the processed image if available, otherwise the original.

**Response**: PNG image file.

---

### Get OCR Result

```
GET /api/pages/{page_id}/ocr
```

**Response** (`200 OK`):
```json
{
  "page_id": "660e8400-...",
  "raw_text": "ఇది తెలుగు పుస్తకం...",
  "bounding_boxes": [
    {
      "text": "ఇది",
      "confidence": 92,
      "bbox": { "x": 100, "y": 50, "w": 40, "h": 20 },
      "block_num": 1,
      "line_num": 1,
      "word_num": 1
    }
  ],
  "confidence": 78.5,
  "language_detected": "tel",
  "corrected_text": null
}
```

---

### Update OCR Correction

```
PUT /api/pages/{page_id}/ocr
```

**Request Body**:
```json
{
  "corrected_text": "ఇది తెలుగు పుస్తకం యొక్క సరిచేసిన వచనం..."
}
```

**Response** (`200 OK`): Same format as Get OCR Result, with `corrected_text` updated.

---

## Extraction API

### List Available LLM Models

```
GET /api/books/models
```

**Response** (`200 OK`):
```json
[
  {
    "name": "airavata",
    "size_gb": 4.1,
    "parameter_count": "7B"
  }
]
```

---

### Dispatch LLM Extraction

```
POST /api/books/{book_id}/run-extraction
```

Creates an LLM extraction job. Book status must be `ocr_complete`.

**Request Body**:
```json
{
  "model": "airavata",
  "temperature": 0.3,
  "max_tokens": 2048,
  "fields_per_batch": 10,
  "custom_system_prompt": null,
  "custom_extraction_prompt": null
}
```

**Response** (`201 Created`):
```json
{
  "job_id": "880e8400-...",
  "book_id": "550e8400-...",
  "status": "queued",
  "total_batches": 8
}
```

---

### Retry LLM Extraction

```
POST /api/books/{book_id}/retry-extraction
```

Retries LLM extraction with new parameters. Book status must be `ocr_complete` or `complete`.

**Request/Response**: Same as run-extraction.

---

## Metadata API

### Get Metadata

```
GET /api/books/{book_id}/metadata
```

**Response** (`200 OK`):
```json
{
  "book_id": "550e8400-...",
  "fields": {
    "title": "నా తెలుగు పుస్తకం",
    "author": "రచయిత పేరు",
    "publisher": "ప్రచురణకర్త",
    "publication_date": "2020",
    "language": "Telugu",
    "genre": "కవిత్వం",
    "pages": "250"
  },
  "updated_at": "2026-05-23T03:00:00Z"
}
```

---

### Update Metadata

```
PUT /api/books/{book_id}/metadata
```

Merges provided fields with existing metadata (partial update).

**Request Body**:
```json
{
  "fields": {
    "title": "Corrected Title",
    "author": "Corrected Author",
    "custom_field_1": "Custom value"
  }
}
```

**Response** (`200 OK`): Same format as Get Metadata, with merged fields.

---

### Get Field Definitions

```
GET /api/books/{book_id}/metadata/fields
```

Returns all 52 metadata field definitions with display names and Wikidata property mappings.

**Response** (`200 OK`):
```json
[
  {
    "field_name": "author",
    "display_name": "Author",
    "wikidata_property": "P50",
    "batch_group": "core_identity"
  },
  {
    "field_name": "title",
    "display_name": "Title (if subtitle exists)",
    "wikidata_property": null,
    "batch_group": "core_identity"
  }
]
```

---

### Get LLM Run History

```
GET /api/books/{book_id}/llm-runs
```

Returns all LLM extraction runs for a book, including prompts and raw responses.

**Response** (`200 OK`):
```json
[
  {
    "id": "990e8400-...",
    "job_id": "880e8400-...",
    "model": "airavata",
    "prompt_template": "Extract the following metadata...",
    "batch_config": { "batch": "core_identity", "fields": [...] },
    "raw_response": "{\"title\": \"...\", \"author\": \"...\"}",
    "parsed_fields": { "title": "...", "author": "..." },
    "created_at": "2026-05-23T02:30:00Z"
  }
]
```

---

## Library API

### List Library Books

```
GET /api/library/books
```

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | null | Search query (triggers fuzzy search) |
| `language` | string | null | Filter by language code |
| `status` | string | null | Filter by book status |
| `genre` | string | null | Filter by genre (partial match) |
| `publisher` | string | null | Filter by publisher (partial match) |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page (max: 100) |

**Response** (`200 OK`):
```json
{
  "items": [
    {
      "id": "550e8400-...",
      "title": "నా తెలుగు పుస్తకం",
      "filename": "book.pdf",
      "language": "tel",
      "status": "complete",
      "total_pages": 250,
      "created_at": "2026-05-23T01:30:00Z",
      "metadata_fields": {
        "author": "రచయిత పేరు",
        "publisher": "ప్రచురణకర్త",
        "title": "నా తెలుగు పుస్తకం"
      },
      "thumbnail_url": "/api/books/550e8400-.../pages/1/thumbnail"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### Search Library

```
GET /api/library/search?q={query}
```

Fuzzy search across title, filename, and metadata JSONB fields using pg_trgm similarity.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 1 character) |
| `language` | string | No | Filter by language |
| `limit` | integer | 20 | Max results (max: 100) |

**Response** (`200 OK`): Array of `BookSearchResult` objects (same format as list items).

---

### Get Filter Options

```
GET /api/library/filters
```

Returns available filter values from the database.

**Response** (`200 OK`):
```json
{
  "languages": ["hin", "tel"],
  "statuses": ["complete", "ocr_complete", "uploaded"],
  "genres": ["కవిత్వం", "నవల", "Fiction"],
  "publishers": ["ప్రచురణకర్త A", "Publisher B"]
}
```

---

### Get Book Detail (Library View)

```
GET /api/library/books/{book_id}/detail
```

Returns comprehensive book detail including pages, OCR text, metadata, jobs, and LLM runs.

**Response** (`200 OK`):
```json
{
  "book": {
    "id": "550e8400-...",
    "filename": "book.pdf",
    "title": "My Book",
    "language": "tel",
    "total_pages": 250,
    "status": "complete",
    "created_at": "2026-05-23T01:30:00Z",
    "updated_at": "2026-05-23T03:00:00Z"
  },
  "metadata": {
    "title": "నా తెలుగు పుస్తకం",
    "author": "రచయిత పేరు"
  },
  "metadata_updated_at": "2026-05-23T03:00:00Z",
  "pages": [
    {
      "id": "660e8400-...",
      "page_number": 1,
      "image_url": "/api/pages/660e8400-.../image",
      "ocr_text": "పుస్తకం యొక్క మొదటి పేజీ...",
      "ocr_confidence": 82.0
    }
  ],
  "llm_runs": [],
  "jobs": []
}
```

---

## Bulk Operations API

### Get Bulk Statistics

```
GET /api/bulk/stats
```

Returns library-wide statistics: total books, books with metadata, breakdown by language and status.

**Response** (`200 OK`):
```json
{
  "total_books": 1234,
  "books_with_metadata": 1100,
  "languages": {"tel": 800, "hin": 434},
  "statuses": {"complete": 1100, "ocr_complete": 134}
}
```

---

### Export Metadata as CSV

```
POST /api/bulk/export
```

Exports all book metadata as a CSV file. One row per book. The first column is `book_id` (UUID) for re-import matching.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | string | null | Filter by language code (e.g., `tel`, `hin`) |
| `status` | string | null | Filter by book status (e.g., `complete`) |

**Response**: CSV file download (`text/csv`)

**CSV Columns**: `book_id, title, language, filename, label, author, description_work, ...` (all 52 metadata fields)

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/export?language=tel" -o export.csv
```

---

### Import Metadata from CSV

```
POST /api/bulk/import
```

Upload a cleaned CSV to update book metadata. The CSV must contain a `book_id` column.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `merge` | `merge` — only update provided fields; `overwrite` — replace all fields |

**Content-Type**: `multipart/form-data`

**Body**: Form data with a `file` field containing the CSV.

**Response** (`200 OK`):
```json
{
  "total_rows": 500,
  "books_updated": 498,
  "books_not_found": 2,
  "fields_changed": 1523,
  "errors": ["Row 45: invalid book_id 'not-a-uuid'"]
}
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/import?mode=merge" \
  -F "file=@cleaned_metadata.csv"
```

---

### Export QuickStatements for Wikibase

```
POST /api/bulk/export-wikibase
```

Generates a QuickStatements TSV file for uploading books to Wikibase. Each book becomes a new item with properties mapped from the `FIELD_WIKIDATA` mapping.

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `language` | string | Filter by language code |

**Response**: TSV file download (`text/tab-separated-values`)

**Format** (one block per book):
```
CREATE
LAST	Len	"Book Title"
LAST	P50	"Author Name"
LAST	P123	"Publisher Name"
LAST	P31	Q571
LAST	P407	Q809
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/export-wikibase" -o quickstatements.tsv
```

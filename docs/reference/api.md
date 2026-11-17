# API Reference

Every endpoint is served under `/api` except the unprefixed `GET /health` used by container health
checks. All responses are JSON.

- Composition and auth wiring: `backend/app/api/router.py`
- Auth dependencies: `backend/app/api/deps.py`

---

## Conventions

| Aspect | Rule |
| --- | --- |
| Auth | Session cookie (`access_token`) or, for media only, a signed token |
| CSRF | `X-CSRF-Token` header required on cookie-authenticated `POST`/`PUT`/`PATCH`/`DELETE` |
| Errors | `{detail, type}` where `type` ∈ `validation_error`, `http_error`, `internal_error` |
| Pagination | `?page=&page_size=` (1-based, `page_size` ≤ 100), envelope `{items, total, page, page_size}` |
| Ownership | Non-visible resources return **404**, never 403 |
| Approval | Every router except `health`, `media` and `auth` requires `account_status == approved` |

---

## Health

Mounted at `/api` **and** unprefixed at `/health`. Unauthenticated by design.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Checks PostgreSQL, Redis, Ollama. 200 when all ok, 503 `degraded` otherwise |
| GET | `/api/health` | Same handler |
| GET | `/api/status` | Lightweight status |

---

## Auth — `/api/auth`

Outside the approval gate so pending and rejected users can hold a session.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/register` | Create account; 201 |
| POST | `/login` | Authenticate; sets all three cookies |
| POST | `/refresh` | Rotate refresh token; 401 on replay |
| POST | `/logout` | Revoke refresh token, clear cookies; 204 |
| GET | `/me` | Current user |
| POST | `/verify-email` | Consume verification token; starts a session |
| POST | `/resend-verification` | 202, always generic |
| POST | `/forgot-password` | 202, always generic |
| POST | `/reset-password` | Consume reset token; revokes all sessions |
| POST | `/change-password` | Requires current password; clears cookies |

Rate limit: 10 requests/minute/IP on `login`, `register`, `forgot-password`, `reset-password`,
`resend-verification`.

---

## Books — `/api/books`

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/upload` | Upload PDF (≤ `MAX_UPLOAD_SIZE_MB`, default 200) |
| GET | `/{book_id}` | Book summary |
| GET | `/{book_id}/detail` | Book with page and job summary |
| PATCH | `/{book_id}/language` | Correct the OCR language |
| DELETE | `/{book_id}` | Delete book and cascade |
| GET | `/{book_id}/pages` | Paginated pages |
| POST | `/{book_id}/pages` | Render selected pages (creates `page_extraction` job) |
| POST | `/{book_id}/preprocessing` | Apply preprocessing to pages (creates job) |
| POST | `/{book_id}/run-ocr` | Start OCR (creates `ocr` job) |
| GET | `/{book_id}/ocr-status` | Per-page OCR status and errors |
| GET | `/{book_id}/jobs` | Paginated jobs for the book |
| POST | `/{book_id}/reset` | Reset the workflow |
| POST | `/{book_id}/rerun-ocr` | Re-run OCR from the current pages |
| POST | `/{book_id}/rerun-extraction` | Re-run extraction |

`GET /{book_id}/detail` exists specifically so the detail screen does not need several list calls.

---

## Extraction — `/api/books`

Mounted **before** the books router so these static paths are not captured by `/{book_id}`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/prompt-defaults` | Default system and extraction prompts |
| GET | `/models` | Models available in Ollama (paginated) |
| POST | `/{book_id}/run-extraction` | Start extraction; accepts model, temperature, max tokens, prompt overrides |
| POST | `/{book_id}/retry-extraction` | Retry with unchanged parameters |

---

## Metadata — `/api/books`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/{book_id}/metadata` | The 50-field record |
| PUT | `/{book_id}/metadata` | Update fields (takes a row lock) |
| POST | `/{book_id}/review/complete` | Mark human review complete |
| GET | `/{book_id}/metadata/fields` | Field definitions with display names and batch group |
| GET | `/{book_id}/metadata/evidence` | Per-field provenance (paginated) |
| GET | `/{book_id}/llm-runs` | LLM audit rows (paginated) |

---

## Export — `/api/export`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/books/{book_id}/export?format=&include_details=` | Export one book (owner or admin) |
| POST | `/export` | Export selected books, or a filtered slice of the caller's library |

Formats: `csv`, `xlsx`, `json`, `jsonl`, `wikibase`, `openrefine`.

```json
POST /api/export
{ "format": "xlsx", "include_details": false,
  "book_ids": ["…"],                 // omit to use the filters
  "language": "tel", "status": "complete",
  "owner_id": "…"                    // administrators only
}
```

- **Scope:** non-admins export only their own books; a foreign `book_id` returns **404**. Admins may
  pass `owner_id` or export the whole library. `owner_id` supplied by a non-admin returns 404.
- **Eligibility:** only books with a saved metadata record are exported. Empty fields are preserved
  as empty cells/keys; the 49 canonical columns are always emitted.
- **Identity:** `book_id` is always the first column/key.
- **Details:** `include_details=true` adds `book_title`, `book_language`, `source_filename`
  (basename only), `status`, `total_pages`, `uploaded_at`, `reviewed_at` to CSV/XLSX and a `book`
  object to JSON/JSONL. Wikibase and OpenRefine ignore the flag.
- **Encoding:** CSV is UTF-8 **with BOM**; OpenRefine CSV is UTF-8 without BOM. JSON/JSONL use
  `ensure_ascii=False`, so Telugu and Hindi survive byte-for-byte.
- **Custom fields:** `custom:<name>` columns in CSV/XLSX; a `custom_fields` object in JSON/JSONL;
  a non-standard `custom_fields` sibling in Wikibase JSON.
- **Wikibase JSON:** entity-shaped items with `labels`, optional `descriptions`, and `claims` keyed by
  local P-IDs from `property-mapping.json`. `P31 → Q571`, language → `Q809`/`Q1568`/`Q1860`, and
  parseable years in `publication_date`/`inception` become `time` datavalues.
- **Limits:** at most 1000 explicit `book_ids` and 5000 rows per request (**413** above that).
- **Safety:** values starting with `=`, `+`, `-`, `@`, tab, or CR are prefixed in CSV/XLSX to prevent
  spreadsheet formula injection. JSON is not altered. Every response sets
  `Cache-Control: no-store`.

---

## Pages — `/api/pages`

| Method | Path | Purpose |
| --- | --- | --- |
| PUT | `/{page_id}/preprocessing` | Update one page's preprocessing config |
| POST | `/{page_id}/preprocessing/preview` | Render a preview with a candidate config |
| GET | `/{page_id}/ocr` | OCR result for the page |
| PUT | `/{page_id}/ocr` | Save corrected text and word edits |

---

## Jobs — `/api/jobs`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/{job_id}` | Job status and progress |

Cancellation is exposed at the dashboard and admin surfaces rather than here.

---

## Stages — `/api/books`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/{book_id}/stages` | Full stage history (paginated) |
| GET | `/{book_id}/stages/current` | Latest attempt per stage |

---

## Dashboard — `/api/dashboard`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/summary` | Counts for the signed-in user |
| GET | `/books` | Paginated books |
| GET | `/jobs` | Paginated jobs |
| POST | `/jobs/{job_id}/cancel` | Cancel a job |

---

## Admin — `/api/admin`

Requires `role == admin` **and** an approved account.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/users` | Paginated users |
| POST | `/users` | Create a user |
| GET | `/users/pending-count` | Badge count |
| GET | `/users/{user_id}` | Detail |
| PATCH | `/users/{user_id}` | Update role / active / display name |
| POST | `/users/{user_id}/approve` | Approve account |
| POST | `/users/{user_id}/reject` | Reject with reason |
| POST | `/users/{user_id}/reset-password` | Force a reset |
| DELETE | `/users/{user_id}` | Delete (blocked while the user owns books) |
| GET | `/stats` | Platform counts |
| GET | `/filters` | Filter options |
| GET | `/books` | All books |
| DELETE | `/books/{book_id}` | Delete any book |
| POST | `/books/{book_id}/reset` | Reset workflow |
| POST | `/books/{book_id}/rerun-ocr` | Re-run OCR |
| POST | `/books/{book_id}/rerun-extraction` | Re-run extraction |
| GET | `/system` | Host and container metrics |
| GET | `/maintenance` | Maintenance state |
| PUT | `/maintenance` | Enable/disable maintenance mode |
| GET | `/jobs` | All jobs |
| GET | `/jobs/summary` | Queue summary |
| POST | `/jobs/cancel` | Bulk cancel |
| POST | `/jobs/{job_id}/retry` | Retry a job |
| POST | `/jobs/{job_id}/cancel` | Cancel one job |

---

## Bulk — `/api/bulk`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/stats` | Export candidate counts |
| POST | `/export` | Admin-scoped export, any of the six formats |
| POST | `/import` | Import edited rows |
| POST | `/export-wikibase` | Generate a QuickStatements TSV **locally** |

`/export-wikibase` never contacts Wikibase. See
[integrations](../architecture/integrations.md#5-optional-integrations--wikibase-stack).

---

## Notifications — `/api/notifications`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `` (root) | Paginated notifications |
| GET | `/unread-count` | Badge count |
| POST | `/{notification_id}/read` | Mark one read |
| POST | `/read-all` | Mark all read |
| GET | `/preferences` | Email notification preference |
| PATCH | `/preferences` | Update preference |

---

## Media — `/api`

Mounted without the approval gate; accepts a session **or** a signed token scoped to the resource.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/books/{book_id}/pages/{page_number}/thumbnail` | 180 px thumbnail (rate-limit exempt) |
| GET | `/books/{book_id}/pages/{page_number}/preview` | Cached wide preview, `?width=` |
| GET | `/pages/{page_id}/image` | Full page image |
| GET | `/pages/{page_id}/preprocessing/preview` | Cached preprocessing preview |

---

## Server-Sent Events — `/api/sse`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/books/{book_id}/events` | Event stream for one book (rate-limit exempt) |

Event types:

| `type` | Payload |
| --- | --- |
| `job.progress` | `job_id`, `job_type`, `progress`, optional `batch` |
| `job.terminal` | `job_id`, `status`, `error_log` |
| `book.status_changed` | `status`, `job_id` |
| `book.awaiting_review` | `low_confidence_count` |

---

## Request and response bodies

Concrete shapes for the endpoints where the table above is not enough. Examples are illustrative;
field names and nullability are the contract.

### Authentication

```json
POST /api/auth/register
{ "email": "reader@example.com", "display_name": "Ada", "password": "long-enough-password" }

201 → { "message": "Account created. …", "email": "reader@example.com" }
```

Registration is moderated by default: the account is `pending` and unverified. `REGISTRATION_REQUIRES_APPROVAL=false`
auto-approves.

```json
POST /api/auth/login       { "email": "…", "password": "…" }
POST /api/auth/verify-email { "token": "<from email link>" }
POST /api/auth/reset-password { "token": "…", "new_password": "…" }
```

Each of these sets `access_token`, `refresh_token`, and `csrf_token` and returns the user object:

```json
{
  "id": "…", "email": "reader@example.com", "display_name": "Ada",
  "role": "user", "is_active": true, "account_status": "approved",
  "rejection_reason": null,
  "email_verified_at": "…", "last_login_at": "…", "created_at": "…"
}
```

`POST /api/auth/refresh` rotates the refresh cookie. Reusing a rotated token is treated as theft:
all sessions are revoked and the token version is bumped.

### Books

```text
POST /api/books/upload            multipart/form-data
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | PDF, capped by `MAX_UPLOAD_SIZE_MB` (200) |
| `title` | string | no | Optional display title |
| `language` | string | **yes** | `tel` \| `hin` \| `eng`; anything else is 422 |

```json
201 → { "id": "…", "filename": "book.pdf", "title": "…", "language": "tel",
        "total_pages": 250, "status": "uploaded", "created_at": "…" }
```

```json
PATCH /api/books/{book_id}/language   { "language": "hin" }
200 → { "id": "…", "language": "hin", "job_id": "…" }
```

Changing the language cancels active jobs, discards OCR derived from the old language, resets from
the OCR stage, keeps the PDF and page images, and queues fresh OCR. `job_id` is `null` when no pages
are selected or the language was already correct.

```json
POST /api/books/{book_id}/pages   { "selected_pages": [1, 2, 3, 248, 249, 250] }
200 → { "book_id": "…", "selected_count": 6, "status": "pages_selected" }
```

```json
POST /api/books/{book_id}/run-ocr
201 → { "id": "…", "book_id": "…", "job_type": "ocr", "status": "queued",
        "progress": 0.0, "created_at": "…", "started_at": null,
        "completed_at": null, "error_log": null }
```

```json
GET /api/books/{book_id}/ocr-status
{ "total_pages": 8, "ocr_complete_count": 8, "ocr_pending_count": 0,
  "avg_confidence": 78.5,
  "pages": [ { "page_number": 1, "page_id": "…", "has_ocr": true, "confidence": 82.0 } ] }
```

```json
GET /api/books/{book_id}/detail        (owner or admin; 404 otherwise)
{ "book": { "id": "…", "filename": "book.pdf", "title": "…", "language": "tel",
            "total_pages": 250, "status": "complete", "created_at": "…", "updated_at": "…" },
  "metadata": { "title": "…", "author": "…" },
  "metadata_updated_at": "…",
  "owner_display_name": "Ada Lovelace",
  "pages": [ { "id": "…", "page_number": 1, "image_url": "/api/pages/…/image",
               "ocr_text": "…", "ocr_confidence": 82.0 } ],
  "llm_runs": [], "jobs": [] }
```

`owner_display_name` is exposed; the owner's email never is.

Lifecycle endpoints return `{ "id", "status" }` unless noted:
`DELETE /api/books/{id}`, `POST /api/books/{id}/reset`,
`POST /api/books/{id}/rerun-ocr` (`{ "job_id", "book_id", "status" }`, 400 when no pages),
`POST /api/books/{id}/rerun-extraction` (400 when OCR has not run or a job is active).

### Pages

```json
PUT /api/pages/{page_id}/preprocessing
{ "grayscale": true, "brightness": 10, "contrast": 20, "binarization": "otsu",
  "adaptive_block_size": 11, "adaptive_c": 2, "deskew": true,
  "denoise": false, "denoise_strength": 10 }

200 → { "page_id": "…", "processed_image_url": "/api/pages/…/image",
        "config_applied": { … } }
```

```json
GET /api/pages/{page_id}/ocr
{ "page_id": "…", "raw_text": "…", "cleaned_text": "…", "corrected_text": null,
  "bounding_boxes": [ { "text": "…", "confidence": 92,
                        "bbox": { "x": 100, "y": 50, "w": 40, "h": 20 },
                        "block_num": 1, "line_num": 1, "word_num": 1 } ],
  "confidence": 78.5, "language_detected": "tel",
  "ocr_engine": "line_model", "ocr_route": null,
  "ocr_coverage": 1.0, "ocr_script": { "latin": 0.01, "telugu": 0.98, "devanagari": 0.0 } }

PUT /api/pages/{page_id}/ocr   { "corrected_text": "…" }   → same shape, corrected_text set
```

`GET /api/pages/{page_id}/image` serves the processed image when one exists, otherwise the original.

### Extraction

```json
GET /api/books/models                    (paginated envelope)
{ "items": [ { "name": "gemma4:e4b", "size_gb": 6.6, "parameter_count": "7.5B" } ],
  "total": 1, "page": 1, "page_size": 20 }
```

```json
POST /api/books/{book_id}/run-extraction
{ "model": "gemma4:e4b", "temperature": 0.3, "max_tokens": 512,
  "custom_system_prompt": null, "custom_extraction_prompt": null }

201 → { "job_id": "…", "book_id": "…", "status": "queued", "total_batches": 8 }
```

The model is pinned to `gemma4:e4b`; other names are rejected. Book status must be `ocr_complete`.
`POST /api/books/{book_id}/retry-extraction` takes the same body and also accepts `complete`.

### Metadata

```json
GET /api/books/{book_id}/metadata
{ "book_id": "…", "fields": { "title": "…", "author": "…", "publisher": "…",
                              "publication_date": "2020", "pages": "250",
                              "custom_fields": { "my_key": "value" } },
  "updated_at": "…" }

PUT /api/books/{book_id}/metadata
{ "fields": { "title": "Corrected Title", "author": "Corrected Author" } }
```

`PUT` **merges** the supplied keys; unspecified fields are untouched.

```json
GET /api/books/{book_id}/metadata/fields     (paginated)
{ "items": [ { "field_name": "author", "display_name": "Author",
               "wikidata_property": "P50", "batch_group": "core_identity" } ], … }
```

49 standard fields plus `custom_fields`. `GET /api/books/{book_id}/metadata/evidence` returns the
per-field provenance rows; `GET /api/books/{book_id}/llm-runs` returns the batch audit trail
(prompts, raw responses, parsed fields).

### Dashboard

```json
GET /api/dashboard/summary
{ "books": { "total": 3, "by_status": { "complete": 1, "awaiting_review": 1, "uploaded": 1 } },
  "jobs":  { "total": 12, "queued": 1, "running": 1, "completed": 9, "failed": 1, "cancelled": 0 },
  "queue": { "ocr": 2, "llm": 0 } }
```

Job rows include `queue_ahead` — queued jobs ahead in the same queue (`0` when running, `null` when
not queued). `POST /api/dashboard/jobs/{job_id}/cancel` returns `{ "id", "status" }` and 400s on a
terminal job.

### Admin

`GET /api/admin/stats` includes `users: { total, active, pending }` and a top-level
`pending_user_count`. Role changes, deactivation, rejection, and password resets revoke the target
user's sessions. The last active admin cannot be demoted or deactivated, and an admin cannot reject or
delete their own account.

### Bulk

```json
GET /api/bulk/stats
{ "total_books": 1234, "books_with_metadata": 1100,
  "languages": { "tel": 800, "hin": 434 },
  "statuses": { "complete": 1100, "ocr_complete": 134 } }

POST /api/bulk/import?mode=merge    (multipart, `file` = CSV with a book_id column)
200 → { "total_rows": 500, "books_updated": 498, "books_not_found": 2,
        "fields_changed": 1523, "errors": ["Row 45: invalid book_id 'not-a-uuid'"] }
```

`POST /api/bulk/export?language=&status=&format=` returns a download for every eligible book in
the admin scope; it delegates to the same serializer as `/api/export`. The OpenRefine-compatible
profile is `/api/bulk/export?format=openrefine`. `mode=overwrite` replaces all fields; default
`merge` updates only the provided ones.

The CSV import accepts both the current headers (`book_title`, `book_language`, `source_filename`)
and the legacy (`title`, `language`, `filename`). `custom:<name>` columns are merged into
`fields.custom_fields` instead of becoming top-level field keys.

`POST /api/bulk/export-wikibase?language=` returns `text/tab-separated-values` (QuickStatements),
generated locally:

```text
CREATE
LAST	Len	"Book Title"
LAST	P50	"Author Name"
LAST	P123	"Publisher Name"
LAST	P31	Q571
LAST	P407	Q809
```

### Notifications

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/notifications` | `{ items, total, unread_count, total_pages }`; query `page`, `page_size`, `unread_only` |
| GET | `/api/notifications/unread-count` | `{ "count": N }` |
| POST | `/api/notifications/{id}/read` | Row; 404 if it belongs to another user |
| POST | `/api/notifications/read-all` | `{ "updated": N }` |
| GET / PATCH | `/api/notifications/preferences` | `{ "email_enabled": true }` |

Types: `job_completed`, `job_failed`, `job_cancelled`, `account_approved`, `pending_registration`.
Creation is idempotent per `(user, event_key)`.

---

## Status codes

| Code | Meaning here |
| --- | --- |
| 200 | Success |
| 201 | Created (upload, job dispatch, user creation) |
| 202 | Accepted, response intentionally generic (resend verification, forgot password) |
| 204 | No content (logout, change password, deletes, mark read) |
| 401 | No/invalid session, unverified email, revoked token |
| 403 | CSRF failure, unapproved account, non-admin on admin route |
| 404 | Missing **or** not visible to the caller |
| 413 | Upload exceeds `MAX_UPLOAD_SIZE_MB` |
| 422 | Validation error |
| 429 | Rate limited; `Retry-After` set |
| 503 | Maintenance mode, or `/health` degraded |

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
| POST | `/export` | Export metadata as OpenRefine-ready data |
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

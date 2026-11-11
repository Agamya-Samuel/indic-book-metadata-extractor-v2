# 010 — Agent Browser Testing Handoff

Takeover doc for the **UI/UX + workflow/admin overhaul** (see `plans/006-ui-ux-workflow-admin.md`,
`learnings/007-ui-ux-workflow-admin-audit.md`, `todos/008-ui-ux-workflow-admin.md`).
The implementation is written and unit/integration-tested; this document is the
**browser-testing plan** plus everything a takeover agent needs.

> ## ⚠️ Deploy status — RESOLVED
>
> The deployed host is **up** (`/` and `/login` → 200, API `/health` → 200) and
> serves commit `24a3d49`. Two deploy-time defects were found and fixed:
>
> 1. **Every deploy since the auth/RBAC commit aborted at interpolation.**
>    `docker-compose.production.yml` declares `JWT_SECRET_KEY` and
>    `FRONTEND_URL` with `:?`, and the Dokploy environment had neither, so
>    `docker compose up` died in ~3s and Traefik had no route (404 on `/`,
>    `/login` and `/health`). Both variables are now set in the Dokploy
>    environment.
> 2. **Cross-subdomain API broke CSRF.** The API had its own host
>    (`*-api.agamya.us.kg`). The `csrf_token` cookie is host-only, so the
>    frontend could not read it, sent no `X-CSRF-Token`, and every
>    cookie-authenticated mutation (upload first) returned
>    `403 CSRF validation failed`. The API is now a **path on the frontend
>    host**: `NEXT_PUBLIC_API_URL=/api` with Traefik
>    `Host(domain) && PathPrefix(/api)` → `backend:8000`.
>
> Only the **frontend host is public**. Backend, worker, postgres, redis,
> ollama, mysql, elasticsearch, flower and backup are internal (`expose`, no
> domains, addressed by service name). OpenRefine and Wikibase keep their own
> hosts as operator tools. Dokploy's panel (:3000) and Traefik's API (:8080)
> are firewalled off — reach them over an SSH tunnel.
>
> Until the single-origin deploy is live, §6.2–6.7 and §6.9 cannot be exercised:
> every save/apply/complete button 403s.

Prefer testing against the **deployed `oki` host**, not the local PC (see §1).

---

## 0. TL;DR for the takeover agent

1. Deploy is driven by **push to `main`** (Dokploy builds `docker-compose.production.yml`).
   Push, wait for the deploy, then test at
   `https://indic-book-metadata-extractor.agamya.us.kg/`.
2. You need a **verified admin account** on the deployed host (§2). Registration
   requires SMTP; the cleanest path is the create-admin one-liner over the
   Dokploy terminal.
3. Walk §6 top-to-bottom. Each item lists steps, exact UI text/selectors, and
   expected results. Anything in §7 is a known gotcha — do not re-file it as new.
4. Report using the format in §8. Attach screenshots and the job rows you saw.

---

## 1. Where to test

### Primary — deployed `oki` host (preferred)

- URL: `https://indic-book-metadata-extractor.agamya.us.kg/`
- Deploy: **commit + push to `main`** then a Dokploy build. The production
  service uses **`docker-compose.production.yml`**. First deploy is slow (Ollama
  pulls the model); later deploys are incremental. If the site is not up ~2 min
  after the push, check the Dokploy deployment logs — see the ⚠️ Deploy status
  box above for the two failure modes that were fixed.
- The deployed stack has `SMTP_ENABLED=true` so registration/verification
  emails work; if not, create the admin directly (§2).
- Same-origin in production (frontend and `/api` behind one host), so cookies
  and SSE work without cross-origin caveats. The cross-origin notes in §3/§7
  are **local-only**.

### Local fallback (only if the deployed host is unavailable)

```bash
make up          # core: postgres, redis, ollama, backend, worker-ocr, worker-llm
make migrate
docker compose exec -T ollama ollama pull qwen2.5:7b   # ~4.7 GB
```

Local environment gotchas already fixed on this machine (see §7.1): the repo
`.env` needs `POSTGRES_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`,
`WIKIBASE_*` or `make up` fails. Then run the frontend dev server:

```bash
cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run dev   # :3000
```

Local is **cross-origin** (`:3000` → `:8000`): cookies are `SameSite=Lax`
(same-site across ports, so they're sent), and SSE needs `withCredentials: true`
(already set in `use-sse.ts`).

---

## 2. Access & credentials

### Create an admin (required once per environment)

`backend/scripts/create_admin.py` is **not** copied into the backend image, so on
the deployed host run the equivalent inline over the Dokploy terminal (or
`docker compose exec`):

```bash
docker compose exec -T backend uv run python -c "
import asyncio
from app.core.database import async_session_factory
from app.models.user import UserRole
from app.services import auth_service
async def main():
    async with async_session_factory() as db:
        u = await auth_service.create_user(
            db, email='you@example.com', display_name='QA Admin',
            password='<strong-password>', role=UserRole.ADMIN, verified=True)
        print('created', u.email)
asyncio.run(main())
"
```

Password policy comes from `PASSWORD_MIN_LENGTH` (default **10**). The account is
created verified + active.

- Local account already created for reference: `e2e@example.com` / `E2eTest!2026`
  (local DB only — do **not** expect it to exist on `oki`).

### Roles to exercise

- **Admin**: full admin panel, re-run/reset/delete, owner filters.
- **User**: owns their own books; cannot reach other users' private books.
- **Anonymous**: sees only the public catalog.

---

## 3. Tooling (Playwright MCP) — tips that save time

The browser tools are available (navigate / click / fill / snapshot / screenshot /
`browser_run_code_unsafe`). Gotchas learned while writing this handoff:

1. **Wait for client-side session hydration.** First paint shows
   `Loading session`; wait ~2s or wait for the form text before interacting.
2. **Hidden file input.** The upload dropzone's `<input type=file>` is hidden and
   not clickable. Use:
   ```js
   await page.locator('input[type=file][name=pdf]').first()
     .setInputFiles('/path/to/book.pdf');
   ```
3. **Prefer role/name or `has-text` selectors** over refs when the DOM re-renders
   (stepper/query updates invalidate refs).
4. **Long jobs** (OCR, LLM): poll the admin Jobs page or the job card rather than
   blocking. LLM extraction on CPU can take 10–20 min for a full book.
5. **Screenshots**: capture the stepper + the relevant panel on any failure.

---

## 4. Test data

- Real scanned book used for local verification:
  `backend/storage/uploads/a2db7f01-e1f4-4ed0-9539-0633b6db6763/original.pdf`
  — **Hindi**, 119 pages, scanned (title page reads "वीरेंद्र भाटिया : चयनित कविताएँ").
  Copy it to `/tmp/kilo/e2e-hindi.pdf` for upload. A 29 MB upload is fine
  (limit is `MAX_UPLOAD_SIZE_MB`, default 200).
- Ground-truth corpus manifest: `backend/tests/fixtures/ground_truth/manifest.jsonl`.
- On the deployed host, upload any real Telugu/Hindi scanned PDF; select **1–2
  pages** to keep OCR/LLM fast.

---

## 5. Implementation status (what to verify vs what is still to build)

Legend: ✅ implemented + locally verified · 🟡 implemented, needs deployed verification ·
⬜ not implemented (out of scope for this handoff; listed so you don't expect it).

| Area | Status | Notes |
|---|---|---|
| `workflow-state.ts` derivation + stepper + `WorkflowShell` | ✅ | 7 honest states incl. failure/stale |
| SSE: snapshot/connected/heartbeat, connection mode, polling fallback | 🟡 | `withCredentials` fix just added |
| LLM config escape hatch (form always mounted) + run-scoped job | ✅ | re-run no longer traps on progress |
| LLM preflight (`/books/models`) | ✅ | route shadowing fixed (was 422) |
| OCR editor key/dirty/empty/read-only + unsaved guard | ✅ | saved Hindi correction end-to-end |
| Re-run OCR from any status (backend) + confirm + Celery revoke | ✅ | keeps metadata, resets downstream stages |
| Preprocessing seed/preview/apply/rotation/advanced | ✅ | preview writes temp file only |
| Async page-extraction job (`/extracting-pages?job=`) | ✅ | select → job → auto-redirect to preprocessing |
| Bulk preprocessing job (`POST /books/{id}/preprocessing`) | ✅ | 2-page bulk job completed at 100% |
| Explicit `POST /books/{id}/review/complete` | 🟡 | needs deployed confirm of full metadata flow |
| Admin sidebar/layout + PageHeader + per-row pending + DataTable | 🟡 | jobs table on `DataTable`; books table still bespoke rows |
| Admin `/admin` operations aggregation | ⬜ partial | KPI strip exists; global failures + `has_metadata`-aware stats still derive from the 10-row page |
| Phase 2 polish (upload %, select-pages virtualization, OCR-processing card, metadata SaveBar/evidence nav, field revert) | ⬜ | not implemented |
| Page-extraction failure/retry UX on `/extracting-pages` | 🟡 | basic failure + retry-to-select exists |
| Playwright e2e suite committed to the repo | ⬜ | this doc is the manual plan; no automated Playwright spec was added |

---

## 6. Test matrix

Run in order. For each: **Steps → Expected**. Mark Pass/Fail + evidence.

### 6.1 Login, stepper truth, SSE (baseline)

1. Log in; open an existing book in progress (or upload a new one).
2. Watch the top stepper on every stage page.
   - **Expected**: 7 steps (Upload, Select Pages, Preprocessing, OCR, OCR Review,
     LLM Extraction, Metadata Review). Completed steps are links with a ✓;
     the current step is highlighted with the step number/spinner; future steps
     are **locked** (`aria-disabled`, "complete the previous step first").
3. Open DevTools → Network, filter `events`.
   - **Expected (deployed)**: `GET /api/sse/books/{id}/events` stays **200** and
     streams `heartbeat`/`snapshot`. If the stream drops, the UI shows a
     "polling fallback" notice and recovers on reconnect.
   - Local cross-origin: previously 401; the fix sets `withCredentials: true`. If
     you still see 401 locally, note it (§7).

### 6.2 LLM config is never trapped (P0 #1)

1. Go to a book whose extraction already **completed** (status `awaiting_review`).
2. Open **LLM Extraction**.
   - **Expected**: the configuration form is **always visible** (model, prompts,
     batching), the Run button reads **"Run again"**, and a note warns that
     running again replaces extracted metadata. A completed run does **not**
     replace the form with a progress screen.
3. With Ollama up: no warning banner; Run is enabled. Batching shows
   **"8 LLM calls … across 49 fields (one per batch group)"**.
4. Stop Ollama (or use a host with no models) and reload.
   - **Expected**: an "Ollama is unreachable…" warning appears and Run is disabled.

### 6.3 OCR review editor (P0 #2)

1. Open **OCR Review** for a page with text.
2. Click **Edit text**, type a correction.
   - **Expected**: **Save corrections** becomes enabled; an **Unsaved** chip shows.
3. Clear the textarea completely, then Save.
   - **Expected**: empty text **is** saved (does not silently fall back to the old
     text); an **Edited** chip shows; Save disables again.
4. Edit again, then click a different page thumbnail or a stepper link.
   - **Expected**: a confirm ("You have unsaved changes…") intercepts; Cancel
     keeps you on the page.
5. Verify the notice: "Word boxes below are the original OCR layout — they are
   not updated by text edits."

### 6.4 Preprocessing (P0 #5)

1. Open **Preprocessing** for a book with pages.
   - **Expected**: settings are **seeded from the selected page's saved config**;
     thumbnails show a ✓ when processed; `Language: … • N pages` in the header.
2. Change a control (e.g. toggle **Denoise**) → **Unsaved** appears; **Apply to
   this page** enables.
3. Click **Preview**.
   - **Expected**: page switches to a **Preview** image with the note "This
     preview is not saved. Click Apply to commit it to the page." A Current/Preview
     toggle appears once a preview exists.
4. Click **Apply to this page**.
   - **Expected**: succeeds, page marked processed, no error.
5. Click **Apply to all pages**.
   - **Expected**: a single **"Applying to all pages"** job card with a 0–100%
     progress bar and **Cancel**; on completion, "Settings applied to all pages".
     (Not N parallel requests — check Network: one `POST /books/{id}/preprocessing`.)
6. Try **Rotation** (↺/↻ 90°), **Fine angle** slider, **Advanced** (upscale,
   borders, auto-preprocess), and **Reset to defaults**.

### 6.5 Async page extraction (Phase 3.7)

1. From a book, open **Select Pages**, choose 1–2 pages, click **Confirm N pages**.
   - **Expected**: navigates to `/books/{id}/extracting-pages?job=<id>`.
2. On the extraction page.
   - **Expected**: a JobProgressCard titled **"Extracting pages"** with a 0–100%
     bar and **Cancel**; on completion it auto-redirects to **Preprocessing**.
3. Test **Cancel**: start extraction for many pages and cancel.
   - **Expected**: job shows Cancelled; the admin Jobs page reflects it; no pages
     are left half-written (list pages via the API).
4. Regression: the stepper's **Select Pages** step must not show complete until
   the job finishes.

### 6.6 Re-run OCR (P0 #4)

1. On a book that already has OCR **and** metadata, go to **Preprocessing** and
   click **Re-run OCR on All Pages**.
   - **Expected**: a **confirm dialog** lists what is discarded (OCR text),
     reset (OCR review / LLM / metadata review stages), **kept** (metadata text,
     per-page preprocessing settings) before anything happens.
2. Confirm.
   - **Expected**: new OCR job runs; the stepper shows OCR current and **LLM
     Extraction / Metadata Review as stale (↻)** until re-run; the previously
     extracted metadata text is still present in Metadata Review (marked stale),
     not deleted.
3. Verify in Admin → Jobs that the previous OCR/LLM jobs show **cancelled** and a
   new OCR job is queued/running.

### 6.7 Review completion (Phase 3.8)

1. In **Metadata Review**, edit a field and click **Save Metadata**.
   - **Expected**: saves, but the book **stays in review** (does **not** jump to
     complete). The stepper's Metadata Review remains current.
2. Click **Mark review complete**.
   - **Expected**: a confirm dialog listing empty/low-confidence field counts;
     confirming calls `POST /books/{id}/review/complete`, the book becomes
     **complete**, and the stepper shows all steps complete.
3. Try to complete with a running job.
   - **Expected**: server returns 409 and the UI surfaces an error.

### 6.8 Admin restructure

1. Visit `/admin`, `/admin/books`, `/admin/jobs`.
   - **Expected**: a **left sidebar** (Operations/Books/Jobs/Users) on desktop
     with `aria-current` on the active item; a **mobile drawer** under ~1024px.
     No duplicate top admin bar.
2. Each page has a `PageHeader` (Operations / Books / Jobs).
3. Jobs table: progress shows the **0–100** value (a job at 42% shows "42%", not
   "4200%"). Owner column, book link (uses in-app navigation), per-row **Cancel**
   that only disables the row being cancelled.
4. Books table: select rows → bulk actions; per-row actions disable only that row.
5. Filters: status, type (**includes page_extraction**), owner; `has_metadata`
   filter total matches the number of returned rows and paginates correctly.

### 6.9 Failure paths (plan §5.3)

- Ollama down → extraction blocked with a clear message.
- Cancel OCR mid-run → job cancelled, book status recovers (not stuck).
- Cancel page extraction mid-render → no orphan partial pages.
- Re-run OCR over existing metadata → metadata kept, stages reset (6.6).
- Admin reset a book → stages reset, status `uploaded`, pages/OCR cleared.
- Review-complete with empty fields → allowed but warned; with a running job → 409.

### 6.10 Not covered here (do not block this handoff on them)

- Phase 2 UX polish (upload progress %, page virtualization, OCR-processing
  progress card, metadata SaveBar/evidence jump nav/field revert).
- `/admin` global failure aggregation and `has_metadata`-aware stat totals.
- pgvector semantic search; Telugu/Hindi only; CPU inference latency.

---

## 7. Known issues / gotchas (do not duplicate)

### 7.1 Local stack start

- `make up` fails without `POSTGRES_PASSWORD` / `MYSQL_ROOT_PASSWORD` /
  `MYSQL_PASSWORD` / `WIKIBASE_*` in `.env` (`.env` is gitignored). MariaDB
  refuses to start without a root password. Add them, then `make up`.
- `wikibase` has no compose healthcheck, so `docker compose up --wait` reports it
  unhealthy even when fine. Flower previously crash-looped on the stale
  `mher/flower` image; it now runs from the backend image via
  `uv run --with flower` (see the `fix(infra): run Flower…` commit).
- `.env` on this machine was patched with a strong `WIKIBASE_ADMIN_PASS` and
  `FLOWER_BASIC_AUTH` to make those two services start.

### 7.2 Auth / cross-origin (mostly local)

- Page images are fetched with `<img src="/api/pages/{id}/image">`. After the
  short-lived access cookie expires, these can 401 because an `<img>` cannot run
  the refresh interceptor. On the deployed same-origin host this is much less
  likely; if you see broken page images after ~15 min, reload. **This is a
  pre-existing auth limitation, not part of the workflow overhaul** — note it,
  don't fix it here.
- SSE must use `withCredentials: true` (fixed). If you still see `401` on
  `/api/sse/...` locally, report it with the request cookies.

### 7.3 Workflow semantics by design

- **Preprocessing shows as "complete" immediately after page extraction** because
  each page is seeded with `DEFAULT_PREPROCESSING_CONFIG`. Defaults are a valid
  config; OCR can run without an explicit Apply. This is intended.
- **Stale** (↻) is derived from stage attempt numbers: re-running an upstream
  stage marks downstream completions stale until they are re-run.
- LLM extraction runs **one call per `batch_group` (8 groups)**, not per N fields.

### 7.4 Concurrency during development

- The working tree has other in-flight workstreams (auth/RBAC, ground-truth
  fixtures, LLM eval scripts). When committing, stage only the files you touched;
  don't sweep the whole tree.

---

## 8. Reporting format & exit criteria

For each matrix item report:

```
[6.x] <title> — PASS/FAIL
Environment: deployed oki / local
Steps: …
Observed: …           (paste exact UI text, job status/progress, HTTP codes)
Expected: …
Evidence: screenshot path / network entry
```

**Exit criteria:** all of §6.1–6.9 PASS on the deployed host, or each FAIL has a
repro + evidence and is filed with a severity. §6.10 items are explicitly out of
scope. Report the deploy commit SHA you tested.

---

## 9. Where the code lives (for context)

Key files (see `plans/006` §7 for the full map):

- Derivation: `frontend/src/lib/workflow-state.ts` (+ `tests/lib/workflow-state.test.ts`)
- Shell/stepper: `frontend/src/components/shared/workflow-shell.tsx`, `workflow-stepper.tsx`
- SSE: `frontend/src/hooks/use-sse.ts`, `use-book-status.ts`
- Jobs: `frontend/src/hooks/use-job-progress.ts`, `use-job-polling.ts`,
  `components/shared/job-progress-card.tsx`, `progress.tsx`
- Unsaved guard/save bar: `hooks/use-unsaved-changes.ts`, `components/shared/save-bar.tsx`
- Pages: `frontend/src/app/books/[bookId]/{select-pages,extracting-pages,preprocessing,ocr-processing,ocr-review,llm-config,metadata-review}/page.tsx`
- Admin: `frontend/src/app/admin/{layout,page,books/page,jobs/page}.tsx`,
  `components/admin/admin-nav.tsx`, `components/shared/data-table.tsx`
- Backend: `app/api/books.py` (select pages job, re-run OCR, bulk preprocessing),
  `app/api/metadata.py` (`/review/complete`), `app/api/router.py` (route order),
  `app/tasks/page_tasks.py` (page render + bulk preprocess jobs),
  `app/services/stage_manager.py` (`reset_from_stage`),
  `app/services/admin_service.py` (cancel + revoke),
  `app/services/search_service.py` (`has_metadata` in SQL),
  `app/services/preprocessing.py` (rotation), `app/schemas/page.py`.

Recent commits to test against (`git log --oneline`):

```
feat(pages): run page extraction and bulk preprocessing as background jobs
feat(review): add an explicit mark-review-complete action
refactor(admin): add a shared DataTable and per-row action state
fix(infra): run Flower from the backend image and require stack passwords
feat(workflow): derive stage state and rebuild the workflow UI around it
feat(backend): harden re-run OCR, review completion, filters, and preprocessing
feat(auth): add email/password auth, RBAC, and per-user book ownership
fix(routing): include /books/models before /books/{book_id}
```

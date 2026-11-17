# Frontend Architecture

The frontend is a Next.js 16 App Router application (React 19) that renders the seven-step book
workflow, the admin surface, and the account flows. It talks to the backend exclusively over
same-origin `/api` calls.

- Root: `frontend/`
- Entry: `frontend/src/app/layout.tsx`
- API client: `frontend/src/lib/api.ts` (~1,500 lines, the single HTTP surface)
- Workflow model: `frontend/src/lib/workflow-state.ts`

---

## 1. Stack

| Concern | Choice |
| --- | --- |
| Framework | Next.js 16, App Router, `output: "standalone"` |
| UI runtime | React 19 |
| Server state | TanStack Query v5 — `staleTime: 60s`, `refetchOnWindowFocus: false` |
| Client state | Zustand (`frontend/src/stores/book-store.ts`) for cross-step book state |
| HTTP | axios, `withCredentials: true` |
| Canvas | Konva / react-konva for OCR bounding boxes and the zoomable page viewer |
| Toasts | sonner |
| Search | Fuse.js for client-side typeahead |
| Fonts | Geist (UI), Geist Mono, Noto Serif (display; Indic faces fall back to the OS Noto Serif stack) |

`next.config.ts` sets security headers on every route (HSTS, `nosniff`, `X-Frame-Options: DENY`,
`frame-ancestors 'none'`, `Referrer-Policy`, `Permissions-Policy`), disables `X-Powered-By`, and
keeps the New Relic browser agent out of webpack via `serverExternalPackages` plus
`outputFileTracingIncludes`.

**Build tooling:** `npm run build` passes `--webpack`. Turbopack's `next/font/google` loader fails
intermittently in CI with *"next/font/google queries have exactly one entry"* while resolving Noto
Serif (four weights plus italic), which the webpack font pipeline handles deterministically.
`next dev` still uses Turbopack, so local development is unaffected.

---

## 2. Provider composition

`app/layout.tsx` nests providers in a fixed order. Order matters: `AuthProvider` must sit inside
`QueryClientProvider`, and every gate must sit inside `AuthProvider`.

```text
<html>
  └─ <body>
      └─ Providers
          ├─ ThemeProvider          (inline beforeInteractive init script, no FOUC)
          ├─ QueryClientProvider
          ├─ AuthProvider           (session state, refresh, logout)
          ├─ [ children + Toaster ]
          └─ MaintenanceGate
              ├─ AppNavbar
              └─ RouteGuard ─── page
```

A "Skip to main content" link is the first focusable element, and `#main-content` is the target with
`tabIndex={-1}`.

---

## 3. Routing

All routes are filesystem routes under `frontend/src/app/`.

### Public

| Path | Purpose |
| --- | --- |
| `/` | Landing page |
| `/login` | Sign in |
| `/register` | Sign up (email verification required) |
| `/verify-email` | Consume verification token |
| `/forgot-password` | Request reset link |
| `/reset-password` | Consume reset token |
| `/pending-approval` | Holding screen for pending/rejected accounts |

### Application (approved users)

| Path | Purpose |
| --- | --- |
| `/dashboard` | Book list, job history |
| `/upload` | PDF upload |
| `/notifications` | Notification centre |
| `/books/{bookId}` | Book detail / workflow hub |
| `/books/{bookId}/select-pages` | Choose pages, zoomable viewer |
| `/books/{bookId}/extracting-pages` | Page-render progress |
| `/books/{bookId}/preprocessing` | Per-page preprocessing controls and preview |
| `/books/{bookId}/ocr-processing` | OCR progress (SSE) |
| `/books/{bookId}/ocr-review` | Correct OCR text and bounding boxes |
| `/books/{bookId}/llm-config` | Model and prompt profile, then start extraction |
| `/books/{bookId}/llm-processing` | Extraction progress |
| `/books/{bookId}/metadata-review` | Review the 50 fields with OCR reference pane |
| `/books/{bookId}/jobs` | Job history for the book |
| `/books/{bookId}/error` | Book-scoped error boundary |

### Admin

`/admin` (`ADMIN_PATHS = ["/admin"]`), with `/admin/users`, `/admin/books`, `/admin/jobs`,
`/admin/bulk`, `/admin/system`.

**Removed routes:** `/library` and `/bulk-operations` no longer exist. Bulk operations moved under
`/admin/bulk`. Older documents and learnings may still reference them.

---

## 4. RouteGuard

`frontend/src/components/auth/route-guard.tsx` is a client component wrapping every page.

| Rule | Behaviour |
| --- | --- |
| Loading | Full-page spinner |
| No user on a non-public path | Redirect to `/login?next=<encoded path>` |
| User but `account_status !== approved` | Redirect to `/pending-approval` |
| Approved user on `/pending-approval` | Redirect to `/dashboard` |
| Non-admin on an `/admin` path | Redirect to `/dashboard` |
| Otherwise | Render children |

Public path matching is prefix-based (`/login` also matches `/login/…`), and `/` is always public.
The backend enforces the same rules; the guard is navigation UX, not a security boundary.

---

## 5. The seven-step workflow model

The backend has **six** stages. The UI shows **seven** steps. The extra one is *preprocessing*, which
the backend models as per-page configuration rather than a stage.

This mapping lives in exactly one place — `frontend/src/lib/workflow-state.ts` — so the stepper, page
guards, and resume banner cannot disagree.

| UI step | Key | Backend source |
| --- | --- | --- |
| 1 | `upload` | `book.status !== null` |
| 2 | `pages` | `page_extraction` job / `pages[]` present |
| 3 | `preprocessing` | every page has `preprocessing_config`, or OCR has started |
| 4 | `ocr` | `book_stage_status[ocr]` |
| 5 | `ocr_review` | implicit: OCR complete and LLM not started |
| 6 | `llm` | `book_stage_status[llm_extraction]` |
| 7 | `review` | `book_stage_status[human_review]` or `book.status === complete` |

`deriveWorkflowState()` returns per-step `StepState` (`not_started | current | complete | failed |
stale`), the first incomplete step as `currentStep`, and any active processing job with its progress.

### Staleness, not just state

A downstream stage from an earlier attempt is **stale** when its upstream stage was restarted after
it. The comparison prefers stage row `created_at` timestamps and only falls back to `attempt` numbers
when timestamps are missing or equal — because attempt counters are per-stage, so "OCR attempt 2,
LLM attempt 1" is *not* stale.

This is what makes "re-run OCR after extraction" show the LLM and review steps as stale rather than
completed.

### Monotonicity

Starting a later stage proves every earlier one finished. That rule lets legacy books — created
before stage tracking existed and therefore having no stage rows — still render a correct stepper.

---

## 6. Live updates

Two mechanisms, used for different things:

| Mechanism | Used for | Code |
| --- | --- | --- |
| SSE | Job progress, terminal status, book status changes, awaiting-review | `frontend/src/hooks/use-sse.ts` → `GET /api/sse/books/{id}/events` |
| Polling | Fallback and non-streaming surfaces | `use-job-polling.ts`, `use-job-progress.ts`, `use-book-status.ts` |

SSE events consumed: `job.progress`, `job.terminal`, `book.status_changed`, `book.awaiting_review`.
The backend rate limiter explicitly exempts the SSE path so a long-lived stream does not burn the
per-IP quota.

---

## 7. API client

`frontend/src/lib/api.ts` is the only module that performs HTTP.

- **Base URL:** `NEXT_PUBLIC_API_URL`, default `/api` — same-origin in production so the session
  cookie is sent and CSRF is meaningful.
- **Credentials:** `withCredentials: true`.
- **Refresh:** a 401 triggers a single `POST /auth/refresh` and a replay of the original request.
- **Pagination:** `Page<T>` envelope with `fetchAll` helper; the UI defaults to 10 rows with 10/25/50
  options (`lib/pagination.ts`).
- **Types:** every endpoint has a hand-written response interface (`BookDetail`, `PageResponse`,
  `OcrResultResponse`, `JobResponse`, `BookStageResponse`, `PreprocessingConfig`, …).

---

## 8. Notable components

| Component | Responsibility |
| --- | --- |
| `components/shared/workflow-shell.tsx`, `workflow-nav.tsx`, `stage-rail.tsx`, `step-marker.tsx` | The seven-step chrome |
| `components/book/page-viewer.tsx` | Zoomable page viewer used during selection |
| `components/ocr/bounding-box-canvas.tsx`, `text-editor.tsx` | OCR correction with Konva overlays |
| `components/metadata/review-workspace.tsx`, `ocr-reference-pane.tsx`, `metadata-form.tsx` | Split review UI: fields beside OCR evidence |
| `components/auth/maintenance-gate.tsx` | Blocks the app when maintenance mode is on |
| `components/notifications/notification-bell.tsx` | Unread count and popover |
| `components/admin/*` | Queue management, system metrics, maintenance card, confirm dialog |
| `components/shared/data-table.tsx`, `pagination.tsx` | Consistent list behaviour |

---

## 9. Metadata and discoverability

- `src/lib/site.ts` is the single source for the site name, description, keywords and canonical
  origin. The origin resolves from `NEXT_PUBLIC_SITE_URL`, then `FRONTEND_URL`, then
  `http://localhost:3000`.
- The root layout exports `metadata` (title template, OpenGraph, Twitter card, robots, authors,
  Apple web-app hints) and `viewport` (theme colours, `viewport-fit=cover`). Public routes render
  during session loading so their content, including the home H1, is present in the server HTML.
- File conventions add the rest: `app/icon.svg` / `app/favicon.ico` (icons),
  `app/apple-icon.png` (iOS home screen), `app/opengraph-image.tsx` and `app/twitter-image.tsx`
  (1200×630 social card), `app/manifest.ts` (web app manifest), `app/robots.ts` (disallows
  authenticated routes) and `app/sitemap.ts`.
- The home page emits JSON-LD (`Organization`, `WebSite`, `WebApplication`) and its canonical
  `og:url`; `og:url` is the only OpenGraph field the page overrides.
- Per-route titles still come from `useDocumentTitle`; the root template appends "· Indic Books".

---

## 10. Accessibility and UX conventions

- Keyboard-first: skip link, `focus-ring.ts` for consistent focus treatment, `use-document-title.ts`
  for per-route titles.
- `use-unsaved-changes.ts` guards navigation when the metadata form is dirty; `save-bar.tsx` keeps
  the save action visible.
- `Skeleton` components are used for every async region so layout does not jump.
- Theme is applied by an inline `beforeInteractive` script to avoid a flash of the wrong theme.

---

## 11. Known limitations

1. **No runtime feature flags.** `NEXT_PUBLIC_OPENREFINE_URL` / `NEXT_PUBLIC_WIKIBASE_URL` are baked
   in at build time, so optional integrations cannot be hidden without a rebuild.
2. **No offline mode.** Every screen assumes the API is reachable.
3. **Client-side filtering only for typeahead.** Fuse.js indexes the loaded page of results.
4. **No component test coverage for the workflow derivation.** `deriveWorkflowState` is the most
   logic-dense module in the frontend; see [testing strategy](../testing/strategy.md).


# 008 — UI/UX Redesign: Unify the Composition Layer

**Status:** Approved — ready to implement.
**Owner:** user · **Study record (prior):** `learnings/007-ui-ux-workflow-admin-audit.md`
**Predecessor:** `plans/006-ui-ux-workflow-admin.md` (the fix pass) · `todos/008-ui-ux-workflow-admin.md`
**Owed:** `todos/011-ui-ux-composition-redesign.md` (checklist)
**Date:** 2026-11-13

> **⚠️ Working-tree hazard.** During analysis, `frontend/src/app/library/` and
> `frontend/src/app/bulk-operations/` were returned by the tool index but are
> **not tracked in HEAD** — they were removed by `84277d8`. The tree is shared
> with other agent sessions. **Re-read any file immediately before editing it**
> and never assume a path exists because search returned it.

## 1. Goal

Make the internal pages read as **one product**. The design token system
([ARCHIVE LIGHT](frontend/src/app/globals.css)) is genuinely strong — OKLCH ramp,
spacing rhythm, radii, shadows, motion, reduced-motion and forced-colors
handling. What never happened is the **composition layer**: every page was built
by hand on top of good atoms, so the atoms cohere and the molecules do not.

This is **unification, not a reskin**, and it must **preserve all functionality**
— the objective is how features are presented and used, not which capabilities
exist.

## 2. Decisions agreed with the user (2026-11-13)

| Topic | Decision |
|---|---|
| Scope | **Everything**: book workflow (7 stages + 2 monitor screens), dashboard, book detail, admin (`/admin`, books, jobs, users), `/admin/bulk`, plus a **light** auth pass and a **design-kit** page |
| Layout stance | Three explicit modes — `reading` (content-max), `workspace` (full-bleed, sticky panel, no page scroll), `gallery` (full-bleed grid). Top navbar stays anchored to `content-max` |
| Workflow IA | Replace the horizontal stepper with a **persistent left stage rail** (7 stages, state per stage); the two auto-monitors render as running **sub-rows under their owning stage**; mobile = sticky stage bar + sheet |
| Element swaps | (1) metadata-review box viewer → **evidence pane bound to the focused field**; (2) OCR-review page strip → **collapsible thumbnail filmstrip**; (3) llm-config prompts → **collapsed by default** with a "modified" badge + reset |
| Preprocessing | Keep grouped raw controls, **add four named presets** that write group values (fully editable after); no auto-apply, no backend change |
| Phasing | 6 phases with a checkpoint each; **feature branch**; push to `main` (→ auto-deploy) only at **two coherent milestones** the user approves (after phase 3, after phase 5) |
| Design kit | New admin-gated route `/admin/design` rendering every primitive and pattern with states |
| Verification | Deployed host, read-only; a live run only if a screen cannot render otherwise |

Locked from 006 (unchanged): bounding boxes stay **read-only** in OCR review;
**preview ≠ apply** in preprocessing; **explicit** "mark review complete"; no
route deletions.

## 3. Ground truth (verified 2026-11-13)

Route reality differs from the tree described in `plans/006`:

- `/library` and the public catalog are **gone** (`84277d8`); book detail moved to
  `/books/[bookId]`; the admin catalog is `/admin/books`; bulk operations moved to
  `/admin/bulk`; `/pending-approval` was added. Nav is 4 links
  ([app-navbar.tsx:12-27](frontend/src/components/shared/app-navbar.tsx#L12)).
- Every workflow stage page is **byte-count identical** to the 006-era audit, so
  those findings stand.
- `frontend/src/app/dashboard/page.tsx` (766) and
  `frontend/src/app/admin/users/page.tsx` (990) have **changed** since the 006
  audit — re-read before editing; the older analysis of those two is stale.

Confirmed against the deployed app (`56afbff`): two books (one `uploaded`, one
`awaiting_review`, each 119 pages), 20 jobs, 1 metadata record. The dashboard
visibly renders **two** "Your books" headings and **two** "Your jobs" headings.

## 4. Findings (verified on the live tree / deployed app)

### 4.1 Built-but-unadopted primitives — the root cause

| Primitive | Adoption |
|---|---|
| [save-bar.tsx](frontend/src/components/shared/save-bar.tsx) | **0 usages.** Save is hand-rolled twice ([metadata-form.tsx:328](frontend/src/components/metadata/metadata-form.tsx#L328), [text-editor.tsx:139](frontend/src/components/ocr/text-editor.tsx#L139)) |
| [data-table.tsx](frontend/src/components/shared/data-table.tsx) | 1 page ([admin/jobs](frontend/src/app/admin/jobs/page.tsx)). [admin/books](frontend/src/app/admin/books/page.tsx) and [admin/users](frontend/src/app/admin/users/page.tsx) hand-roll the same table |
| [progress.tsx](frontend/src/components/shared/progress.tsx) | 3 hand-rolled copies: [admin/jobs](frontend/src/app/admin/jobs/page.tsx), [admin](frontend/src/app/admin/page.tsx), [dashboard](frontend/src/app/dashboard/page.tsx) |
| `JobProgressCard` + `useJobProgress` | Adopted by 3 pages; [ocr-processing](frontend/src/app/books/[bookId]/ocr-processing/page.tsx) and [metadata-review](frontend/src/app/books/[bookId]/metadata-review/page.tsx) hand-roll spinner + % |
| [stat-card.tsx](frontend/src/components/shared/stat-card.tsx) | dashboard only; [admin](frontend/src/app/admin/page.tsx) re-wraps it, `/admin/bulk` hand-rolls `StatsCard` |
| `Banner` ([empty-state.tsx](frontend/src/components/shared/empty-state.tsx)) | 2 usages; ~7 files hand-roll the same alert |

Net: ~8 distinct status presentations, 3 progress bars, 2 save surfaces, 3
renderings of "a job".

### 4.2 Chrome and heading hierarchy differ per page

- No `<h1>`: `admin/users` (title is a Card `h2`); `ocr-review` hand-rolls one
  ([l.188](frontend/src/app/books/[bookId]/ocr-review/page.tsx#L188));
  `dashboard` hand-rolls the whole header ([l.507](frontend/src/app/dashboard/page.tsx#L507))
  and duplicates "Your books"/"Your jobs" headings.
- `admin/books` and `admin/jobs` use `PageHeader` **and** a Card titled "Filters"
  → the word renders twice.

### 4.3 Workflow navigation is the weakest area

- The 7-chip strip ([workflow-stepper.tsx](frontend/src/components/shared/workflow-stepper.tsx))
  is a book's only navigation, overflows below ~768px, and two of its seven steps
  are not user steps: `/ocr-processing` auto-redirects,
  `/extracting-pages` is not a step at all.
- Each page invents its own next/prev story: [metadata-review](frontend/src/app/books/[bookId]/metadata-review/page.tsx)
  (header actions **and** a footer), [llm-config](frontend/src/app/books/[bookId]/llm-config/page.tsx),
  [ocr-review](frontend/src/app/books/[bookId]/ocr-review/page.tsx).

### 4.4 The two money screens are cramped

- **OCR review:** `h-screen` with nested panes; the page strip renders **every
  page as a Button** — with the production 119-page book that is 119 buttons in an
  `overflow-x-auto` row.
- **Preprocessing:** triple pane inside 1280px; thumbnail rail `max-h-[600px]`
  *and* canvas `max-h-[600px]`; a very long settings column.
- **Metadata review:** 49 full-width fields; evidence (`source_page_number`,
  `source_text_snippet`) surfaced only as a tooltip; a prominent click-to-copy
  bounding-box viewer ([l.356-407](frontend/src/app/books/[bookId]/metadata-review/page.tsx#L356))
  that is not bound to the field being edited.

### 4.5 One entity, three renderings

A job is rendered as: the dashboard table, the `admin/jobs` `DataTable`, and the
per-book card list ([jobs](frontend/src/app/books/[bookId]/jobs/page.tsx)).
[book detail](frontend/src/app/books/[bookId]/page.tsx) adds three hand-rolled
`-mx-5` list renderers plus four copies of the same chip pill and a local
`ocrState` machine.

### 4.6 Dead code

[workflow-store.ts](frontend/src/stores/workflow-store.ts) (131 lines) is
referenced by **nothing**. `SaveBar` is unused. Both are from the 006 push.

### 4.7 Minor but visible

- Upload surfaces the same error inline **and** as a toast
  ([upload:68](frontend/src/app/upload/page.tsx#L68)).
- Auth pages mix `Button loading` with manual spinners; `/pending-approval` is
  fine (already `AuthCard`).
- `/admin/bulk` wraps itself in a second full-page shell.
- The job-type chip renders OCR and LLM **identically**
  ([jobs:134-139](frontend/src/app/books/[bookId]/jobs/page.tsx#L134)).
- Token discipline is otherwise good: **zero** raw Tailwind palette leaks.

## 5. Target architecture

1. **Layout modes.** `PageContainer` gains `layout: "reading" | "workspace" |
   "gallery"`; `workspace`/`gallery` go full-bleed with their own inner gutters.
   Navbar inner width stays `content-max`.
2. **Stage rail.** New `StageRail` component; `WorkflowShell` renders rail + the
   page's own header. Monitor jobs appear as indented child rows under
   `pages`/`ocr`. Mobile: sticky bar + sheet.
3. **One save model.** `SaveBar` used by metadata review, OCR review and
   preprocessing; hand-rolled footers deleted.
4. **One status + progress vocabulary.** `StatusBadge` + `Progress` everywhere;
   the 3 hand-rolled bars deleted; one canonical book-state label set reused by
   dashboard, book detail, admin tables and filters.
5. **One data surface.** `DataTable` adopted by `admin/books`, `admin/users`,
   `dashboard` and book detail; add `Chip` and `Toolbar` primitives; delete
   `workflow-store.ts`.
6. **Evidence pane** (metadata review) bound to the focused field: source page
   image, highlighted snippet, confidence, method, "open in OCR review here".
7. **Filmstrip** (OCR review): collapsible, per-page OCR/low-confidence markers.
8. **Presets** (preprocessing): `Original`, `Standard scan`, `Faded print`,
   `High-contrast text` — partials into the existing `updateConfig`.
9. **Design kit** at `/admin/design` (admin-gated) rendering every primitive in
   its states.

Constraints: **no new npm dependencies**; keep focus rings, `aria-current`,
reduced-motion and forced-colors behaviour; read
`frontend/node_modules/next/dist/docs/` before writing route/layout code
(`frontend/AGENTS.md`).

## 6. Phases

### Phase 0 — Foundations (no visible change to existing screens)

- Layout modes on `PageContainer`; build `StageRail` + `StepMarker`; generalise
  `DataTable`; add `Chip`/`Toolbar`; delete `workflow-store.ts` (with its test);
  create the `/admin/design` kit; add Design to the admin nav (additive,
  admin-only).
- Exit: `pnpm lint`, `tsc --noEmit`, `pnpm test` green; design kit renders.

**Shipped 2026-11-13:** `PageLayout` modes plus `Chip`/`Toolbar`/`StepMarker`/
`StageRail` added; `DataTable` gained `loading`/`empty`/`stickyHeader`/`maxHeight`;
`/admin/design` route + admin nav link; `stores/workflow-store.ts` and its test
deleted (0 references). `SaveBar` adoption and the shell/stepper swap are
Phase 1–2.

### Phase 1 — Workflow shell

- Replace the stepper with the rail on all book pages; page shell + `PageHeader`
  everywhere; one navigation footer pattern; monitors shown as sub-rows.
- Exit: every stage page shows the same rail, the same header anatomy and the
  same footer; no route change.

### Phase 2 — Workflow screens

- select-pages (`gallery`), preprocessing (`workspace` + presets + before/after +
  sticky apply), OCR review (`workspace` + filmstrip + toolbar), metadata review
  (evidence pane + section nav + filter empty/low-confidence + sticky `SaveBar`),
  llm-config (collapsed prompts), the two monitor pages folded into sub-states.
- Exit: each screen usable on a 119-page book without a nested scroll trap.

### Phase 3 — book detail + dashboard  ← **milestone push #1**

- `PageHeader`, `DataTable`, one status vocabulary, tabs or 2-column on book
  detail; dashboard on `PageHeader` + `StatCard` + `DataTable`, duplicate
  headings removed.

### Phase 4 — admin + `/admin/bulk`

- `DataTable` for books/users/jobs; one filter bar (kill the duplicated "Filters"
  label); `/admin/bulk` onto the single shell; `admin/users` re-read first.

### Phase 5 — auth light pass + verification  ← **milestone push #2**

- Shared error surface; `Button loading` everywhere; then deployed-host QA and
  the docs updates.

## 7. File map

**New:** `components/shared/stage-rail.tsx`, `components/shared/chip.tsx`,
`components/shared/toolbar.tsx`, `app/admin/design/page.tsx`,
`components/metadata/evidence-pane.tsx`, `components/ocr/page-filmstrip.tsx`,
`components/preprocessing/presets.ts`.

**Reworked:** `components/shared/{card,data-table,workflow-shell,progress,empty-state}.tsx`,
`components/ocr/text-editor.tsx`, `components/metadata/metadata-form.tsx`,
`app/books/[bookId]/{page,select-pages,preprocessing,ocr-processing,extracting-pages,ocr-review,llm-config,metadata-review,jobs}/*`,
`app/{dashboard,upload,login,register,forgot-password,reset-password,verify-email}/page.tsx`,
`app/admin/{page,books/page,jobs/page,users/page,bulk/page}.tsx`, `lib/*`.

**Deleted:** `stores/workflow-store.ts`; the three hand-rolled progress bars; the
hand-rolled save footers.

## 8. Verification

- Per phase: `pnpm lint`, `tsc --noEmit`, `pnpm test`; deployed-host screenshots
  of the affected screens.
- Final: walk the deployed happy path on a real book
  (upload → select → preprocess → OCR → correct → LLM → metadata) plus the
  failure paths (cancel, Ollama down, re-run OCR); keyboard-only pass on the rail,
  filmstrip, evidence pane and `SaveBar`; light and dark mode on every changed
  screen.
- Docs: `docs/user-guide.md`, `docs/known-issues.md`; the design kit is the
  living reference.

## 9. Risks

- **Shared tree.** Other sessions and stale search results; re-read before edit,
  stage only touched files, no bare `git stash`.
- **Rail + monitor sub-rows** must not regress the 006 rule that the processing
  routes remain real routes.
- **Milestone deploys**: phase 3 and phase 5 only, so production is never a
  half-redesigned app.
- **`workspace` full-bleed** with the sticky navbar can reintroduce scroll traps —
  verify no page scrolls the body while an inner pane scrolls.
- Re-reading `dashboard` and `admin/users` may surface analysis drift; treat the
  code as truth.

## 10. Out of scope

OCR accuracy, Telugu/Hindi expansion, pgvector search, backend behaviour, auth
architecture (only presentation), and the home page (already good).

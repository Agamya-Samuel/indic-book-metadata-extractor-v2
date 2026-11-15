# 015 — Integrated OCR Reference and Metadata Review

## Status

Implemented 2026-11-15. Design agreed 2026-11-14. Phases 1–4 landed in the
frontend; Phase 5 is verified by `npm run lint`, `npx tsc --noEmit`, and
`npm test` (255 passing). No backend changes.
Extends Phase 2 of [008](008-ui-ux-composition-redesign.md) (the evidence pane grows
into a book-wide OCR reference).

## Problem

OCR text and extracted metadata are reviewed on separate pages. When a field is
empty or incomplete, the reviewer leaves metadata review, finds the passage on the
OCR review page, copies it, and comes back. The evidence card's "Open in OCR review"
link always lands on page 1, so even a field that does have provenance costs a full
re-discovery.

## What exists

- **OCR review** ([ocr-review/page.tsx:284](../frontend/src/app/books/%5BbookId%5D/ocr-review/page.tsx#L284)):
  workspace layout with a filmstrip, page canvas (60%) and word-level text editor
  (40%). OCR is fetched one page at a time (`getOcrResult`); the page index is
  component state, so the route cannot be deep-linked today.
- **Metadata review** ([metadata-review/page.tsx:360](../frontend/src/app/books/%5BbookId%5D/metadata-review/page.tsx#L360)):
  reading layout; a top evidence card bound to the focused field; then ~50 fields in
  8 collapsible batches with confidence dots; fixed SaveBar.
- **Bulk OCR data is already one request away.** `GET /books/{id}/pages?include_ocr=true`
  returns per-page `ocr_text` (corrected preferred) and `ocr_confidence`
  ([books.py:367](../backend/app/api/books.py#L367)). A 119-page book is two requests.
- **Provenance is sparse.** Evidence rows only exist for non-empty fields
  ([llm_tasks.py:196](../backend/app/tasks/llm_tasks.py#L196)), and LLM-extracted
  values are persisted with `source_page_number=None` and no snippet
  ([llm_service.py:496](../backend/app/services/llm_service.py#L496)). Only the five
  regex/dictionary fields (isbn, pages, publication_date, publisher, language) have
  a source page. The fields a reviewer most needs help with are therefore exactly
  the ones with no evidence page — the pane must support browsing and search, not
  just evidence-following.

## Decisions (agreed with the user)

1. **Whole-book, searchable corpus**, loaded when the pane opens and cached.
2. **Read-only OCR** in the pane; corrections stay in OCR review, reached by a
   `?page=N` deep link.
3. **Persistent, collapsible, resizable split** on desktop; bottom sheet below `lg`.
4. **Filters** for missing/uncertain fields plus a next-missing step.
5. **Page image tab**, **copy** and **append-only insert** actions.
6. Split stays down to `lg` (1024px) with field labels stacked; sheet below that.

## Alternatives considered

| Approach | Why not |
| --- | --- |
| On-demand drawer | Overlays or squeezes the input being edited; toggling per field is the friction we are removing. Kept only as the sub-`lg` fallback. |
| Inline per-field expansion | No browsing or search; long passages truncated; repeated expansion for a lookup-heavy book. |
| Tabs (Fields / OCR) | Preserves context but not simultaneity; same back-and-forth, one level down. |
| Bottom Dock | Fights the long form and the fixed SaveBar on desktop. |
| Embed the OCR word editor | Word-as-button rendering breaks text selection/copy; editing belongs to the OCR stage. |

## Design

### Layout

- `metadata-review` switches `PageContainer` to `workspace`; `PageHeader` spans the
  full width and the split sits below it.
- `lg+`: CSS grid `[form minmax(0,1fr)] [6px separator] [pane clamp(320px, w, 640px)]`.
  Default `w = 420px`; below `xl` the field label stacks above the input
  (`metadata-form` currently goes row at `sm+`).
- Pane is sticky (`top: calc(var(--nav-height) + 1rem)`), viewport-height, with its
  own scroll. The form scrolls with the page — one page scroll, one explicit pane
  scroll region. Text container carries bottom padding so the fixed SaveBar never
  covers the last lines.
- `<lg`: full-width form, native `<dialog>` bottom sheet (`showModal()` for focus
  trap, Esc, scrim). Fields with a source page get a small "Source p.N" chip; a
  header "OCR" button opens the sheet. Inserting closes the sheet and focuses the
  field. Field focus never auto-opens the sheet.
- Collapse leaves a slim vertical "OCR" tab; width and collapsed state persist in
  `localStorage` (`metadata-review:pane-width`, `metadata-review:pane-collapsed`),
  read in an effect to avoid hydration mismatch.

### Separator

`role="separator"`, `aria-orientation="vertical"`, `aria-valuemin/max/now`,
`tabIndex=0`, `aria-controls` the pane. Arrow keys ±16px (Shift ±64), Home/End to
clamp, Enter/Space toggles collapse, double-click resets to 420px. Clamp depends on
container width (pane ≤ 50%).

### Pane

Header: page prev/next, "Page N of M" with a jump input, confidence chip, collapse
button, and "Open in OCR review" (`?page=N`).

Tabs (proper `tablist`/`tab`/`tabpanel`):

- **Text** — the page's corrected (or raw) OCR text as plain selectable text,
  `dir="auto"`, `whitespace-pre-wrap`. No word buttons, so native selection and copy
  work.
- **Page image** — the existing `getPageImageUrl(page.id)` image, contained to the
  pane width.

Search: `type="search"`, ~150ms debounce, case-insensitive `indexOf` scan over the
cached corpus. Results grouped by page (`page N · k matches`), capped at 50 pages;
clicking jumps to the page and highlights every match with `<mark>` (exact offsets
from the same scan). Summary line is `aria-live="polite"`.

Evidence context, when the focused field has evidence:

- chips: confidence, extraction method, source page;
- the snippet as a quoted block (not inline-highlighted — snippets may be truncated
  and whitespace-differing);
- auto-jump to the source page on focus, without stealing focus from the input.

When the focused field has no source page: "No source page was recorded for this
field" plus the search input focused on demand. Secondary heuristic for non-empty
values (≥3 chars): client-side search of the value; list up to five "appears on
page N" chips. Labelled as a hint, never as provenance.

Text selection is captured on `mouseup`/`keyup`/`touchend` inside the text container
so clicking an action button does not lose it. Actions:

- **Copy** — copies the captured selection, else the page text;
  `navigator.clipboard.writeText`, toast on success/failure.
- **Append to <field>** — disabled until a field has been focused; appends the
  selection (trimmed) with `\n` for long-text fields and a space otherwise, then
  focuses the field with the caret at the end and scrolls it into view. Empty field
  ⇒ effectively fills it; an existing LLM value is never overwritten.

States: corpus loading (skeleton, nav disabled), page without OCR text, empty corpus
(link to OCR review), fetch error with retry.

### Metadata form

- Filter chips inside `metadata-form` (it owns live draft values): All (n) /
  Missing (n) / Uncertain (n), plus "Next missing". Missing = blank after drafts;
  Uncertain = real confidence `< 0.5` or a sentinel value (`n/a`, `not found`,
  `none`, `unknown`). The currently focused row stays visible after it stops
  matching, so the row does not vanish mid-edit. While a filter is active, sections
  containing matches are forced open.
- One count source: replace `onDirtyCountChange` with `onStatsChange` reporting
  `{ dirty, missing, uncertain }`; the page's confirm dialog reads these instead of
  its own persisted-value count. Extract the `0.5` threshold into one helper used
  by the form and the dialog.
- `CollapsibleSection` gains an optional `forceOpen` (open while true); its state
  stays uncontrolled otherwise.
- `onRegisterActions` grows `appendToField(fieldName, text)`; inputs already forward
  refs, so focusing and caret placement are direct DOM calls.
- Small "Source p.N" chip on rows with `source_page_number`, calling
  `onShowSource(fieldName)` (maps to the same jump path as focus, for touch).

### Deep link

`ocr-review` reads `?page=<page_number>` and applies it once when pages first load,
clamped to `[1, length]`; `jobId` handling is unchanged.

## Files

New:

- `frontend/src/lib/ocr-corpus.ts` — corpus build, `searchCorpus`, match/segment
  helpers (pure, unit-tested).
- `frontend/src/hooks/use-ocr-corpus.ts` — React Query wrapper over
  `getAllBookPages(id, { include_ocr: true })`, `enabled` when the pane has been
  opened once; long `staleTime` (10 min).
- `frontend/src/components/metadata/review-workspace.tsx` — split, separator,
  collapse, sheet, persistence.
- `frontend/src/components/metadata/ocr-reference-pane.tsx` — pane body shared by
  split and sheet.

Modified:

- `frontend/src/app/books/[bookId]/metadata-review/page.tsx` — workspace layout,
  corpus query, pane wiring, remove the evidence card, SaveBar clearance, counts.
- `frontend/src/app/books/[bookId]/ocr-review/page.tsx` — `?page=` deep link.
- `frontend/src/components/metadata/metadata-form.tsx` — filters, stats callback,
  `forceOpen`, append action, source chip.
- `frontend/src/components/shared/collapsible-section.tsx` — `forceOpen`.

No backend changes and no new npm dependencies.

## Phases

### Phase 1 — Plumbing (no visible change)

- `?page=` deep link in OCR review; `ocr-corpus.ts` + unit tests;
  `use-ocr-corpus.ts`.
- Exit: `/books/{id}/ocr-review?page=12` lands on page 12 (clamped); lint, `tsc`,
  tests green.

### Phase 2 — Pane replaces the evidence card

- `OcrReferencePane` (tabs, nav, search, highlight, evidence header, copy, append),
  `ReviewWorkspace` with a fixed-width split at `lg+` and a `<dialog>` sheet below;
  remove the evidence card; wire append through the form; SaveBar clearance.
- Exit: on the 119-page book, an empty field can be researched and appended without
  a route change; mobile sheet inserts and closes; existing tests pass.

### Phase 3 — Resize, collapse, keyboard

- Separator keyboard/a11y, persistence, collapse tab, sticky/pane-height polish,
  breakpoint check at 1024/1279/1280.
- Exit: width and collapsed state survive reload; pane never covers the edited
  input; keyboard-only pass through nav, search, results, tabs, actions.

### Phase 4 — Field navigator

- Filter chips + counts + next-missing, `forceOpen`, unified stats and threshold,
  source chips, value-locator hint for unattributed values.
- Exit: filter → fix → row disappearance does not lose the focused row; confirm
  dialog and chips agree.

### Phase 5 — Verification and docs

- Tests for search, highlight, append semantics, filters, sheet; manual structural
  pass on the deployed host; add a pointer from 008 Phase 2 to this plan.

## Verification

- `cd frontend && npm run lint && npx tsc --noEmit && npm test`
- Backend untouched; no pytest change expected.
- Unit: corpus search (Latin + Telugu, repeated matches, no match, offsets),
  highlight segmentation, append separator/trim, filter counts, deep-link clamp.
- Component (Testing Library): pane states, evidence jump, copy/append enablement,
  sheet open/insert/close, filters keep the focused row.
- Manual, deployed host (see the UI verification constraints): snapshot + DOM
  assertions at 1360px (split), ~1100px (split, stacked labels), ~1006px (sheet);
  confirm computed styles, `window.innerWidth`, sticky offsets, SaveBar clearance.
  Pixel judgement (density, typography) is handed over as screenshots; the agent
  cannot judge it.

## Risks and limits

- **Most values have no page provenance** (LLM). Mitigated by search + value
  locator; a backend attribution pass is a follow-up.
- **Corpus payload** grows with book length (~0.5 MB at 119 pages). Loaded on pane
  open and cached; books beyond ~400 pages should get a backend search endpoint.
- **Phrase search does not cross line breaks** (raw OCR text, no whitespace
  normalization) in v1.
- **Snippet highlighting** is skipped; snippets may be truncated or whitespace-
  different, so only page-level jumps are claimed.
- **Two scroll regions** by design; the pane is the only nested scroll and is
  labelled.
- Forced-colors mode: `<mark>` needs a border fallback so highlights remain visible;
  reduced-motion respected for the sheet.
- Selection capture relies on `mouseup`/`keyup`; verify in Chromium and Firefox.

## Out of scope

Editing OCR corrections in the pane; changing the OCR review editor; backend OCR
search or page attribution; word-box overlays in metadata review; a mobile
field-by-field wizard; new dependencies.
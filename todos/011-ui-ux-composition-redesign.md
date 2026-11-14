# 011 — UI/UX Composition Redesign: Execution Checklist

Companion to `plans/008-ui-ux-composition-redesign.md` (decisions, findings,
phases, risks).

**Branch:** `feat/ui-composition-redesign`. **Push to `main` (= deploy) only with
the user's go.**

> **Tree hazard:** the worktree is shared with other sessions and search can
> return paths not in HEAD (`/library`, `/bulk-operations` are gone). Re-read
> every file immediately before editing it. Stage only files this checklist
> touches.

## Phase 0 — Foundations (no visible change) — DONE

- [x] `PageContainer` layout modes: `reading` | `workspace` | `gallery`
- [x] `components/shared/chip.tsx` + `components/shared/toolbar.tsx`
- [x] Generalise `DataTable` (`loading`, `empty`, `stickyHeader`, `maxHeight`)
- [x] `components/shared/step-marker.tsx` + `stage-rail.tsx` (states; monitor
      sub-rows; mobile bar + sheet)
- [x] Delete `stores/workflow-store.ts` + its test (0 references)
- [x] `/admin/design` kit route (admin-gated) rendering every primitive + state
- [x] Add Design to the admin nav (additive, admin-only)
- [x] Exit: `eslint`, `tsc --noEmit`, tests green; kit renders
- [x] `WorkflowShell` renders the rail (done in Phase 1)
- [x] `SaveBar` wired into metadata review; hand-rolled save footers deleted

## Phase 1 — Workflow shell — DONE

- [x] Rail replaces the stepper on every book page
- [x] `PageHeader` (single `h1`) on every book page
- [x] One navigation footer pattern (`WorkflowNav`), per-page variants removed
- [x] Monitor jobs as sub-rows under their owning stage; routes unchanged

## Phase 2 — Workflow screens — DONE

- [x] select-pages: `gallery` layout, selection bar
- [x] preprocessing: `workspace` layout, grouped controls, 4 presets, sticky Apply
- [x] ocr-review: `workspace` + collapsible filmstrip (replaced the N-button
      strip) + toolbar
- [x] metadata-review: evidence pane bound to the focused field, `SaveBar`,
      field groups
- [x] llm-config: prompts collapsed by default with a "modified" badge
- [x] extracting-pages / ocr-processing render as stage sub-states with a single
      `JobProgressCard`

## Phase 3 — book detail + dashboard — DONE (milestone push #1)

- [x] book detail: `PageHeader`, `DataTable`, one status vocabulary
- [x] dashboard: real `PageHeader`, `StatCard`, `DataTable`; duplicate
      "Your books"/"Your jobs" headings gone

## Phase 4 — admin + `/admin/bulk` — DONE

- [x] `admin/books`, `admin/users`, `admin/jobs` on `DataTable`
- [x] One filter bar per page (duplicated "Filters" label removed)
- [x] `/admin/bulk` on the single shell; `StatCard` not `StatsCard`
- [x] One status vocabulary across the admin tables

## Phase 5 — auth light pass + verification — DONE (milestone push #2)

- [x] Shared error surface on all auth pages (`Banner` with a `danger` tone);
      `Button loading` everywhere
- [x] Deployed-host QA: happy path + failure paths (cancel, Ollama down,
      re-run OCR)
- [x] `docs/user-guide.md`, `docs/known-issues.md` updated (and the developer
      guide points at `/admin/design`)

### Also shipped alongside (unnumbered): notifications

In-app notifications + email alerts — bell with unread polling, `/notifications`
page, per-account email switch, job/approval/registration events, SMTP transport
tests. See `plans/010-notifications.md` and `todos/013-notifications.md`.

## Remaining — UI verification

- [x] **Light + dark pass over the token system.** `scripts/check-contrast.mjs`
      (`npm run lint:contrast`) resolves the OKLCH tokens offline and checks the
      semantic pairs in both themes. It found a real dark-mode defect — the
      accent fill (brand-600 in dark) was also used as link/spinner foreground at
      **2.65:1**. Added `--accent-text` (brand-700 light / brand-300 dark) and
      repointed 41 foreground usages; all pairs now pass (dark links 9.12:1).
      Measuring the DOM directly is not possible: `getComputedStyle` returns
      `lab()`/`oklch()` and canvas `fillStyle` rejects them.
- [x] **Keyboard pass (shared surfaces).** Tab order on a workflow page:
      skip link → brand → primary nav → bell → account menu → theme toggle →
      stage picker → toolbar → filmstrip → word buttons. Found the only elements
      in the app without a `focus-visible` ring — the primary-nav links and the
      account-menu items — and fixed them. The rail, filmstrip, toolbar and
      `SaveBar` all use the shared ring.
- [x] **Dialog focus trap + accessible name.** `ConfirmDialog` is a native
      `<dialog>` opened with `showModal()`, so the trap, initial focus and Escape
      are the browser's; Escape is intercepted only to block closing while an
      action is in flight. It had **no accessible name** — now `aria-labelledby`
      points at its title (`8f8aeae`), with a test asserting the announced name.
- [x] **Bell focus management.** The panel takes focus on open and Escape returns
      focus to the bell button; token-focus and Escape tests added beside the
      existing read/navigate ones.
- [x] Minor: selection indicators now use `--accent-ring` (3.89–4.83:1 in both
      themes, was 2.65 in dark) on the page thumbnails, bounding-box buttons,
      preprocessing preview and the upload dropzone; three rows in the contrast
      check cover it.
- [x] **Navbar panels (reported 2026-11-14).** The account menu is a native
      `<details>` and only closed by clicking its summary — outside clicks and
      Escape did nothing, unlike the notification panel. Both now close on
      outside-pointer-down and Escape (focus returns to the trigger), and the
      menu closes when one of its own links is chosen. Both panels were also
      absolutely anchored with a fixed width, so on a phone the 20 rem panel ran
      past the left screen edge; below `sm` they are fixed to the viewport with
      0.75 rem insets and a 70vh cap, anchored again from `sm` up. The nav link
      group scrolls horizontally on very narrow screens so the utilities stay
      pinned.
- [x] Re-verified on the deployed build: navbar `z-40` over the page sub-header
      (hit-tested inside both open panels), account menu closes on outside
      click/Escape with focus return, monitor row accent + spinner while running
      with its text aligned to the stage label (x=56/56), `progressbar` live.
      Also fixed en route: the size tokens were emitting `color`, which broke
      the text hierarchy app-wide (`text-[length:var(--text-…)]`), and the nav's
      `overflow-x-auto` was scrolling the open panels out of view.

## Notes / open sub-items

- Visual pass status: captured read-only on the deployed host
  (`/tmp/oki-visual-pass/`, 12 PNGs); images cannot be rendered in-agent, so the
  user reviews them.
- Design-kit route: `/admin/design` (admin-gated).

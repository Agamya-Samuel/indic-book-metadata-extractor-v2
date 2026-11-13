# 011 — UI/UX Composition Redesign: Execution Checklist

Companion to `plans/008-ui-ux-composition-redesign.md` (decisions, findings,
phases, risks). Work top-to-bottom; do not skip the exit criteria.

**Branch:** `feat/ui-composition-redesign`. **Push to `main` (= deploy) only at
Phase 3 and Phase 5, with the user's go.**

> **Tree hazard:** the worktree is shared with other sessions and search can
> return paths not in HEAD (`/library`, `/bulk-operations` are gone). Re-read
> every file immediately before editing it. Stage only files this checklist
> touches.

## Phase 0 — Foundations (no visible change)

- [x] `PageContainer` layout modes: `reading` | `workspace` | `gallery`
- [x] `components/shared/chip.tsx` + `components/shared/toolbar.tsx`
- [x] Generalise `DataTable` (`loading`, `empty`, `stickyHeader`, `maxHeight`)
- [x] `components/shared/step-marker.tsx` + `stage-rail.tsx` (states; monitor
      sub-rows; mobile bar + sheet) — built, not yet wired
- [x] Delete `stores/workflow-store.ts` + its test (0 references)
- [x] `/admin/design` kit route (admin-gated) rendering every primitive + state
- [x] Add Design to the admin nav (additive, admin-only)
- [x] Exit: `pnpm lint`, `tsc --noEmit`, `pnpm test` green; kit renders
- [ ] Rework `WorkflowShell` to render the rail → moved to Phase 1
- [ ] `SaveBar` wired into surfaces; delete hand-rolled save footers → Phase 2

## Phase 1 — Workflow shell

- [ ] Rail replaces the stepper on every book page
- [ ] `PageHeader` (single `h1`) on every book page
- [ ] One navigation footer pattern (kill per-page next/prev variants)
- [ ] Monitor jobs as sub-rows under `pages`/`ocr`; routes unchanged
- [ ] Exit: identical rail + header + footer anatomy across stages

## Phase 2 — Workflow screens

- [ ] select-pages: `gallery`, virtualised thumbs, sticky selection bar, range-select
- [ ] preprocessing: `workspace`, grouped controls, 4 presets, before/after, sticky Apply
- [ ] ocr-review: `workspace` + collapsible filmstrip (replace N-button strip) + toolbar
- [ ] metadata-review: evidence pane bound to focused field, section nav, filter
      empty/low-confidence, `SaveBar`, denser field layout
- [ ] llm-config: prompts collapsed by default + "modified" badge + reset
- [ ] extracting-pages / ocr-processing: fold into stage sub-states; single
      `JobProgressCard`
- [ ] Exit: 119-page book usable with no nested scroll trap

## Phase 3 — book detail + dashboard  ← **milestone push #1**

- [ ] book detail: `PageHeader`, `DataTable`, one status vocabulary, tabs/2-col
- [ ] dashboard: real `PageHeader`, `StatCard`, `DataTable`; remove duplicate
      "Your books"/"Your jobs" headings
- [ ] Exit: both screens consistent with the workflow shell; user approves deploy

## Phase 4 — admin + `/admin/bulk`

- [ ] `admin/books`, `admin/users` (re-read first — 990 lines), `admin/jobs` on `DataTable`
- [ ] One filter bar per page (remove the duplicated "Filters" label)
- [ ] `/admin/bulk` onto the single shell; `StatCard` not `StatsCard`
- [ ] One status vocabulary across the three tables

## Phase 5 — auth light pass + verification  ← **milestone push #2**

- [ ] Shared error surface on all auth pages; `Button loading` everywhere
- [ ] Deployed-host QA: happy path + failure paths (cancel, Ollama down, re-run OCR)
- [ ] Keyboard-only pass: rail, filmstrip, evidence pane, `SaveBar`
- [ ] Light + dark mode on every changed screen
- [ ] `docs/user-guide.md`, `docs/known-issues.md` updated
- [ ] Commits: logical increments, heading + body, no co-author lines

## Notes / open sub-items

- Visual pass status: captured read-only on the deployed host
  (`/tmp/oki-visual-pass/`, 12 PNGs); images could not be rendered in-agent, so
  the user reviews them. A live run (Q7-ii) is deferred — the two monitor screens
  are fully known from code and are being folded into sub-states anyway.
- Design-kit route chosen: `/admin/design` (admin-gated).

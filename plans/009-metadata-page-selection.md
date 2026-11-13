# 009 — Metadata-Page Selection (front/back window) POC → MVP

- **Date:** 2026-11-13
- **Status:** POC run on `test-node-1` (2026-11-13). Labelling was flawed (see below); `llm_text` is the promising detector. MVP plumbing written, not adopted.

## POC result (2026-11-13)

Ran on 4 Telugu + 4 Hindi books (front 12 / back 4), detectors `fixed` / `heuristic` / `llm_text`.

- **`fixed`:** 8 pages · **`heuristic`:** 10.5–14 pages · **`llm_text`:** 1.5 pages.
- The heuristic **barely fires on noisy OCR** (pages are short, so `is_body_page` rarely trips) and keeps *more* pages than `fixed` — useless as written.
- The **`llm_text` judge is ~5× more selective** than the fixed window (1.5 vs 8 pages) — the only promising lever for cutting prompt noise.
- **The metric was invalid:** silver labels required an exact GT identity value in the OCR text, which OCR errors blank (silver=0 for every book → precision 0, recall meaningless). Patched the labeller to fuzzy token overlap but did not re-run (cost vs the accuracy eval).

**Verdict:** do **not** adopt the heuristic. `llm_text` is worth re-running with the fuzzy labeller to confirm recall before any MVP. Low priority relative to the accuracy eval.
- **Motivation:** the extraction prompt is fed a fixed page window (first N + last M). Body-text pages add OCR noise and can crowd out the bibliographic front/back matter. We want to *choose* the metadata pages instead.

## Objective

Decide, per book, which pages carry bibliographic metadata (title / author / publisher / copyright / colophon), so the LLM sees those pages and not the body. Deliver a **measured POC** comparing detectors, then an **MVP** only if a detector beats the current fixed window.

## Approaches tested

| # | Detector | How |
|---|---|---|
| 1 | `fixed` | first 6 + last 2 (current behaviour) — baseline |
| 2 | `heuristic` | from each end, keep pages until the first *body-like* page (`len>1200` + `>14` lines + no metadata cue word) |
| 3 | `llm_text` | per page, ask the local model (gemma4, `think:false`) yes/no "is this bibliographic matter?" |
| 4 | `vlm_image` | per page image, ask a free OpenRouter vision model — **blocked** (see below) |

Shared logic lives in [`app/services/page_selection.py`](../backend/app/services/page_selection.py) (unit-tested); the POC script has its own copy so an experiment cannot change behaviour in place.

### Finding: free hosted VLMs cannot judge the page images (2026-11-13)

Tested two free OpenRouter models with the declared `image` input modality
(`google/gemma-4-26b-a4b-it:free`, `nvidia/nemotron-3.5-super-vl:free`): both
return HTTP 200 with **`image_tokens: 0`** and empty content for a base64 data
URL, and **HTTP 400** ("Received 400 status code when fetching image from URL")
for a public image URL (provider Google AI Studio). The key is valid (models
list returns 200). Conclusion: free image input is unusable here; a hosted VLM
would need a paid model. Not pursued.

## Silver labels

A page is a *metadata page* if its OCR text contains a known ground-truth
identity value (`label`/`title`/`author`/`publisher`/`place_of_publication`),
normalised as a substring. Limitation: derived only within the OCR'd window, so
recall beyond the window is unmeasured — but the baseline cannot reach it either,
so the comparison is fair.

## Metrics & decision rule

Per book: **recall** (metadata pages kept / metadata pages), **precision**
(kept pages that are metadata pages) and **pages kept**. Adopt a non-fixed
detector only if it matches `fixed`'s recall (≥ ~0.9) while cutting pages
kept — fewer pages, less noise, same coverage.

## MVP (if the POC wins)

Two-pass selection in the fill runner ([`node_gt_fill.py`](../backend/scripts/node_gt_fill.py),
`--select fixed|heuristic`): OCR the wide scan window (`--scan-front/--scan-back`),
run `select_pages` on the resulting text, then feed **only the selected pages** to
the LLM. `fixed` keeps today's behaviour. Not wired into production — this runner
is a GT/eval tool, not the app's extraction path.

## Success criteria

- POC reports recall/precision/pages for each detector on a tel+hin subset.
- A detector (or the LLM judge) beats `fixed` on pages-kept without losing recall.
- MVP runs one book end-to-end with the winning strategy and the GT merge still improves coverage.

## Next steps

1. Finish the deep fill; merge into the corpus.
2. Run the 3 feasible detectors on the subset; record numbers here + in `learnings/`.
3. Decide (fixed vs heuristic vs llm_text) and set the MVP default.
4. Run the accuracy evaluation on the enriched corpus.

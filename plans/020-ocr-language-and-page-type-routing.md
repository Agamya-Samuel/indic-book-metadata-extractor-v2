# 020 — OCR Language Integrity and Page-Type Routing

**Status:** complete for P0/P1 routing — A1/A2/A4, C1/C2/C3, the Latin/dominant-script reroutes, and the `TESSERACT_TESSDATA_DIR` fix are shipped. A3 (OSD preflight) and C4 (line detector) are deferred by measurement; fine-tuning remains gated by plan 019's Hindi GT/training work.
**Evidence:** [learnings/029](../learnings/029-ocr-language-routing-and-font-benchmarks.md) (this plan implements its P0–P1)
**Related:** [learnings/026](../learnings/026-ocr-accuracy-strategy-review.md) (dead settings/training path), [027](../learnings/027-default-preprocessing-upscale-benchmark.md) / [028](../learnings/028-line-model-preprocessing-benchmark.md) (preprocessing)
**Depends on:** [learnings/020](../learnings/020-ocr-engine-benchmark.md) (locked engine decision), [plans/019](019-ocr-accuracy-improvement.md) (Hindi GT/fine-tune phases)

## Problem

The wrong text is often produced by the **right engine reading the wrong language/page type**, not by a weak model:

- Uploads default to Telugu; there is no detection and no way to change a book's language.
- `LANGUAGE_MAP` sends every Telugu page to `tel+eng` and every Hindi page to `hin+eng`, injecting Latin into pure-script pages and raising Telugu consonant errors from 14.5 % to 24.5 %.
- All Telugu-language pages go to the Telugu-only line model, including English/bilingual covers where Tesseract reads at CER 0.002 and the line model at 0.880.
- The line model silently returns `""` for over-wide crops; production has no split/guard.
- A line-model failure falls back to `tel+eng` and completes normally, with only `pages.ocr_error` recording it.

Measured consequences (details in 029): Hindi-as-Telugu **CER 0.824, 77 % Latin**; line-model cover page **0.880**; split-wide recovery to **0.025**; pure-Telugu line model **0.163** vs Tesseract `tel` 0.295 / `tel+eng` 0.405.

## Principles

1. **Page-level, not book-level.** A bilingual book has Telugu body pages and English front matter; one global language flag cannot serve both.
2. **Do not add `eng` unless Latin is expected.** `+eng` is a page-level tool, not a default.
3. **Do not silently accept nonsense.** Empty/short output, wrong-script output, or a failed engine must fall back and be recorded.
4. **No new model work in P0.** Routing and guards first; fine-tuning stays in plan 019.
5. **Keep the audit honest.** Record engine, model, route reason, script shares and coverage per page.

## Phase A — Upload language integrity

| # | Item | Files | Done when |
|---|---|---|---|
| A1 | Remove the Telugu default from both upload paths | `frontend/src/app/upload/page.tsx`, `backend/app/api/books.py`, `frontend/src/lib/api.ts` | **Done** — API rejects a missing language with 422, the UI starts empty and blocks submit until one is chosen; upload tests updated (6 pass) |
| A2 | Add a book-language correction endpoint | `app/api/books.py` (new `PATCH /books/{id}/language`), `app/schemas/book.py`, `app/services/admin_service.py` | **Done** — `change_language()` reuses the re-run OCR path (cancel, clear OCR, reset from OCR, keep page images/metadata) and dispatches a new job when pages exist; 4 integration tests (before pages, no-op, invalid, with pages → `hin` dispatch) |
| A3 | Script preflight on upload | — | **Deferred.** Tesseract OSD measured 9/11 on Telugu pages (one mixed → Latin, one decorative → Arabic, one mirrored → error) and costs 1–2 s/page at full resolution. The implemented output-script reroutes use the actual OCR text and are strictly more reliable; OSD is only worth revisiting for orientation, not language selection |
| A4 | Config hygiene | `app/core/config.py`, `app/services/ocr_service.py`, docs | **Done** — `TESSERACT_TESSDATA_DIR` now passes `--tessdata-dir`; `DEFAULT_OCR_LANGUAGE`, `OCR_CUSTOM_MODEL_DIR`, and the unused `_is_dictionary_enabled` helper are removed; docs/compose/examples updated. Custom models use `TESSERACT_TESSDATA_DIR` (2 unit tests) |

### Script preflight: use OSD as a hint, not truth

Tesseract OSD on full-resolution pages measured 1–2 s/page and was right on **12/12** Hindi pages (Devanagari) but **9/11** Telugu pages (one mixed page → Latin, one decorative page → Arabic, one mirrored page → error). Therefore:

- Run OSD on a **downscaled** grayscale page (long edge ~1000 px) and only on a sample (upload: first 3 pages; routing: ambiguous pages only).
- Treat the result as a prior; confirm with the actual OCR text's script share.
- Use OSD's `Rotate` for orientation; it did not detect the known mirrored page, so mirror handling remains a separate preflight flag.

## Phase B — Page-type/script routing

### Routing matrix

| Detected page type | Primary | Language flag | Verify / reroute |
|---|---|---|---|
| Telugu body | line model, `ctc` | `tel` | If Telugu share <0.5 or coverage <0.5 → Tesseract `tel`, then `tel+eng` if Latin share >0.5 |
| Latin-heavy front matter/cover | Tesseract page OCR, `--psm 3/4` | `tel+eng` or `eng` | If expected script share low → `eng` |
| Mixed/bilingual | Tesseract `tel+eng` | `tel+eng` | Telugu line model only on lines with Telugu script |
| Hindi body | Tesseract `hin` | `hin` | If Latin share >0.5 → `hin+eng` / `eng` |
| English | Tesseract `eng` | `eng` | — |

Implementation:

- `_get_tesseract_lang` must become a **page** decision, not a book decision: either pass an explicit lang per page from the router, or add `route_language(page_script, book_language, latin_share)`.
- Do **not** change `LANGUAGE_MAP` globally to `tel`/`hin` and stop there: bilingual pages still need `+eng`. Change the call site.
- Use the OCR output's script shares as the verification signal. A single extra Tesseract pass is cheap (1–2 s/page) compared with a wrong 0.824-CER page.
- Cache the decision on the page/result (`ocr_route`, `ocr_engine`, `ocr_script`), so re-runs and audits are deterministic.

### Implemented (conservative first pass)

`process_page_image` now reroutes two cases:

1. **Latin-dominated line-model page → Tesseract.** Trigger: line output ≥80 % Latin and ≤20 % Telugu; keep Tesseract only if it returns ≥50 % of the text. On the 21-page bundle this changes **3/21 pages**: the 1857 cover 0.880→0.014, one Angleya page 0.060→0.000, one unchanged; pure Telugu untouched (bundle median 0.163→0.116, mean 0.243→0.199).
2. **Dominant-script Tesseract page → drop `+eng`.** Trigger: output ≥85 % of the book's script and ≤15 % Latin; keep the narrower model only if it retains ≥90 % of the text. Measured: Hindi **23/24 pages, median 0.090→0.061**; Telugu Tesseract **9/21 pages, median 0.331→0.272**.

Flag: `OCR_SCRIPT_ROUTING` (default true); 7 routing unit tests. Remaining in this phase: OSD/front-matter routing and recording the route on the OCR result.

### Page-type classifier

Start with two features that are already available after a first pass:

1. **Script share** from the OCR output (Telugu/Devanagari/Latin).
2. **Coverage** (non-empty lines / detected lines; output chars vs line area).

Only if those are insufficient, add a cheap image classifier for front matter/body (text density, connected components, margin structure). Do not use `--psm 11` for whole pages; 029/prior work show it reads borders as Latin rubble.

## Phase C — Line-model robustness

| # | Item | Files | Done when |
|---|---|---|---|
| C1 | Split over-wide line crops | `app/services/ocr_line_model.py` | **Done** — `_crop_width_limit()` + `_split_crop()` split at ~92 % of the model's limit with 16 px overlap and rejoin; 2 new unit tests (split / fitting crop stays whole); 381 unit tests pass |
| C2 | Coverage/empty-output guard | `app/services/ocr_line_model.py`, `app/tasks/ocr_tasks.py` | **Done** — total-empty output raises `LineModelEmptyOutput` and triggers the Tesseract fallback; `detected_lines`/`empty_lines` are returned for audit. A sub-50 % threshold was rejected by measurement: the minimum observed coverage was **0.66** (21 pages), and a 0.70 cutoff would fall back on `10879…p5`, where Tesseract scores **1.35 CER vs the line model's 0.41** |
| C3 | Record engine/model/coverage | `app/models/ocr_result.py`, `alembic/versions/017_ocr_route_metadata.py`, `app/tasks/ocr_tasks.py`, `app/schemas/page.py`, `app/api/pages.py` | **Done** — nullable `ocr_engine`, `ocr_route`, `ocr_coverage`, `ocr_script` columns (migration 017) are persisted per page and returned by the OCR API. The review UI still needs to display them |
| C4 | Optional: better line detector | — | **Deferred.** Oracle line crops vs detected Tesseract boxes differ by ~0.03 CER on clean synthetic pages; body-page error is dominated by recognition, not detection. The wide-line split already removes the one catastrophic detection failure. Revisit only if a measured book-level gap appears |

C1 evidence: wide synthetic pages improved from mean CER **0.548→0.203**; the 1857 cover from **0.880→0.025** (132→1071 characters). On the 21-page real bundle, **19/21 pages are byte-identical**, one body page is 0.006 worse, and the cover recovery moves the bundle median **0.163→0.116**. C1 is cheap and has no effect on normal body pages (they do not hit the limit; 027/028 saw 0 over-limit crops on body pages).

## Phase D — Measurement and gates

Use the frozen corpus:

- Telugu: 21 pages / 8 books with `wikisource_gt.json`; report both the whole bundle and the pure-Telugu/`latin_share` groups.
- Hindi: 24 IndicVisionBench pages; add ≥2 of our own Hindi books under plan 019 Phase 1 before a production claim.
- Front matter: at least the 1857 cover and one English copyright page; add 5–10 real front-matter pages.
- Metrics: page CER/WER, script shares, conjunct-cluster error, coverage, s/page, peak RAM, engine/route distribution.

**Gate G-ROUTE:**

1. Pure Telugu median CER ≤0.16 (no regression from 029).
2. Hindi median CER ≤0.07.
3. Latin-heavy front matter median CER ≤0.05 with Tesseract.
4. No page is persisted with empty output or coverage <0.5 without a recorded fallback.
5. Mislabel test: a Hindi book selected as Telugu is warned/re-routed, not scored at 0.82.
6. s/page increase ≤20 % overall; OSD/fallback only on ambiguous pages.
7. No book regresses by >2 absolute CER points.

## Non-goals

- No new OCR engine or VLM in this plan (Surya/IndicOCR/Sarvam are deferred; see 029 §6 and 019 Phase 5).
- No global binarization/denoise or shirorekha removal.
- No numeral-to-word normalization.
- No change to the locked engine decision (Telugu line model / Hindi Tesseract) unless a measured PoC beats it.

## Risks

| Risk | Mitigation |
|---|---|
| OSD is wrong on decorative/mixed pages (measured 9/11 Telugu) | Treat it as a prior; verify with output script share and reroute |
| Extra Tesseract pass doubles OCR time | Only ambiguous pages (wrong script/coverage); cache decision; measure s/page in the gate |
| Language edit endpoint races active jobs | Cancel/revoke first, then delete OCR/results and reset stages in one transaction; reuse the re-run OCR path |
| Wide-line split duplicates text at overlaps | 16 px overlap and join with a space; compare split vs unsplit on body pages (expected identical) |
| Routing hides a genuine recognition failure | Always record engine/route/coverage; show fallback on the page status |
| Changing `LANGUAGE_MAP` globally breaks bilingual decoding | Change the call site; keep `+eng` available per page |

## Success criteria

Every page has an explicit, recorded route; a wrong book language cannot silently produce Latin rubble; Telugu body accuracy is preserved at ≤0.16; Hindi stays ≤0.07; Latin front matter is read by Tesseract, not the Telugu line model; and no page completes with empty/short OCR without a visible fallback.

# 019 — OCR Accuracy Improvement Plan (Hindi + Telugu, CPU-only)

**Status:** proposed
**Review:** [learnings/026](../learnings/026-ocr-accuracy-strategy-review.md)
**Depends on:** [learnings/020](../learnings/020-ocr-engine-benchmark.md) (locked engine decision), [learnings/021](../learnings/021-ocr-engine-operational-requirements.md)
**Sequencing:** [plans/020](020-ocr-language-and-page-type-routing.md) (language/page-type routing) lands **before** Phase 2 here — [learnings/029](../learnings/029-ocr-language-routing-and-font-benchmarks.md) shows the dominant error source is the right engine reading the wrong language (`+eng` in the model, upload language, page type), so fine-tuning a model that is being fed the wrong language would be wasted.
**Supersedes:** the strategy document reviewed in 026 (no repo artifact of its own)

## Scope

Improve OCR fidelity for Hindi and Telugu inside the existing CPU-only, offline, single-worker envelope, **without** reopening the locked engine decision unless a measured PoC wins on accuracy *and* s/page *and* RAM.

Baseline to beat (page-level, NFC, whitespace-collapsed; frozen at `backend/scripts/ocr_bench/results.json`):

| Language | Engine | median CER | median WER | s/page | peak RAM |
|---|---|---|---|---|---|
| Telugu | `telugu-ocr-model` (CTC) | 0.163 | 0.600 | 3.8 | 779 MB |
| Hindi | Tesseract 5 `hin` | 0.072* | 0.250 | 2.3 | 44 MB |

\* measured on IndicVisionBench, **not** our books. Closing that gap is Phase 1's job, not an assumption.

## Guiding constraints

1. **No global preprocessing change.** Anything that binarizes, denoises or erodes strokes must be opt-in per page and must prove no mean-confidence regression on the frozen corpus.
2. **No substitution of text values.** Normalization may canonicalize Unicode and punctuation only; it may never rewrite numerals, dates or proper nouns.
3. **Offline.** All weights vendored into the image (`HF_HUB_OFFLINE=1`); no runtime downloads.
4. **One increment per commit**; `pytest` + bench before each gate.

## Phase 0 — Connect the path and measure (no model work)

The strategy's pillar 1 is unusable until this exists. Four defects found in 026 §B/C:

| # | Item | Files | Done when |
|---|---|---|---|
| 0.1 | Decide `OCR_CUSTOM_MODEL_DIR`: implement it or delete it | `app/core/config.py`, `app/services/ocr_service.py` (`_build_config`), docs | **Done (delete/replace)** — the dead setting is removed. Custom models now use `TESSERACT_TESSDATA_DIR`, passed through Tesseract's real `--tessdata-dir`; the directory must contain every language loaded (e.g. `hin` + `eng`). Covered by 2 unit tests |
| 0.2 | Fix `train_tesseract_lstm.sh` | `backend/scripts/train_tesseract_lstm.sh`, `docs/ocr-training.md`, `docs/ocr-postdeploy-runbook.md` | **Fixed (static)** — uses `--training_text`/`--start_model`, accepts comma-separated `--fonts` as repeated `--fontlist`, drops the no-op `--epochs`, and combines via `combine_tessdata -o` (two operands). `bash -n` passes; a live dry-run is blocked because `tesstrain.sh` is not installed in this environment |
| 0.3 | Corrections export | new `GET /api/admin/ocr-corrections`, `ocr_results`/page correction storage | Exports `(image_path, bbox, wrong, right)` for user edits; needs a table or JSON column that records the edit, since `corrections` today holds only rule firings |
| 0.4 | Resolve `auto_preprocess` inconsistency | `config.py`, `schemas/page.py`, `preprocessing.py`, `docs/ocr-setup.md`, `frontend/.../preprocessing/page.tsx`, `lib/api.ts`, `e2e_prod.py`, `build_corpus.py` | **Removed** — the flag was UI-only (stored, never read). Deleted from the schema, defaults, `Settings`, the frontend toggle and `api.ts`, plus the two script references. The per-page `preprocessing_config` is the only control |
| 0.5 | Language-gate the danda rule | `app/services/ocr_postprocess.py` (`_danda_cleanup`) | **Done** — skipped when `language == "eng"`; 2 regression tests added |
| 0.6 | Baseline harness for "our books" | `backend/scripts/eval_ocr.py`, `scripts/ocr_bench/` | **Done** — `bench_preprocess.py` reproduces the 020 baseline locally (`raw_300dpi` median CER 0.343 on 18 pages); result in [learnings/027](../learnings/027-default-preprocessing-upscale-benchmark.md) |

**Gate G0:** 0.1–0.6 merged, tests green, and the 020 numbers reproduce within noise. No accuracy claim yet.

## Results so far

| Date | Change | Evidence |
|---|---|---|
| 2026-11-16 | Default preprocessing was rescaling every 300-DPI page 1.5× to 450 DPI while telling Tesseract `--dpi 300` | [learnings/027](../learnings/027-default-preprocessing-upscale-benchmark.md): median CER 0.365 vs 0.285 with the upscale off, worse on 15/18 pages |
| 2026-11-16 | `run_pipeline` now takes `source_dpi` (default `OCR_RENDER_DPI`); a 300-DPI render is no longer rescaled | Re-run: `pipeline_default` median CER **0.285** (was 0.365), identical to `no_upscale` on all pages; 2 new tests |
| 2026-11-16 | Danda rule gated to non-`eng` | `test_ocr_postprocess.py` (14 passing) |
| 2026-11-16 | Removed `auto_preprocess` everywhere (0.4) | Flag was UI-only; schema, defaults, `Settings`, frontend toggle and scripts updated; 376 backend tests + `tsc --noEmit` clean |
| 2026-11-16 | Verified the 027 fix on the **line model** (production Telugu engine) | [learnings/028](../learnings/028-line-model-preprocessing-benchmark.md): median CER unchanged (0.174), legacy 450-DPI worse on 11/18 pages — global fix correct, no engine branch |

Also measured (and worth not re-litigating): `deskew`, `remove_borders` and `grayscale` are **inert** on 300-DPI library scans — the only active default was the upscale.

## Phase 1 — Hindi ground truth on our own scans

Needed because every Hindi statement in 020/026 rests on an external corpus.

- Pick ≥2 Hindi books with clean front matter and body pages; hand-transcribe 20–30 pages (or reuse an existing Wikisource-verified set if one is found — [learnings/002](../learnings/002-gt-enrichment-sources.md) says hi.wikisource is not proofread, so hand transcription is likely).
- Freeze page images at `OCR_RENDER_DPI` with the production `process_page_image` path so the score matches production.
- Store under `fixtures/` with a manifest and licence note (CC/PD only, per [learnings/001](../learnings/001-ground-truth-dataset-feasibility.md)).

**Gate G1:** our-books Hindi Tesseract CER and WER recorded. If our-books CER is materially worse than 0.072, the fine-tune case strengthens and Phase 2 becomes the priority; if it is comparable, Phase 2 drops in priority behind Phase 3.

## Phase 2 — Hindi Tesseract fine-tune (PoC first)

Blocked by [plans/020](020-ocr-language-and-page-type-routing.md): routing integrity comes first ([learnings/029](../learnings/029-ocr-language-routing-and-font-benchmarks.md)).

Per the AGENTS.md workflow this must be a PoC before implementation.

**PoC (poc/005) scope:**
- Corpus: hybrid — synthetic lines from 3–5 Devanagari fonts representative of the books (`scripts/generate_training_data.py`) **plus** real lines cropped from Phase 1 books, 90/10 train/held-out split by book (never by line).
- Train: `tesstrain.sh` with `--start_model` from `hin.traineddata`, `--linedata_only` where applicable; `--pass_through_recoder` evaluated as an A/B, not assumed.
- Evaluate: `lstmeval` on held-out **and** the Phase 1 page set through `process_page_image` with `TESSERACT_TESSDATA_DIR` pointing at the custom model directory (0.1).
- Report: CER/WER deltas, mean confidence delta, s/page delta, model size.

**Gate G2 (go/no-go):**
- ≥15 % relative median CER reduction on our-books Hindi **and**
- no >2-point absolute CER regression on any single book **and**
- s/page within +25 % **and**
- Telugu and English outputs byte-identical (the custom dir must never leak across languages).

Fail → document in `learnings/` and stop. Do not tune the test set.

## Phase 3 — Post-processing safety and signal

- Expand `normalize_text` with Unicode-level rules only: NFC, nukta/anusvara canonical forms per script, script-gated danda, ZWJ/ZWNJ rules gated to languages where they are spurious.
- **Explicitly excluded:** numeral→word conversion, date/currency rewriting, any LLM correction pass that can alter proper nouns.
- Use Phase 0.3's export to measure the **raw→corrected edit rate per engine per language**; this is the metric that makes future engine decisions cheap.

**Gate G3:** edit-rate dashboard exists; no regression in `cleaned_text` on the frozen corpus.

## Phase 4 — Conditional preprocessing experiments (per-page, opt-in)

Each idea is a separate, small experiment against the frozen corpus; none may become a default without a measured win **and** no mean-confidence regression.

1. **Adaptive compound binarization** (global Otsu seed + local window). Compare against `None`, `sauvola`, `otsu` on the same pages.
2. **Illumination normalization** (image ÷ blurred image) before grayscale — non-destructive, plausible.
3. **Dewarping** (`page-dewarp` or equivalent) on visibly curved pages only, gated by a cheap curvature score.

**No-go without new evidence:** shirorekha removal, global denoise, global binarization, `--psm 11`.

## Phase 5 — Deferred / not scheduled

- **Surya or other VLM OCR:** requires (a) a written licence decision (OpenRAIL-M, <$5 M revenue), (b) a measured CPU s/page on `test-node-3`, (c) a PoC that beats 0.163 Telugu / 0.072 Hindi. IndicOCR already failed this bar (>12 min/page). Revisit only on GPU availability.
- **Custom Hindi CRNN/CTC line model** (mirroring the Telugu model): architecturally the most promising long-term path, but needs a real line-image corpus (Mozhi-style) and a training budget; it is larger than the Tesseract fine-tune. Consider only after Phase 2 reports.
- **ONNX/quantization of the line model:** measure only; no memory pressure justifies it today.
- **PaddleOCR, EasyOCR, Chitrapathak-2:** closed. See 020/021.

## Risks

| Risk | Mitigation |
|---|---|
| Custom model dir leaks across languages and silently changes Telugu/English | Single resolver keyed by language; test asserts Telugu path unchanged |
| Synthetic-only training overfits fonts | Hold-out by book; real-line mix required |
| Fine-tune improves CER but hurts confidence calibration used by the review UI | Report mean confidence delta; reject on unexplained drops |
| Phase 0 expands into a refactor | Each item ≤1 commit, no adjacent cleanup |
| "Improving OCR" absorbed into the 81 % LLM bottleneck | Success measured per stage; do not re-optimize OCR speed |

## Success criteria for the plan as a whole

1. Every documented OCR configuration knob is either functional or deleted.
2. Hindi accuracy is measured on our own books, not borrowed from an external corpus.
3. Either a fine-tuned Hindi model ships with a measured, gated improvement, or the negative result is recorded with evidence.
4. No post-processing rule can alter a bibliographic value.

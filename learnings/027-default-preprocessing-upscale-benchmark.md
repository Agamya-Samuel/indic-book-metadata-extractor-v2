# 027 — Default Preprocessing Is a 1.5× Upscale, and It Costs Accuracy

- **Date:** 2026-11-16
- **Study context:** [learnings/026](026-ocr-accuracy-strategy-review.md) §C found that preprocessing is *not* off by default: `page_tasks._insert_page` attaches `DEFAULT_PREPROCESSING_CONFIG` to every rendered page. Reading `run_pipeline` showed a suspected double-scale — pages are rendered at `OCR_RENDER_DPI=300`, then `upscale_to_dpi(current_dpi=200, target_dpi=300)` scales them again to 450 DPI, while Tesseract is told `--dpi 300`. This measured whether that actually costs accuracy, using the harness already written at `backend/scripts/ocr_bench/bench_preprocess.py`.
- **Artifacts:** `backend/reports/ocr-preprocess-bench.json` (18 pages / 8 books, 6 variants each), harness [`bench_preprocess.py`](../backend/scripts/ocr_bench/bench_preprocess.py), `TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast`, run locally on a workstation (CPU).
- **Dataset:** the same Wikisource-verified Telugu body pages used by [learnings/020](020-ocr-engine-benchmark.md): GT entries with `telugu_share ≥ 0.55`, `len ≥ 60`, no markup residue; 300-DPI PyMuPDF renders. Scoring is page-level code-point CER/WER, NFC + whitespace-collapsed.

## Summary

The suspected defect is real and measurable: the default pipeline scales an already-300-DPI render to **450 DPI**, and that upscale **increases** median CER (0.365 vs 0.343 raw; 0.285 with the upscale disabled) while raising OCR time ~36 %. `deskew` and `remove_borders` changed **nothing** on all 18 pages, and `grayscale` changed almost nothing — so the entire default preprocessing path reduces to the harmful upscale. Removing it is a free accuracy and throughput win with no new dependency.

## Key findings

### 1. The double upscale is confirmed in code and in pixels

`pdf_service.render_full_page` renders at `settings.ocr_render_dpi` (300). `page_tasks._insert_page` then attaches `DEFAULT_PREPROCESSING_CONFIG`, whose `upscale_to_300dpi: True` calls `upscale_to_dpi(image, current_dpi=200, target_dpi=300)` — a fixed 1.5×. Measured mean image width confirms it: **1571 px raw → 2356 px through the pipeline** (1.50×), while every "no_upscale" variant stayed at 1571 px.

### 2. The upscale makes OCR worse (paired, same pages)

| Variant | median CER ↓ | mean CER ↓ | median WER ↓ | mean conf | mean width | s/page |
|---|---|---|---|---|---|---|
| `raw_300dpi` (no preprocessing) | 0.343 | 0.447 | 0.971 | 53.0 | 1571 | 2.86 |
| `grayscale_only` | 0.343 | 0.447 | 0.971 | 53.0 | 1571 | 2.33 |
| **`no_upscale`** | **0.285** | **0.433** | 0.971 | 51.7 | 1571 | **2.37** |
| `deskew_borders_no_upscale` | 0.285 | 0.433 | 0.971 | 51.7 | 1571 | 2.44 |
| `upscale_only` | 0.358 | 0.443 | 0.982 | 52.0 | 2356 | 2.94 |
| `pipeline_default` | 0.365 | 0.460 | 1.000 | 50.1 | 2356 | 3.22 |

Paired against `no_upscale` on the same 18 pages:

| Variant | mean ΔCER | median ΔCER | pages worse | pages better | identical |
|---|---|---|---|---|---|
| `pipeline_default` | **+0.0269** | +0.0126 | **15** | 2 | 1 |
| `upscale_only` | +0.0108 | +0.0047 | 13 | 5 | 0 |
| `raw_300dpi` | +0.0138 | 0.0000 | 3 | 3 | 12 |
| `grayscale_only` | +0.0139 | 0.0000 | 3 | 2 | 13 |
| `deskew_borders_no_upscale` | 0.0000 | 0.0000 | 0 | 0 | **18** |

The direction is consistent, not a single-page artefact: 15/18 pages are worse with the default pipeline, 2 better, 1 tied.

### 3. Only one operation in the default config does anything

`deskew_borders_no_upscale` produced **byte-identical CER on all 18 pages** to `no_upscale`, and `grayscale_only` matched `raw_300dpi` on 13/18 (differences on the rest are within rounding/noise). Conclusions:

- `deskew` is inert here: `deskew()` returns the image unchanged when `|angle| < 0.5°`, which is the case for these 300-DPI library scans.
- `remove_borders` is inert: `remove_borders()` bails when the detected border is < 30 % of a dimension.
- `grayscale` is a no-op for recognition — Tesseract thresholds internally anyway.
- Therefore the *entire* default preprocessing pass is equivalent to "upscale by 1.5×", which is the thing that hurts.

### 4. Cost is not just accuracy

The 450-DPI path is slower per page (3.22 s vs 2.37 s, +36 %) and carries 2.25× the pixels through OpenCV, on a worker that is already the memory-sensitive service.

### 5. Baseline cross-check

`raw_300dpi` median CER here is **0.343**, against 0.402 in [learnings/020](020-ocr-engine-benchmark.md). The samples differ (18 pages here after the `telugu_share ≥ 0.55` + duplicate filter, vs 21 there), so this is a consistency check, not a contradiction. Comparisons in this document are all **within-run and paired**.

## Recommendation

**Go:** make the upscale conditional on the true source DPI instead of assuming 200, and then stop advertising preprocessing as universally beneficial.

- `run_pipeline` should treat the source as whatever the renderer produced (`settings.ocr_render_dpi`), so a 300-DPI render is not rescaled. Upscaling should remain available for genuinely low-DPI sources.
- Keep `deskew`, `remove_borders`, `grayscale` in the config — they are harmless — but do not claim they improve accuracy on this corpus; they are inert.
- Do **not** promote any other preprocessing (Sauvola, denoise, dewarping) to default on this evidence.

This also resolves half of [learnings/026](026-ocr-accuracy-strategy-review.md) §C: the strategy's assumption that preprocessing is conservative-but-off is wrong in the opposite direction — the one active operation is the one that should be off.

## Verified after the fix

`run_pipeline` now takes `source_dpi` (defaulting to `settings.ocr_render_dpi`), so a 300-DPI render is not rescaled. Re-running the identical benchmark (`backend/reports/ocr-preprocess-bench-postfix.json`, same 18 pages):

| Variant | median CER before | median CER after | mean CER after | mean width after |
|---|---|---|---|---|
| `pipeline_default` | 0.365 | **0.285** | 0.433 | 1571 |
| `no_upscale` | 0.285 | 0.285 | 0.433 | 1571 |
| `upscale_only` | 0.358 | 0.343 | 0.447 | 1571 |

`pipeline_default` is now **identical to `no_upscale`** on every page, and mean width dropped from 2356 to 1571 px — i.e. the default path no longer runs the harmful 1.5× scale. The two new unit tests cover both directions (`source_dpi=300` unchanged, `source_dpi=200` still upscales by 1.5×).

## Next steps

1. ~~Implement the `source_dpi` fix and re-run the benchmark.~~ Done, see above.
2. Update `docs/ocr-setup.md` §5.1 (currently says preprocessing is off by default) and the `OCR_AUTO_PREPROCESS` dead-setting item from 026 §C.
3. ~~Re-measure the **line model** path with and without the upscale.~~ Done in [learnings/028](028-line-model-preprocessing-benchmark.md): the line model is insensitive to the rescale (median CER unchanged) and the legacy 450-DPI path is slightly worse — no engine-conditional branch needed.

## References

- Harness: [`bench_preprocess.py`](../backend/scripts/ocr_bench/bench_preprocess.py) · baseline: [learnings/020](020-ocr-engine-benchmark.md)
- Code: `backend/app/services/preprocessing.py` (`upscale_to_dpi`, `run_pipeline`), `backend/app/tasks/page_tasks.py:113,121`, `backend/app/tasks/ocr_tasks.py:79-85`, `backend/app/services/pdf_service.py:42`
- Plan: [plans/019](../plans/019-ocr-accuracy-improvement.md) Phase 0.6 / Phase 4

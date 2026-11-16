# 028 — The Telugu Line Model Does Not Want the 1.5× Upscale Either

- **Date:** 2026-11-16
- **Study context:** [learnings/027](027-default-preprocessing-upscale-benchmark.md) removed a 1.5× rescale from the default preprocessing pass and measured the gain on **Tesseract**. Production Telugu, however, runs `harsha-desaraju/telugu-ocr-model` with no declared DPI and line-level crops — so the extra pixels could plausibly have *helped*, making the 027 change a production regression. This measured the actual production engine before accepting the fix.
- **Artifacts:** [`bench_lines_preprocess.py`](../backend/scripts/ocr_bench/bench_lines_preprocess.py) (new), `backend/reports/ocr-lines-preprocess-bench.json`; run locally with `HF_HUB_OFFLINE=1`, `torch 2.15.0+cpu`, `transformers 4.46.3`, cached weights (311 MB), CTC decode.
- **Method:** the same 18 Wikisource-verified Telugu body pages as 027, rendered at 300 DPI, scored with the production code path (`ocr_line_model.run_line_ocr`, i.e. Tesseract line boxes at `--psm 6` + `model.transcribe`). Three variants per page:
  - `raw_300dpi` — untouched render
  - `pipeline_default` — the full default config with `source_dpi = OCR_RENDER_DPI` (current behaviour, no rescale)
  - `legacy_upscale_450` — the same config with `source_dpi = 200`, reproducing pre-027 behaviour (1.5× → 450 DPI)

## Summary

The line model is **insensitive** to the rescale: the new default leaves median CER unchanged (0.174 → 0.174) and the legacy 450-DPI path is slightly **worse** (median 0.184, mean +0.012, worse on 11/18 pages). The engine-conditional branch considered in 027 is unnecessary — the global fix is correct for both engines.

## Results

| Variant | median CER ↓ | mean CER ↓ | median WER ↓ | mean lines | mean widest crop | s/page |
|---|---|---|---|---|---|---|
| `raw_300dpi` | **0.174** | **0.226** | **0.620** | 18.9 | 1131 | 4.92 |
| `pipeline_default` (current) | **0.174** | 0.230 | **0.620** | 18.7 | 1130 | 4.33 |
| `legacy_upscale_450` | 0.184 | 0.238 | 0.644 | 19.0 | 1693 | 5.46 |

Paired against `raw_300dpi`, same pages:

| Variant | mean ΔCER | median ΔCER | worse | better | equal |
|---|---|---|---|---|---|
| `pipeline_default` | +0.0037 | 0.0000 | 4 | 2 | **12** |
| `legacy_upscale_450` | **+0.0122** | +0.0032 | **11** | 3 | 4 |

Interpretation: the current default is indistinguishable from raw (12/18 pages byte-equal in score, mean delta within noise), while the old 450-DPI path is a small but consistent regression.

## Notes

- **Preprocessing changes segmentation, not just recognition.** Line counts differ between variants on several pages (e.g. 6/4/5 lines on one page in the smoke run, 29/29/27 on another). The line model consumes whatever Tesseract's `--psm 6` boxes produce, so a preprocessing change can move line boundaries and merge or split crops. This is the mechanism behind the WER movement, and it is another reason not to add pixel-level preprocessing by default.
- **The width limit drops lines, but the rescale is not the cause.** The model scales a crop to `image_height` before recognition, so a crop is rejected once it exceeds `height * max_image_width / image_height` (64 px tall, 2048 limit ⇒ 32 px of width per px of height). **4 crops exceed that limit in every variant** — raw, current and legacy — because the limit scales with crop height too. Production does not split wide crops, so those 4 lines are silently dropped regardless of preprocessing; fixing that is a separate change (see [learnings/029](029-ocr-language-routing-and-font-benchmarks.md), which measures the `--split-wide` recovery).
  - Correction: the first run of this harness reported `0` over-limit crops because `_max_crop_width` had the ratio inverted (`height * image_height / max_image_width`), which made the check a no-op. The CER numbers below were unaffected and reproduced exactly; only the over-limit counts were wrong.
- Throughput is unchanged within noise (4.3–5.5 s/page); the 450-DPI variant is worst because it processes 2.25× the pixels.
- Page-level CER here (median 0.174) is consistent with [learnings/020](020-ocr-engine-benchmark.md) (0.163) on a slightly different 18-page sample. Within-run comparisons only.

## Recommendation

**Keep the global `source_dpi` fix** from 027; do not add an engine-conditional upscale. The default preprocessing path can stay attached to every page: at a 300-DPI render it is a no-op for Tesseract (deskew/borders/grayscale inert) and neutral for the line model.

Revisit only if a genuinely low-DPI source appears — `upscale_to_300dpi` still works when `source_dpi < 300`.

## Next steps

1. No action on the fix. Phase 0.5/0.6 and 027/028 are closed.
2. Routing work ([plans/020](../plans/020-ocr-language-and-page-type-routing.md)) precedes Phase 2: wide-crop splitting and language integrity affect accuracy more than any preprocessing choice measured here.
3. Phase 0.1 (`OCR_CUSTOM_MODEL_DIR` wiring) when Phase 2 (Hindi fine-tune) starts.
4. Phase 1 (Hindi page-level ground truth) remains the gate for any Hindi accuracy claim.

## References

- Predecessor: [learnings/027](027-default-preprocessing-upscale-benchmark.md) · engine baseline: [learnings/020](020-ocr-engine-benchmark.md)
- Code exercised: `app/services/ocr_line_model.py` (`run_line_ocr`, `_line_boxes`), `app/services/preprocessing.py` (`run_pipeline`)
- Plan: [plans/019](../plans/019-ocr-accuracy-improvement.md)

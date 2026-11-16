# 026 — Review of the Hindi/Telugu OCR Improvement Strategy: What the Evidence Supports

- **Date:** 2026-11-16
- **Study context:** An external strategy document proposed four pillars for improving Hindi and Telugu OCR on CPU-only infrastructure: (1) fine-tune Tesseract for Hindi, (2) adopt transformer/VLM OCR (Surya, Chitrapathak-2, EasyOCR, PaddleOCR, a custom Hindi CRNN), (3) add shirorekha-aware and adaptive preprocessing plus CPU parallelization, (4) add WFST/LLM post-processing and language detection. Before spending effort, each claim was checked against the code, the benchmark artifacts, and prior learnings. This is a desk review, not a measurement study.
- **Artifacts:** [backend/scripts/ocr_bench/results.json](../backend/scripts/ocr_bench/results.json), [learnings/020](020-ocr-engine-benchmark.md), [learnings/021](021-ocr-engine-operational-requirements.md), [learnings/015](015-service-inventory-and-gating.md), [docs/ocr-training.md](../docs/processing/ocr-training.md), [backend/scripts/train_tesseract_lstm.sh](../backend/scripts/train_tesseract_lstm.sh).

## Summary

The strategy's **premises are mostly correct, but its priorities are wrong for this repo**. Hindi is already the strong language (median CER 0.072 on external real-print GT), Telugu is already served by an Indic-specific model, and OCR is only **19 % of per-book wall-clock** — so a Hindi fine-tune is not the highest-ROI first move. The genuinely actionable findings are that the **Tier 3 path the strategy relies on is not wired**, its **training script cannot run as written**, and the **documented corrections export does not exist**. Two of the proposed post-processing/preprocessing ideas (spoken-form number normalization, shirorekha removal) would actively damage this project's output. Recommendation: fix and measure first; fine-tune second; defer VLM adoption.

## Key findings

### A. The numbers the strategy cites are correct, but one is stripped of a decisive caveat

| Claim in strategy | Status | Evidence |
|---|---|---|
| Tesseract 5 `tel` median CER 0.402 / WER 0.989 | correct | `learnings/020`, `results.json` (21 pages / 8 Telugu books) |
| PaddleOCR PP-OCRv4 `te` median CER 0.511 / WER 0.974 | correct | same |
| `harsha-desaraju/telugu-ocr-model` median CER 0.163 / WER 0.600 | correct **for CTC fast decode**; joint decode is ~9× slower for ~11 % lower AER | `learnings/020` |
| Tesseract 5 `hin` median CER 0.072 / WER 0.250 | correct **but measured on IndicVisionBench, not our books** | `learnings/020` caveats; `results.json.environment` |
| Hindi → Tesseract, Telugu → line model, Paddle rejected | correct, and already in production | `ocr_service._use_line_model`, `learnings/020/021` |
| "both languages suffering from reported poor accuracy" | **contradicted by the cited table itself** | CER 0.072 is good; Telugu is the problem |

The Hindi number is the only one measured outside our corpus, because our Hindi books have no page-level ground truth ([learnings/001](001-ground-truth-dataset-feasibility.md), [002](002-gt-enrichment-sources.md)). The strategy builds its first pillar on that number without carrying the caveat.

### B. Tier 3 (Hindi fine-tuning) is documented but **not connected**

This is the most important finding, because pillar 1 assumes the path works:

1. **`OCR_CUSTOM_MODEL_DIR` is dead.** It is declared in `app/core/config.py:87` and documented in `docs/ocr-setup.md` / `docs/ocr-training.md` §6, but **no code reads it** (`grep -rn ocr_custom_model_dir app/` returns only the declaration). Deploying a fine-tuned `hin.traineddata` has no route into the worker: `LANGUAGE_MAP` hardcodes `hin+eng` and `_get_tesseract_lang` ignores custom directories entirely.
2. **`scripts/train_tesseract_lstm.sh` cannot run as documented.** Its `tesstrain.sh` invocation passes `--trainlistfile`, `--continue_from` and `--output_dir`, which are not `tesstrain.sh` arguments (the flags are `--training_text`, `--start_model`, `--output_dir`), so `tesstrain.sh` will reject or ignore them. `--epochs` is parsed and echoed but **never passed to anything**. The final `combine_tessdata -e "$BASE_MODEL" a.lstm b.traineddata` uses three operands; `-e` takes two. And the documented usage `--fonts "Noto Sans Devanagari" "Mangal"` passes two words to a `--fonts` handler that consumes exactly one, so the second is rejected as `Unknown flag`.
3. **The corrections corpus does not exist.** `docs/ocr-training.md` §1 documents `GET /api/admin/ocr-corrections?language=hin`; that route is **not implemented** (no match in `app/`). `ocr_results.corrections` only ever holds post-processing rule firings (`ocr_tasks.py:116` writes `{"rules": [...]}`), never user edits. So the "500+ user-corrected lines" precondition has no collection mechanism.
4. **`--pass_through_recoder` (recommended in pillar 1) appears nowhere** in the training tooling.

### C. Preprocessing is **not** "off by default" the way the strategy assumes

The strategy says Advanced preprocessing is "disabled by default because it can erode the shirorekha". Only *part* of that is true, and the code disagrees with the docs:

- `DEFAULT_PREPROCESSING_CONFIG` (`preprocessing.py`) enables `grayscale`, `deskew`, `upscale_to_300dpi`, `remove_borders` and sets `auto_preprocess: True`; only `binarization: None` and `denoise: False` are off.
- `run_pipeline` is invoked whenever `page.preprocessing_config` is truthy and the page has no `processed_image_path` (`ocr_tasks.py:79-85`, `:304-315`), so deskew/upscale/border-removal **do** run in production.
- `OCR_AUTO_PREPROCESS` (`config.py:81`, default `False`) is **never read** — a second dead setting, and `docs/ocr-setup.md` presents it as the global toggle.
- The page schema defaults `auto_preprocess: True` (`schemas/page.py:25`), contradicting the config default.

### D. Claims that are unverified (external literature, no local evidence)

- Surya "supports CPU inference through the `llama.cpp` backend". Surya is a PyTorch document model; no `llama.cpp` path is known to exist. **Treat as unsupported** until measured. Its licence (OpenRAIL-M, <$5 M revenue, per [learnings/021](021-ocr-engine-operational-requirements.md) deferred item 4) is a separate adoption blocker the strategy omits.
- Surya/Citrapathak ANLS scores (16.85 / 12.61 / 6.69), the MBART-50 34 %/49 % relative gains, the "7.37× multiprocessing speedup", adaptive compound thresholding, `page-dewarp` CPU performance, `--pass_through_recoder` gains, and the Mozhi CRNN result. None are measured here.
- **EasyOCR was already considered and rejected** on Indic accuracy (with Surya) in `learnings/021`; the strategy re-proposes it without acknowledging that.
- Chitrapathak-2 is explicitly GPU-only in the strategy's own table, which excludes it by the CPU constraint — it should not be in a shortlist.

### E. Conflicts with repo evidence

1. **Shirorekha removal.** The strategy proposes deleting the horizontal top bar before OCR. That bar is part of the glyph identity for Devanagari; `preprocessing.denoise` already carries a comment that erosion of the shirorekha *hurts* Tesseract, and `docs/ocr-setup.md` records that Sauvola + denoise measurably hurt Indic scripts. Removal would need re-insertion logic (the cited patent is online handwriting recognition). **High risk, no local evidence, do not implement as a preprocessing filter.**
2. **"Normalize" numbers/dates/currency into spoken form** (`indic-text-normalization`, e.g. `२५ → पच्चीस`). This project extracts **bibliographic metadata**: years, page counts, catalogue numbers, titles. Converting numerals to words would destroy the fields the pipeline is scored on. The same applies to a fine-tuned MBART-50/ByT5 correction pass: it rewrites proper nouns and titles, exactly the high-precision fields where [learnings/013](013-verified-shortlist-and-ocr.md) already shows recall/format sensitivity.
3. **Model/memory optimization is solving a problem OCR does not have.** Peak OCR RAM measured at 44–779 MB; the memory pressure comes from the LLM (~7.9 GiB, [learnings/024](024-host-network-and-gemma-resource-reality.md)). Quantization/ONNX/`accelerate` offload for OCR is premature; ONNX export of the 81 M line model is the only defensible sliver (already a deferred item in 021).
4. **`tessedit_char_whitelist` is a poor fit for Indic.** The whitelist must enumerate every combining mark and ligature form; a partial list silently drops matras. Not recommended.
5. **OCR is not the pipeline bottleneck.** Per [learnings/015](015-service-inventory-and-gating.md), extraction is **81 %** of per-book wall-clock and OCR **19 %**. Halving OCR time saves ~10 % of book time; doubling OCR accuracy raises the quality of the LLM's input, which matters more than its speed.

### F. What the strategy gets right

- Per-language engines beat one global engine — already the production design.
- Line-level recognition is the right abstraction for Indic scripts.
- Tesseract LSTM training is CPU-feasible; the constraint is data, not hardware.
- Post-processing is underdeveloped (no corrections export, danda rule ungated by language — `ocr_postprocess._danda_cleanup` runs for `eng` too, logged in `docs/ocr-setup.md` §8).

## Recommendation

**Go, but resequenced.** Do not start with a Hindi fine-tune; start by connecting the path and measuring on our own books.

| Pillar | Verdict |
|---|---|
| Hindi Tesseract fine-tune | **Conditional go, Phase 2.** Requires Phase 0 wiring + a Hindi page-level GT set first. |
| Surya / VLM adoption | **Defer.** No local CPU evidence, licence unresolved, ~0.8 B-class CPU throughput already failed for IndicOCR (>12 min/page). |
| PaddleOCR / EasyOCR / Chitrapathak-2 | **No-go.** Already rejected (accuracy, speed, segfault) or GPU-only. |
| Shirorekha removal | **No-go as preprocessing.** Only revisit as detect-and-restore, and only with a PoC. |
| Adaptive thresholding / intensity normalization / dewarping | **Conditional, low priority.** Must beat the current defaults on the frozen corpus *without* lowering mean confidence; gate behind per-page config, never global. |
| Spoken-form normalization | **No-go.** Destroys metadata values. |
| MBART/ByT5 post-correction | **No-go for now.** High risk to proper nouns, adds a CPU model stage. |
| ONNX/quantization of the line model | **Low priority.** No memory pressure; possible throughput gain only. |
| Multiprocessing the OCR batch | **Already present** via `OCR_THREAD_WORKERS`; the open question is GIL-bound torch, not preprocessing. |

## Next steps

1. Execute [plans/019](../plans/019-ocr-accuracy-improvement.md) Phase 0 (wiring + measurement).
2. Build Hindi page-level GT for ≥2 books before any Hindi training claim ([learnings/020](020-ocr-engine-benchmark.md) next step 2, still open).
3. Correct `docs/ocr-training.md` and `docs/ocr-setup.md` to match the code, or implement what they promise.
4. Re-visit Surya only with a licence decision and a measured CPU s/page number on `test-node-3`.

## References

- Benchmarks: [learnings/020](020-ocr-engine-benchmark.md) · Runtime requirements: [learnings/021](021-ocr-engine-operational-requirements.md)
- Pipeline cost split: [learnings/015](015-service-inventory-and-gating.md) · LLM memory: [learnings/024](024-host-network-and-gemma-resource-reality.md)
- Code checked: `backend/app/services/{ocr_service,preprocessing,ocr_line_model,ocr_postprocess,page_classifier}.py`, `backend/app/tasks/ocr_tasks.py`, `backend/app/core/config.py`, `backend/scripts/train_tesseract_lstm.sh`
- Plan: [plans/019](../plans/019-ocr-accuracy-improvement.md)

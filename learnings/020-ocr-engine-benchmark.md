# 020 — OCR Engine Benchmark on Real Indic Scans: General vs Indic-Specific

- **Date:** 2026-11-13
- **Study context:** Answer [plans/003](../plans/003-ocr-engine-evaluation.md) with measurement, not published benchmarks: which OCR engine gives high accuracy **and** fits the CPU-only / 16 GB envelope? Telugu is scored on our own Wikisource-verified scans; Hindi is scored on the IndicVisionBench verified-scan set because our Hindi books lack page text.
- **Artifacts:** harness saved under [backend/scripts/ocr_bench/](../backend/scripts/ocr_bench/) (`build_bundle.py`, `bench.py`, `bench_lines.py`, `fetch_indicvision_hindi.py`, setup scripts) + [results.json](../backend/scripts/ocr_bench/results.json) + a reproduction [README](../backend/scripts/ocr_bench/README.md); run on GCP `test-node-3` (e2-standard-4, 4 vCPU / 16 GB, CPU only).

## Method

- **Test set:** 21 pages from **8 Telugu books** with `wikisource_gt.json` (level 3–4 human-verified text), evenly sampled per book, rendered at 300 DPI. Identical PNGs scored against identical references for every engine (page-level, Unicode NFC, whitespace-collapsed).
- **Metrics:** code-point CER (Levenshtein) and WER; median is reported because a few title/cover pages blow up the mean (stamps, near-empty refs).
- **Engines:** Tesseract 5 (`tel`); PaddleOCR PP-OCRv4 (`te`); `harsha-desaraju/telugu-ocr-model` (81 M-param CTC line model, MIT, `transformers`), with page→line segmentation via Tesseract's line boxes.

## Results (same 21 pages, CPU only)

| Engine | median CER ↓ | mean CER ↓ | median WER ↓ | s/page | peak RAM |
|---|---|---|---|---|---|
| Tesseract 5 (`tel`) | 0.402 | 0.578 | 0.989 | **2.0** | **167 MB** |
| PaddleOCR PP-OCRv4 (`te`) | 0.511 | 0.508 | 0.974 | 13.0 | 1278 MB |
| **telugu-ocr-model (CTC decode)** | **0.163** | **0.227** | **0.600** | 3.8 | 779 MB |

### Hindi result (real printed Hindi pages, IndicVisionBench OCR set)

Same method (page-level CER/WER) on **24 Hindi pages** from the IndicVisionBench `ocr` config (real printed book scans with verified transcription). Our own Hindi corpus has no verified page text, so this external real-scan GT is the closest available; it is not our exact books.

| Engine | median CER ↓ | mean CER ↓ | median WER ↓ | s/page | peak RAM |
|---|---|---|---|---|---|
| Tesseract 5 (`hin`) | **0.072** | 0.085 | 0.250 | 2.3 | **44 MB** |

Tesseract is **strong on Hindi (~7 % CER)** — the opposite of its Telugu behaviour, and consistent with published real-print Hindi results (CER ~9 %, WER ~29 %). The language, not a blanket "general engines fail", drives the decision.

## Key findings

1. **General-purpose engines are not usable on real Telugu scans.** Tesseract and PaddleOCR both leave roughly **40–50 % of characters wrong** (median CER 0.40 / 0.51) and ~**99 % of words wrong** (WER ~0.97–0.99). This matches [learning 004](004-ocr-stage-cer.md) and confirms OCR is the pipeline ceiling.
2. **An Indic-specific model is a step change.** The Telugu-specific line model is **2.5× lower median CER** (0.163 vs 0.402) and **1.6× lower WER** (0.60 vs 0.99) than Tesseract — and it still **fits the envelope** (3.8 s/page, 0.78 GB peak; CTC fast decode). Joint/beam decode is ~9× slower for ~11 % lower AER (published), i.e. best-accuracy mode is still CPU-feasible.
3. **PaddleOCR is the wrong trade.** Same-or-worse accuracy than Tesseract at ~6.5× the time and ~7.6× the RAM. PaddlePaddle 3.x **segfaults** on this CPU (PIR/oneDNN `ConvertPirAttribute2RuntimeAttribute`); 2.x works but is slow and memory-heavy.
4. **Per-language beats one global engine** — the direct answer to plans/003's single-vs-per-language question. A Telugu-specific model dominates generic engines on Telugu by a wide margin.
5. **Line segmentation is required** for the winning model (it is a line recogniser, not a page parser). Tesseract's layout boxes are an adequate, cheap segmenter; a purpose-built line detector would be the production choice.

### Resource fit at book scale (projected from measured s/page)

| Engine | ~250-page book (OCR only) | peak RAM |
|---|---|---|
| Tesseract 5 | ~8–10 min | 44–167 MB |
| PaddleOCR | ~54 min | 1.28 GB |
| telugu-ocr-model | ~16 min | 0.78 GB |

Every viable option fits the 4 vCPU / 16 GB box; Paddle's penalty is time, not memory. A Telugu book OCRs in ~16 min at <1 GB — comparable to the existing ~10–20 min LLM stage and well inside the RAM budget.

## Recommendation — per-language, evidence-based

The answer is **not one engine for all languages**:

- **Hindi → keep Tesseract 5 (`hin`).** Already high-accuracy on real printed Hindi (median CER 0.072, WER 0.25) and the lightest option (44 MB, 2.3 s/page). An Indic-specific Hindi model would have to beat ~7 % CER to justify added complexity; IndicOCR (published ~96 % word-acc) is the only candidate for a step change, but it is gated and 0.8 B.
- **Telugu → switch to `harsha-desaraju/telugu-ocr-model`.** Tesseract is unusable on Telugu (median CER 0.402); the Indic-specific line model more than halves error (median 0.163) and still fits CPU/RAM (3.8 s/page, 0.78 GB). Pipeline: page render → line detection (Tesseract boxes work) → per-line transcribe → concatenate.
- **Do not adopt PaddleOCR** for either language: no accuracy gain over Tesseract, 6–13× slower, ~1.3 GB RAM, and PaddlePaddle 3.x segfaults on this CPU.

So: **Tesseract for Hindi, an Indic-specific CRNN/transformer for Telugu** — a per-language OCR stack chosen by measured accuracy under the same CPU/RAM budget.

## Caveats

- **Source asymmetry:** Hindi figures use the **IndicVisionBench** real-scan OCR set (24 pages) because our Hindi books lack verified text; Telugu figures use our own Wikisource-verified scans (21 pages / 8 books).
- n = 21 pages / 8 books; page-level includes title/cover pages with stamps absent from GT, which penalise every engine equally (ranking survives, absolutes are pessimistic).
- Telugu numbers use CTC fast decode; joint decode trades ~9× time for ~11 % lower error.
- Downloaded model weights persist in `/home` on `test-node-3`; the `/tmp` venvs and test bundles are cleared on stop/start and recreated per run. Node stopped after the runs (spend guardrail).

## Next steps

1. Wire the Telugu line pipeline into `ocr_service.py` behind a language switch (Telugu → model; keep Tesseract as fallback).
2. Establish Hindi GT (hand-transcribed front matter ≥ 2 books) or use IndicVisionBench, then benchmark an Indic-specific Hindi model the same way.
3. Optional: re-run Telugu with joint decode and a dedicated line detector to quantify the accuracy/time ceiling.

## References

- Plan: [plans/003](../plans/003-ocr-engine-evaluation.md) · Prior OCR: [learnings/004](004-ocr-stage-cer.md), [013](013-verified-shortlist-and-ocr.md) · GT: [poc/004](../poc/004-poc-telugu-wikisource-gt.md)
- Telugu model: https://huggingface.co/harsha-desaraju/telugu-ocr-model · PaddleOCR: https://www.paddleocr.ai · IndicOCR: https://huggingface.co/bodhan-ai/indic-ocr
- Node tracker: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
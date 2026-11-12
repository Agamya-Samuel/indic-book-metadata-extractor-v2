# 012 — Verified-GT Shortlist, OCR Model Variant, and Recall Diagnosis

- **Date:** 2026-11-12
- **Context:** Execution of the prioritized next steps (A/B/C/D) following [010](010-llm-shortlist-benchmark.md). Heavy runs on GCP `test-node-3` (reset once after a wedged run); prod (`oki`) touched only for a reversible memory cap.
- **Artifacts:** `backend/reports/gt-verified-*.json`, `backend/reports/ocr-tessdata-best.json`; scripts [verify_ground_truth.py](../backend/scripts/verify_ground_truth.py), [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py).

## A1 — Ground truth verified

`verify_ground_truth.py` marks every book `verification_status=verified` when each prefilled value traces to an authoritative source (Commons / Wikisource index / Internet Archive) and records per-field evidence (`scan_confirmed` where the value appears in the fetched Wikisource page text, else `not_in_scan`). **35/35 books verified.** Note this is *source*-verification; a human spot-check is still advisable (13 Telugu books had `not_in_scan` values — mostly Roman-vs-Telugu transliteration).

## A2 — Shortlist re-run on verified books (resolves 010 vs 005)

2 verified books, `--pages 6`:

| Model | P | R | F1 |
|---|---|---|---|
| **phi4-mini (3.8B)** | 0.667 | 0.222 | **0.333** |
| qwen3-4b-instruct-2507 | 1.000 | 0.056 | 0.106 |

**phi4-mini wins** (author/title/pages/publication_date each F1 0.667; qwen3-4b only publication_date). This **confirms [010](010-llm-shortlist-benchmark.md) and contradicts [005](005-llm-model-evaluation.md)** — on this task phi4-mini (3.8B, ~2.5 GB, MIT) beats the recommended `qwen3-4b-instruct-2507`.

## B3 — OCR model variant (`tessdata_best` vs `fast`)

| Telugu tessdata | median CER |
|---|---|
| `fast` (baseline, learnings/004) | 0.453 |
| **`best`** | **0.419** |

A **marginal** improvement (~0.034 / ~7.5% relative) — Telugu OCR stays ~0.42 CER. Not enough on its own.

## B4 — Recall diagnosis (why name fields fail)

Inspecting predicted-vs-expected values:
- **Most fields return `None`** — the small models simply do not fill author/publisher/language from the (poor) OCR text.
- **`title="CoreIdentityBatch"`** from phi4-mini — the model **echoed the Pydantic schema class name**; an extraction/parse bug worth fixing.
- `publication_date=2005` (wrong; GT 1913) — a stray/again wrong value, likely from OCR noise.

## C6 / C5

- **C6:** corpus grew to **35 books** (from 27); 17 have page-level OCR text. New books are mostly un-proofread (metadata only).
- **C5:** the oki Ollama container was unbounded on a **16 GB no-swap** host; capped at **6 GiB** live (`docker update`) and in `docker-compose.production.yml`, with `OLLAMA_NUM_THREADS=3`, `MAX_LOADED_MODELS=1`, `NUM_PARALLEL=1`, ctx 4096.

## Recommendation

1. **Pick `phi4-mini`** as the production extractor (best measured, smallest, MIT) — pending the schema-echo fix and a larger verified sample.
2. **Fix the schema-echo bug** (`title="CoreIdentityBatch"`) and the null-recall — likely prompt/parse, on top of OCR.
3. **OCR remains the ceiling** (~0.42 CER even with `tessdata_best`); a different engine (not just traineddata) is needed for a real step change.
4. Keep the 6 GiB cap; a 4B/3.8B fits with headroom.

## Next steps

- Fix the schema-echo + investigate null-returns (batch prompt / JSON parsing) before the next model sweep.
- Scale the verified set (currently 2 books used) and re-run phi4-mini vs 2–3 alternatives.
- Trial a non-Tesseract OCR engine (Indic-tuned / VLM) on the same Wikisource GT.

## References

- Reports: `backend/reports/{gt-verified-phi4-mini,gt-verified-qwen3-4b-instruct-2507,ocr-tessdata-best}.json`
- Prior: [010](010-llm-shortlist-benchmark.md) · [005](005-llm-model-evaluation.md) · [004](004-ocr-stage-cer.md) · [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
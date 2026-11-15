# 012 — Handoff: OCR engine decision locked → implement the Telugu line OCR

- **Status:** Decision complete; **implemented and packaged 2026-11-15** — production defaults to `OCR_TEL_ENGINE=line_model`, the worker image bakes CPU torch/transformers + the 310 MB weights, and a per-page Tesseract fallback covers load failures. Deploy + CER verification pending.
- **Decision & evidence:** [plans/003](../plans/003-ocr-engine-evaluation.md) · [learnings/020](../learnings/020-ocr-engine-benchmark.md) · [learnings/021](../learnings/021-ocr-engine-operational-requirements.md) · harness [backend/scripts/ocr_bench/](../backend/scripts/ocr_bench/).

## Locked decision (do not re-litigate without new measurements)

| Language | Engine | Measured |
|---|---|---|
| Hindi | **Tesseract 5 (`hin`)** — keep as-is | median CER 0.072, 2.3 s/page, 44 MB |
| Telugu | **`harsha-desaraju/telugu-ocr-model`** (line OCR + Tesseract line boxes) | median CER 0.163 vs Tesseract 0.402, 3.8 s/page, 0.78 GB |

Rejected: PaddleOCR (no gain, slower, heavier, Paddle 3.x CPU segfault); IndicOCR (gated + not CPU-viable, >12 min/page); Surya/EasyOCR (licence / poor Indic).

## What still needs to be built (ordered)

1. [x] **Config** (`config.py`): `ocr_tel_engine` (default `tesseract`), `ocr_line_model_name`, `ocr_line_model_decode`, `ocr_line_model_confidence` (conservative 50).
2. [x] **New service** `backend/app/services/ocr_line_model.py`: lazy `AutoModel`/`AutoTokenizer` (`trust_remote_code=True`, process-wide lock), Tesseract `--psm 6` line boxes grouped by `(block_num, par_num, line_num)` and ordered top→bottom, batched `model.transcribe`, same contract as `run_ocr` plus `"engine": "line_model"`.
3. [x] **Dispatch** in `ocr_service.run_ocr`: Telugu + `ocr_tel_engine=="line_model"` → line pipeline; otherwise Tesseract. `"engine"` added to the Tesseract return too; any model error falls back to Tesseract with `engine_fallback_reason`.
4. [x] **Guard Tesseract-only steps** in `ocr_tasks.py`: `retry_low_confidence_words` is skipped when `engine != "tesseract"`; a fallback is recorded in `pages.ocr_error`.
5. [x] **Dependencies**: `ocr-line` extra (`torch` from the PyTorch CPU index → 2.15.0+cpu, `transformers==4.46.3`) in `pyproject.toml`/`uv.lock`; the worker image builds with `OCR_LINE=true` and bakes the **310 MB** weights into `/app/ocr_models/telugu-ocr-model`. Backend/flower skip both. Egress measured at PyPI ~32 MB/s / HF ~1.1 MB/s ([learnings/024](../learnings/024-host-network-and-gemma-resource-reality.md)).
6. [x] **Tests**: adapter tested with a fake model; dispatch/fallback tested without torch. The golden-page CER check still needs the artifact.

## Open design decisions the next agent must settle

- **Word-level confidence — settled:** the line model emits no confidence, so each line is stored as one `word` entry with the line bbox and a conservative `ocr_line_model_confidence` (default 50). Do **not** fake green; a future "unscored" UI can replace this.
- **Line segmentation source:** Tesseract boxes are adequate and cheap; a dedicated line detector may improve the ceiling (optional).
- **Offline weights path:** where to vendor `weights/ocr` (1.7 GB) — image layer vs mounted volume — per the offline constraint.

## Acceptance criteria

- With `ocr_tel_engine=line_model`, a Telugu page through the real Celery path (no DB-less shortcut) produces `raw_text` whose CER against the GT is **no worse than 0.163** and strictly better than the Tesseract path on the same page; Hindi paths unchanged.
- Book-scale timing within a 4 vCPU / 16 GB worker (~16 min / 250 pp) with peak RSS < 1.5 GB.
- `pytest` + `ruff` clean; default config reproduces today's behaviour exactly.

## Blockers / assets needed from a human

- **Hindi on our own books (optional):** the locked Hindi engine is measured on IndicVisionBench, not our corpus. To validate on our scans, hand-transcribe 4–8 front-matter pages × ≥2 Hindi books, then run `ocr_bench/bench.py --engine tesseract --lang hin --bundle <bundled>`.
- **Secrets:** an HF token was used only to test gated IndicOCR; it was removed from the node and is not in the repo. Rotate it.

## Deferred research (not blockers)

- IndicOCR on a GPU (or with `flash-linear-attention`/`causal_conv1d`) — only Hindi step-change candidate.
- Telugu `decode="joint"` (~9× slower, ~11% lower AER) and a dedicated line detector.
- Reviewer-effort metric: write `ocr_results.corrections` and implement `GET /api/admin/ocr-corrections`.
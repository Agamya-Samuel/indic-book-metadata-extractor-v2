# 012 — Handoff: OCR engine decision locked → implement the Telugu line OCR

- **Status:** Decision complete; implementation pending (for the next agent).
- **Decision & evidence:** [plans/003](../plans/003-ocr-engine-evaluation.md) · [learnings/020](../learnings/020-ocr-engine-benchmark.md) · [learnings/021](../learnings/021-ocr-engine-operational-requirements.md) · harness [backend/scripts/ocr_bench/](../backend/scripts/ocr_bench/).

## Locked decision (do not re-litigate without new measurements)

| Language | Engine | Measured |
|---|---|---|
| Hindi | **Tesseract 5 (`hin`)** — keep as-is | median CER 0.072, 2.3 s/page, 44 MB |
| Telugu | **`harsha-desaraju/telugu-ocr-model`** (line OCR + Tesseract line boxes) | median CER 0.163 vs Tesseract 0.402, 3.8 s/page, 0.78 GB |

Rejected: PaddleOCR (no gain, slower, heavier, Paddle 3.x CPU segfault); IndicOCR (gated + not CPU-viable, >12 min/page); Surya/EasyOCR (licence / poor Indic).

## What still needs to be built (ordered)

1. **Config** ([backend/app/core/config.py](../backend/app/core/config.py)): add `ocr_tel_engine: str = "tesseract"` (values `tesseract|line_model`), `ocr_line_model_name = "harsha-desaraju/telugu-ocr-model"`, `ocr_line_model_decode = "ctc"`, and a word-confidence policy setting. Default stays `tesseract` so behaviour is unchanged until flipped.
2. **New service** `backend/app/services/ocr_line_model.py`:
   - Lazy-load `AutoModel`/`AutoTokenizer` with `trust_remote_code=True` (cache + process-safe lock; Celery may run books concurrently).
   - Segment a page into lines with `pytesseract.image_to_data(..., lang=..., config="--psm 6")`, group by `(block_num, par_num, line_num)`, order top→bottom.
   - `model.transcribe(crops, tokenizer, decode=...)` (batch per page).
   - Return the **same contract as `run_ocr`**: `{words, full_text, avg_confidence, word_count, psm, psm_label}` + a new `"engine": "line_model"`.
3. **Dispatch** in `ocr_service.run_ocr`: Telugu + `ocr_tel_engine=="line_model"` → line pipeline; otherwise Tesseract. Add `"engine"` to the Tesseract return too.
4. **Guard Tesseract-only steps** in [backend/app/tasks/ocr_tasks.py](../backend/app/tasks/ocr_tasks.py): skip `retry_low_confidence_words` when `engine != "tesseract"` (it would re-OCR words with Tesseract and undo the model output).
5. **Dependencies**: `torch` (CPU wheel) + `transformers==4.46.x` + the 81 M model weights vendored into the image/mount (offline). Backend already `requires-python >=3.11`. `pytesseract` + `tesseract` already present.
6. **Tests**: unit test the adapter with a fake model (no torch in CI); a golden-page check that page CER on a known Telugu page beats the Tesseract path.

## Open design decisions the next agent must settle

- **Word-level confidence:** the line model emits no per-word confidence. `run_ocr`'s `words[].confidence` / `avg_confidence` feed the review-UI confidence dot and metrics. Decide: map line→words with line bbox and a *conservative* confidence (do **not** fake green), or extend the schema/UI to handle "unscored". This is the main reason integration was not rushed.
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
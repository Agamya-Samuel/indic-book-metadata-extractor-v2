# 030 — Telugu Line-Model Fine-Tune on Real Book Lines (and Hindi Negative Results)

- **Date:** 2026-11-16
- **Context:** Follow-up to [029](029-ocr-language-routing-and-font-benchmarks.md). Routing fixed front matter and wrong-language pages, but Telugu body recognition stayed at ~0.16 CER. This tests whether the 81M line model can be adapted to the actual scanned-book distribution without changing inference size or CPU cost, and whether a local Hindi improvement exists without third-party APIs.
- **Constraint:** production inference stays on **4 vCPU / 16 GB**, CPU-only. No third-party OCR APIs. Training used the workstation's 8 cores; the delivered artifact is the same 81M architecture.

## Summary

- **Telugu fine-tune works.** Fine-tuning only the 20M CTC encoder on 1,868 aligned real lines improved held-out **page median CER 0.0667 → 0.0514 (−23 %)** and **WER 0.500 → 0.389 (−22 %)** on 16 pages from held-out books. 11/16 pages improved; 4 regressed.
- **The gain is not free everywhere.** One hard Kalidasa cover regressed (0.817 → 0.865), and mean page CER only moved 0.1539 → 0.1499. The model still fails on decorative/mirrored pages.
- **Hindi: two alternatives rejected.** `hin` best-vs-fast ensembling had no gain (fast was better on 19/24 pages), and a synthetic multi-font Tesseract fine-tune degraded real pages (worse on 19/24; mean CER 0.0879 → 0.0972). Hindi stays on stock `hin` plus the routing fix; a real gain needs Hindi page-level GT.
- **Deployment:** fine-tuned weights live on oki's persistent storage volume (`/app/storage/models/telugu-ocr-ft`); compose points at it with automatic fallback to the baked base checkpoint.

## Telugu method

### Corpus

- **15 books / 3,940 line crops** from the 17 Wikisource-verified Telugu books with local PDFs.
- Tesseract `--psm 6` line boxes at 300 DPI; 4 px padding; blank crops dropped.
- **Book-level split:** every fifth book held out (3 usable test books, 16 pages, 349 lines).
- Labels recovered by running the current model on each line, aligning the concatenated hypotheses to the verified page text, and cutting the page text back per line. Lines with normalized similarity `<0.55` were discarded; 3,209/3,940 survived (mean similarity 0.944).
- Low-similarity `<0.4` labels were inspected and rejected: they were mostly reading-order/segmentation errors in multi-column or decorative pages, not recognition labels.
- Training set capped at 300 lines/book to prevent the two 800-line books from dominating: **1,868 train / 313 test**.

### Training

- Encoder-only CTC fine-tune (20M of the 81M parameters); decoder untouched. This is the path production uses (`decode="ctc"`).
- AdamW, lr 5e-5 cosine, batch 8, 4 epochs, CTC loss; 85 min on 8 CPU cores.
- Light augmentation: contrast/brightness/blur/±1.2° rotation.
- Checkpoint: 311 MB, same architecture/config; no inference memory or CPU increase.

### Results

| Set | Metric | Base | Fine-tuned | Change |
|---|---|---:|---:|---:|
| Held-out lines (313) | median CER | 0.0236 | **0.0222** | −6 % |
| Held-out lines | mean CER | 0.0546 | 0.0639 | worse |
| **Held-out pages (16)** | **median CER** | **0.0667** | **0.0514** | **−23 %** |
| Held-out pages | mean CER | 0.1539 | 0.1499 | −2.6 % |
| Held-out pages | median WER | 0.5000 | **0.3894** | −22 % |
| Held-out pages | pages improved | — | **11/16** | 4 worse |

Paired page deltas: median **−0.0111 CER**, mean **−0.0040**; most Kalidasa body pages improved 0.03–0.07 → 0.02–0.05. Regressions: the Kalidasa decorative cover and one body page.

Epoch-level line median: baseline 0.0236 → 0.0206 (ep1) → **0.0204 (ep2)** → 0.0208 (ep3) → 0.0213 (ep4). Epoch 2 was the line-level optimum; the deployed epoch-4 checkpoint still gives the page-level gain above.

Speed/RAM in the held-out page run: **3.1 s/page, 566 MB peak** (the base run was measured under concurrent training load, so its 18 s/page is not comparable). Same weights size, so the 4-vCPU production budget is unchanged.

## Hindi experiments (both rejected)

1. **`tessdata_best` vs `tessdata_fast` and confidence ensemble** on 24 real Hindi pages:
   - fast median 0.0628 / mean 0.0879
   - best median 0.0648 / mean 0.0989
   - choose-by-confidence median 0.0628 / mean 0.0877 (no gain)
   - fast was better on 19/24 pages. Keep fast `hin`.
2. **Synthetic Tesseract LSTM fine-tune** from the float `tessdata_best` model:
   - 13 Devanagari fonts, 10 train / 3 held-out, 500 iterations; train BCER 0.347 %.
   - On the 24 real Hindi pages: median 0.0617 (vs 0.0628 fast) but mean **0.0972 vs 0.0879**, worse on **19/24 pages**. Rejected; do not ship.
   - Lesson: synthetic font adaptation does not transfer to the old printed pages without real-page labels. Hindi needs hand-verified page-level GT before any fine-tune claim.

## Deployment

- Artifact: `/app/storage/models/telugu-ocr-ft` on the persistent `storage_data` volume.
- SHA-256 of `model.safetensors`: `fbcf8f1441e3ac92101ac6856dbf46110da7e9652303ffe3c73ffb2c9762a1e5`.
- Compose worker env:
  - `OCR_LINE_MODEL_NAME=/app/storage/models/telugu-ocr-ft`
  - `OCR_LINE_MODEL_FALLBACK_NAME=/app/ocr_models/telugu-ocr-model`
- `_resolve_model_name()` falls back to the baked base checkpoint if the volume artifact is missing (fresh host), so a deploy never drops to Tesseract just because the volume is empty.
- Weights are not committed (311 MB); the training scripts and reports are.

## Reproduce

```bash
# corpus + labels (workstation)
TESSDATA_PREFIX=/home/agamya/.cache/tessdata_fast \
  backend/.venv/bin/python backend/scripts/ocr_bench/build_line_corpus.py \
  --out /home/agamya/.cache/telugu-ocr-ft/data

TESSDATA_PREFIX=/home/agamya/.cache/tessdata_fast \
  /home/agamya/.cache/ocr-ft-venv/bin/python backend/scripts/ocr_bench/align_line_corpus.py \
  --data /home/agamya/.cache/telugu-ocr-ft/data

# CTC encoder fine-tune + held-out page eval
/home/agamya/.cache/ocr-ft-venv/bin/python backend/scripts/ocr_bench/finetune_telugu_lines.py \
  --data /home/agamya/.cache/telugu-ocr-ft/data --out /home/agamya/.cache/telugu-ocr-ft/model-ft-ctc \
  --mode ctc --epochs 4 --batch-size 8 --lr 5e-5 --max-per-book 300

TESSDATA_PREFIX=/home/agamya/.cache/tessdata_fast \
  /home/agamya/.cache/ocr-ft-venv/bin/python backend/scripts/ocr_bench/bench_lines.py \
  --model /home/agamya/.cache/telugu-ocr-ft/model-ft-ctc \
  --bundle /home/agamya/.cache/telugu-ocr-ft/eval_bundle --split-wide
```

## Caveats

- 16 held-out pages / 3 books is a small evaluation; the 23 % median gain is promising but not a full-corpus claim.
- Labels are model-aligned to verified page text, so easy lines dominate; the hard decorative/multi-column lines were excluded. The fine-tune improves the readable-body distribution, not the pathological pages.
- The deployed epoch-4 checkpoint is not the line-level optimum (epoch 2); a future run should keep epoch 2 and compare page-level on more held-out books.
- No Hindi model was improved; the routing fix in 029 remains the Hindi gain.

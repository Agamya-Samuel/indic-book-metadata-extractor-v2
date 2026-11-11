# 004 — OCR-Stage Error (Tesseract Telugu) vs Wikisource Ground Truth

- **Date:** 2026-11-11
- **Context:** The pipeline is OCR → LLM. The LLM half needs Ollama+Postgres (unavailable), but the **OCR half can be measured today** — Tesseract is installed. This quantifies where the information loss happens, which the earlier consultations ([reference/chat1.md](../reference/chat1.md), [chat2.md](../reference/chat2.md)) could only hypothesize.
- **Artifact:** [backend/scripts/eval_ocr.py](../backend/scripts/eval_ocr.py) (new).

## Method

For each Telugu book with a `wikisource_gt.json` (human-verified pages): render the same PDF pages (PyMuPDF @ 300 dpi), run the **pipeline OCR** (`app.services.ocr_service.run_ocr(..., "tel")`), and compute Character/Word Error Rate against the verified Wikisource text. Telugu+English tessdata were staged in a user dir and `TESSDATA_PREFIX` pointed at it (no system install).

```
cd backend
TESSDATA_PREFIX=/tmp/tessdata uv run python -m scripts.eval_ocr --limit 10 --pages 3 --out /tmp/ocr-report.json
```

## Results (14 books, up to 3 pages each)

**Median book CER = 0.453, median WER = 1.35** (mean CER 0.60 across 14 books). Typical range 0.20–0.62; a handful stay >1 even after length-guarding (near-empty or partial-reference pages). Table below is an earlier 10-book slice.

| Book | CER | WER |
|---|---|---|
| A_Collection_of_Telugu_Proverbs | 0.195 | 0.43 |
| 2015.372978.Andhra-Kavithva | 0.196 | 0.63 |
| 10049upanyaasans033612mbp | 0.410 | 1.10 |
| 2015.328360.Andhra-Mahaniyulu | 0.425 | 1.36 |
| 10031upanishhats033596mbp | 0.453 | 1.35 |
| 2015.373190.Athma-Charitramu | 0.456 | 1.08 |
| .Kalidasa-Charitra… | 0.610 | 1.81 |
| 10879telugukaavy034400mbp | 0.621 | 1.79 |
| 2030020025431_chitra_leikhanamu | 1.343 | 3.77 |
| 1857_ముస్లింలు | 15.497 | 19.25 |

**Median book CER ≈ 0.45; typical range 0.20–0.62.** Two outliers (CER > 1) are page-alignment / sparse-GT artifacts (title/cover pages where the verified text is near-empty), not literal character error. (After adding a reference-length guard, that book dropped to 0.245.)

## Key findings

- **Telugu OCR is the dominant error source.** Roughly **half of all characters are wrong** on a typical page (median CER ≈ 0.45); no metadata stage can recover that. This confirms the prior consultation: *garbage in, garbage out*.
- **CER > 1 is a data-quality flag, not a higher error rate.** It means the predicted text is much longer than the reference (or pages misalign) — mostly cover/title pages with little verified text. The evaluator must **gate on reference length and exclude `markup_residue` pages**, and report **median** rather than mean.
- **Structured/serif-heavy pages OCR best** (0.19–0.20 on *A Collection of Telugu Proverbs*, *Andhra-Kavithva*); verse/ornamental/small-type pages worst.
- **The harness's own pipeline path is separately broken:** [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) calls `PDFService.render_pages(...)`, which **does not exist** — so even with services up, `run_pipeline_on_pdf` would fail. Real scoring is blocked three ways: no tel tessdata on the host, no Ollama/Postgres, and the missing `render_pages` method.

## Preprocessing A/B (same 14 books, up to 3 pages)

| Preprocess before OCR | median CER | median WER |
|---|---|---|
| none (baseline) | **0.453** | 1.35 |
| adaptive binarization | 0.562 | 1.40 |
| Sauvola binarization | 0.581 | 1.41 |

**Binarization hurts.** Both Sauvola and adaptive thresholding *raised* Telugu CER by ~0.11–0.13 versus no preprocessing. The pipeline's advertised Sauvola step is counterproductive on this GT; the default config (`binarization: None`) is the better setting. Reproduce with `--preprocess {none,sauvola,adaptive}`.

### Render DPI (no binarization)

| DPI | median CER |
|---|---|
| **300 (baseline)** | **0.453** |
| 400 | 0.508 |
| 600 | not usable — large-format pages exceed PIL's image-size guard; no gain where it ran |

Higher DPI did **not** help; **300 DPI remains best**. Net: on this GT none of {binarization, denoise, higher DPI} improves Tesseract Telugu — the ~0.45 CER is the engine's ceiling, and a better OCR engine/model is required to move it.

## Recommendation

1. **Treat OCR quality as the priority.** Until Telugu CER drops well below ~0.1, field-extraction accuracy cannot improve much regardless of the LLM/prompt.
2. **Harden `eval_ocr.py`:** report median + per-page diagnostics; skip near-empty references; exclude `markup_residue` pages.
3. **Fix `PDFService.render_pages`** (or point the harness at the real render API) so end-to-end runs work once services are up.

## Next steps

- Run across all 14 OCR-GT books; add the length/misalignment guards.
- Add the missing `render_pages`; wire the LLM eval for when Ollama+Postgres are available.
- Compare OCR engines (Sauvola-binarized Tesseract vs alternatives) on the same GT.

## References

- Evaluator: [eval_ocr.py](../backend/scripts/eval_ocr.py) · GT: `backend/tests/fixtures/ground_truth/tel/*/wikisource_gt.json`
- Prior: [learnings/003](003-harness-and-wikisource-scaling.md) · [learnings/001](001-ground-truth-dataset-feasibility.md) · [plans/002](../plans/002-ground-truth-poc.md)
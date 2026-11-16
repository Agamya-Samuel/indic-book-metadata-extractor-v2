# 029 — Why the OCR Looks Wrong: Language Routing, the `+eng` Model, and Typeface Limits

- **Date:** 2026-11-16
- **Study context:** Investigate the reported poor OCR on Hindi/Telugu scanned books, verify the suspected Latin/English fallback against the actual code and runtime, and measure accuracy on representative scans rather than infer it. Preprocessing was investigated in parallel and is recorded separately: [027](027-default-preprocessing-upscale-benchmark.md) (the 1.5× upscale fix) and [028](028-line-model-preprocessing-benchmark.md) (line-model confirmation). This document covers **language/script routing, page-type routing, typeface effects, and the engine decision**.
- **Artifacts:** new harnesses [bench_lang_config.py](../backend/scripts/ocr_bench/bench_lang_config.py), [bench_fonts.py](../backend/scripts/ocr_bench/bench_fonts.py), [bench_line_fonts.py](../backend/scripts/ocr_bench/bench_line_fonts.py), and `--split-wide` in [bench_lines.py](../backend/scripts/ocr_bench/bench_lines.py). Reports are under `backend/reports/ocr-*`.
- **Environment:** Tesseract 5.5.0, `tessdata_fast` (tel 2.7 MB, hin 1.1 MB) and `tessdata_best` (tel 8.7 MB, hin 12 MB); PyMuPDF 1.27 at 300 DPI; `harsha-desaraju/telugu-ocr-model` 81.3 M params (310 MB) on CPU `torch 2.15.0+cpu` / `transformers 4.46.3`; Python 3.14 for Tesseract, Python 3.11 for the line model.
- **Data:** 21 pages from 8 Telugu books with Wikisource-verified page text (16 books / 187 usable Telugu pages exist); 24 real printed Hindi pages with verified text from the IndicVisionBench `ocr` set (the repo's Hindi books have metadata-only GT); controlled font renders of the same verified passage.

## Summary

The OCR is not uniformly bad, and the cause is not mainly "non-standard fonts".

- **Hindi is already strong** when correctly labelled: Tesseract `hin` median **CER 0.063**, WER 0.247 on 24 real printed pages. Adding English (`hin+eng`) raises CER to 0.081 and is ~1.8× slower.
- **Telugu body text is the weak language.** The production line model re-validates at median **CER 0.163** / WER 0.616 on 21 pages; Tesseract `tel` is 0.382 and `tel+eng` 0.331 on the same bundle (the `+eng` figure is helped by English front matter). On pure Telugu body pages the line model wins 14/15 pages.
- **The Latin/English fallback is real, but it is an integration bug, not Tesseract silently falling back.** `LANGUAGE_MAP` sends every Telugu page to `tel+eng` and every Hindi page to `hin+eng`; that injects Latin into pure-script pages and *increases* Telugu consonant errors from 14.5 % (`tel`) to 24.5 % (`tel+eng`). The line-model→Tesseract fallback also lands on `tel+eng`; forcing that path produced 13.7 % Latin on a Telugu body page while still reporting confidence 61.
- **A wrong upload language is catastrophic and currently unfixable in the UI.** Uploads default to **Telugu** (frontend and API), there is no script detection, and no endpoint changes a book's language. A Hindi page read as `tel+eng` scored **CER 0.824** with **77 % Latin / 23 % Telugu / 0 % Devanagari**.
- **Typeface matters, but the engine dominates.** Tesseract Telugu reaches only **0.153 CER on a perfectly clean Noto Sans rendering**; the best/worst Telugu fonts span 0.153–0.224. The line model reaches 0.084 on Noto Sans (oracle line crops) but 0.19–0.30 on decorative fonts. Controlled blur/low-contrast/low-resolution/noise changed CER by <0.02 — the recognition model, not mild scan degradation, is the floor.
- **The line model silently drops lines wider than 2048 px** (after scaling to height 64). On wide front-matter/cover lines this is catastrophic; splitting the crop recovered 132→1071 characters on the 1857 cover and CER **0.880→0.025**, and 0.548→0.203 mean CER on wide synthetic pages. On the 21-page bundle, 19/21 pages are byte-identical, but the cover recovery moves median CER **0.163→0.116** and mean 0.243→0.203. Production has no guard.
- **Recommendation:** script/page-type-aware routing (line model for Telugu body; Tesseract for Latin-heavy front matter and Hindi; `+eng` only where Latin is actually expected), plus upload-language integrity and the wide-line/empty-output guard. A new engine is not justified by the evidence; fine-tuning is a Phase-2 decision for historical typefaces/orthography, not the first fix.

## 1. Current OCR architecture and configuration

### Engines and models actually selected

| Path | Engine/model | Config |
|---|---|---|
| Telugu (`language == "tel"` and `OCR_TEL_ENGINE=line_model`) | `harsha-desaraju/telugu-ocr-model` (81.3 M, F32, 310 MB; CTC decoder) | Tesseract `--psm 6 --oem 1` line boxes → per-line `model.transcribe(decode="ctc")` |
| Telugu with engine `tesseract` (default in `Settings`, and the fallback) | Tesseract 5 stock `tel` **plus `eng`** | `--psm 3/4` from the page classifier, `--oem 1`, `--dpi 300` |
| Hindi | Tesseract 5 stock `hin` **plus `eng`** | same |
| English | Tesseract 5 `eng` | same |

Production worker compose defaults `OCR_TEL_ENGINE=line_model`; the backend container sets `tesseract` because it does not OCR. The worker image installs `tesseract-ocr-{tel,hin,eng}` and bakes the line-model weights at `/app/ocr_models/telugu-ocr-model` (`HF_HUB_OFFLINE=1`). No PaddleOCR, Surya, EasyOCR or cloud OCR runs in production.

`LANGUAGE_MAP` in [ocr_service.py](../backend/app/services/ocr_service.py) is the decisive integration point:

```python
LANGUAGE_MAP = {"tel": "tel+eng", "hin": "hin+eng", "eng": "eng"}
```

This mapping is global: it cannot distinguish a pure Telugu body page from a bilingual title page.

### Page → OCR input

- `pdf_service.render_full_page` renders at `settings.ocr_render_dpi` (300 DPI) with PyMuPDF.
- `page_tasks._insert_page` attaches `DEFAULT_PREPROCESSING_CONFIG` to every rendered page; `ocr_tasks` runs `preprocessing.run_pipeline` once and stores `processed_image_path`.
- After [027](027-default-preprocessing-upscale-benchmark.md), `run_pipeline` takes `source_dpi` (default `OCR_RENDER_DPI`), so a 300-DPI render is no longer rescaled to 450 DPI. The remaining default pass is grayscale + deskew + remove_borders; binarization and denoise stay off.
- The line model receives the *preprocessed page* and crops Tesseract `--psm 6` line boxes; it has no per-line confidence.

### Language selection and detection

There is **no language detection** (only a required-code validation now). At study time the upload form defaulted to Telugu in both places:

- At study time, [frontend/src/app/upload/page.tsx](../frontend/src/app/upload/page.tsx) defaulted to `useState("tel")` and [backend/app/api/books.py](../backend/app/api/books.py) to `language: str = Form("tel")`, with options Telugu/Hindi/English. Both now require an explicit choice.

At study time, the stored `ocr_results.language_detected` was simply the requested `book.language`, not a detection result, and `settings.default_ocr_language` was never read. A mislabelled book could only be fixed by re-upload. The implementation follow-up removed the default, requires an explicit language, and adds `PATCH /books/{id}/language` plus a header control.

### Dead/misleading configuration

| Setting | Status |
|---|---|
| `TESSERACT_TESSDATA_DIR` | **Was inert; fixed.** `pytesseract.pytesseract.tessdata_dir` is not a real attribute; the implementation now passes Tesseract's `--tessdata-dir` flag. |
| `OCR_CUSTOM_MODEL_DIR` | **Removed.** It was declared but never read; custom models now use `TESSERACT_TESSDATA_DIR` (a full tessdata directory). |
| `DEFAULT_OCR_LANGUAGE` | **Removed.** It was declared but never read; upload now requires an explicit language. |
| `_is_dictionary_enabled` | **Removed.** It was unused; `_build_config` checks `OCR_USE_DICTIONARY` directly. |
| `_classify_psm(..., page_position)` | Still accepts the position but ignores it; the docstring's "title page gets a rotation pass via `--psm 1`" is not implemented. There is no OSD/orientation/mirror handling. |

## 2. Measured accuracy

All numbers are page-level code-point CER/WER, Unicode NFC, whitespace-collapsed; "median" is over pages.

### Telugu — same 18 body pages, same images, only the language flag changes

Pages filtered to verified body text (`telugu_share ≥ 0.55`), 8 books, 300 DPI, no preprocessing.

| Config | median CER | mean CER | median WER | Latin share of output | s/page |
|---|---:|---:|---:|---:|---:|
| `tel@3` | **0.343** | **0.447** | 0.971 | 0.00 | 2.66 |
| `tel+eng@3` (mapping when Tesseract is selected or the line model falls back) | 0.376 | 0.480 | 0.978 | **0.21** | 4.24 |
| `eng@3` | 0.878 | 0.924 | 1.489 | **1.00** | 2.62 |
| `tel@4` | 0.308 | 0.413 | 0.975 | 0.00 | 2.77 |
| `tel@6` | 0.336 | 0.449 | 0.980 | 0.00 | 2.40 |
| `tel+eng@4` | 0.409 | 0.457 | 1.046 | 0.21 | 4.28 |

Adding `eng` is **not neutral**: it injects Latin and costs ~0.03–0.07 CER on pure Telugu, and it nearly doubles recognition time.

### Telugu — engine comparison on the 21-page benchmark bundle

The bundle includes front matter, so it is deliberately harsher than the body-only table above.

| Engine | median CER | mean CER | median WER | s/page | peak RAM |
|---|---:|---:|---:|---:|---:|
| `telugu-ocr-model` (CTC) | **0.163** | **0.243** | **0.616** | 7.7–9.7 (cold) | 534–604 MB |
| `telugu-ocr-model` + split-wide (same 21 pages) | **0.116** | **0.203** | 0.591 | 2.4 (warm) | 596 MB |
| Tesseract `tel` (psm 6) | 0.382 | 0.544 | 0.984 | 1.2 | 171 MB |
| Tesseract `tel+eng` (psm 6) | 0.331 | 0.404 | 0.983 | 1.8 | 186 MB |

The split-wide row is not a different recognition model: **19/21 pages are byte-identical**. It recovers the wide front-matter page (`1857` cover 0.880→0.025) and one body page is 0.006 worse (0.408→0.414). The median moves because the cover is one of 21 pages; the body-page score is unchanged.

The `tel+eng` bundle advantage disappears once pages are split by script:

| Page group | n | line model median | `tel` median | `tel+eng` median | Line model best |
|---|---:|---:|---:|---:|---:|
| Pure Telugu (`telugu_share ≥ 0.80`) | 15 | **0.163** | 0.295 | 0.405 | 14/15 |
| Mostly Latin (`latin_share ≥ 0.50`) | 5 | 0.060 | 0.881 | **0.014** | 2/5 |
| Mixed | 1 | 0.324 | 0.787 | 0.673 | 1/1 |

The line model's Latin median is misleading: it transcribes clean short English (archive boilerplate) but **drops most lines on dense English pages** (1857 cover: 132/1071 characters, CER 0.880). Tesseract `tel+eng` reads the same cover at CER 0.002. This is the page-type problem, not a Telugu recognition problem.

### Hindi — 24 real printed pages (IndicVisionBench)

| Config | median CER | mean CER | median WER | s/page | Note |
|---|---:|---:|---:|---:|---|
| `hin@3` | **0.063** | 0.088 | 0.247 | 1.7 | best |
| `hin+eng@3` (production mapping) | 0.081 | 0.115 | 0.267 | 3.0 | 4 % Latin, 29 % higher median error |
| `eng@3` | 0.821 | 0.824 | 1.000 | 2.3 | 100 % Latin |
| `tel+eng@3` (Hindi uploaded as Telugu) | **0.824** | 0.827 | 1.000 | 5.4 | **77 % Latin, 23 % Telugu, 0 % Devanagari** |
| `hin@4` | 0.063 | 0.085 | 0.247 | 2.4 | no gain |
| `hin@6` | 0.062 | 0.086 | 0.242 | 2.4 | no gain |

Hindi recognition is good on correctly labelled pages. The catastrophic row is a *routing* failure: exactly what the default upload language produces if the operator leaves the selector on Telugu.

### Typeface and degradation (controlled, same passage)

Seven Telugu fonts / six Devanagari fonts, same verified passage rendered at 11.5 pt, 300 DPI, then degraded.

| Test | median CER | range | Interpretation |
|---|---:|---:|---|
| Telugu, Tesseract `tel`, clean fonts | 0.211 | 0.153–0.224 | Noto Sans best (0.153); Tenali/Gurajada worst |
| Telugu, Tesseract `tel`, mild degradations | 0.199–0.212 | — | Blur/low contrast/150→300 DPI/noise changed almost nothing |
| Telugu, line model, **oracle line crops** | **0.168** | 0.084–0.217 | Noto Sans 0.084, Noto Serif 0.093, Tenali 0.146, Mallanna 0.217 |
| Telugu, line model, detected lines (narrow column) | 0.196 | 0.118–0.299 | detection adds ~0.03 |
| Hindi, Tesseract `hin`, clean fonts | **0.052** | **0.045–0.144** | Noto Serif 0.045, Lohit 0.047, Noto Sans 0.051; Kalam 0.144 |
| Hindi, Tesseract `hin`, mild degradations | 0.051–0.054 | — | Kalam remains 0.134–0.150 |

The important result is the **floor**: Tesseract Telugu is at CER 0.153 even on a pristine modern Noto rendering. Font choice adds ~0.07 CER; mild scan degradation adds <0.02. You cannot preprocess your way from 0.15 to 0.02.

### Real-book spread (Telugu line model, 8 books)

Median page CER by book: 0.033 (2009 reprint) and 0.060/0.088 (1927/1928) up to 0.396 (1891) and 0.236 (1956). The old 1891–1894 books are the worst. This is consistent with historical typeface/orthography/scan quality, but the sample is small; it is not a clean era-controlled experiment.

### Error categories (aggregated edit operations, pure-script pages)

| Category (ref chars) | Line model Telugu | Tesseract `tel` | Tesseract `tel+eng` | Tesseract `hin` |
|---|---:|---:|---:|---:|
| consonants | 4.9 % | 14.5 % | **24.5 %** | 2.2 % |
| matras | 5.1 % | 10.3 % | **21.5 %** | 2.6 % |
| virama | 6.1 % | 15.6 % | **28.4 %** | 3.9 % |
| spaces | 16.4 % | 13.6 % | 12.8 % | 1.9 % |
| Indic digits | 44.3 % | 67.2 % | 58.0 % | 33.6 % |
| punctuation | 25.1 % | 41.3 % | 38.6 % | 28.1 % |
| Latin | 74.6 % | 100 % | 59.3 % | 100 % |
| **conjunct clusters** | **9.6 %** | **35.5 %** | **42.1 %** | 8.4 % |

Caveats: edit alignment charges dropped spaces and layout differences; "Latin 100 %" for a monolingual model means it *cannot emit Latin*, not that every Latin glyph is misread. Still, the ranking is unambiguous: the line model is much better on Telugu consonants/matras/virama; digits and punctuation are weak for **both** engines; `+eng` makes conjugate/accented Telugu materially worse.

### `tessdata_best` and joint decode

| Experiment | Result | Verdict |
|---|---|---|
| Telugu `tel+eng`, best vs fast (21 pages) | median 0.318 vs 0.331, mean 0.377 vs 0.404, 2.7× slower | Not a reliable gain; keep fast |
| Telugu `tel`, best vs fast | median 0.403 vs 0.382 | No |
| Hindi `hin`, best vs fast | median 0.062 vs 0.068, mean 0.097 vs 0.085, 2.1× slower | Marginal/noisy; keep fast |
| Line model, joint vs CTC (3 pages) | median 0.111 vs 0.116, mean **0.225 vs 0.178**, 28.1 vs 4.4 s/page, 788 vs 505 MB | Keep CTC; joint is 6.4× slower and not robust on the degraded page |

## 3. The Latin/English fallback: what actually happens

The suspicion is confirmed, but the mechanism is **not** an automatic Tesseract fallback when a language model is missing.

1. **Tesseract does not silently fall back to English.** If `tel.traineddata` is absent it fails hard (`Failed loading language 'tel'`), as observed. The presence of `eng` in `tel+eng` is an explicit request to load both LSTM models. On noisy/pure-Telugu pages the English model wins some glyphs and emits Latin rubble.
2. **Our mapping asks for it globally.** `tel→tel+eng` and `hin→hin+eng` are applied to every page, including pure-script body pages. Measured effect on Telugu body: 21 % Latin output, consonant error 14.5 %→24.5 %, matra 10.3 %→21.5 %, virama 15.6 %→28.4 %.
3. **The line-model failure path lands on the same Latin-prone config.** `run_ocr` catches any line-model exception and calls `_run_ocr_with_img`, which resolves `tel` to `tel+eng`. Forced locally (no `transformers` installed): `engine=tesseract`, `engine_fallback_reason=ModuleNotFoundError`, 639 chars, **13.7 % Latin**, confidence **61.0**. The book completes normally; only `pages.ocr_error` records the fallback.
4. **The wrong-language upload is the most likely source of "everything came out Latin".** Hindi pages read with `tel+eng` produced 77 % Latin / 23 % Telugu / 0 % Devanagari (CER 0.824). Because the upload defaults to Telugu and there is no language edit, this failure is easy to trigger and impossible to correct in place.
5. **Models are present.** The worker image installs `tesseract-ocr-tel`, `-hin`, `-eng` and bakes the line model. The problem is not a missing recognition model; it is the language flag and page routing. The one genuine model-plumbing defect is `TESSERACT_TESSDATA_DIR` being inert, so a custom/best model silently never loads.

## 4. Root causes of poor recognition

| Rank | Cause | Evidence | Fix type |
|---|---|---|---|
| 1 | Wrong language / wrong engine routing (Hindi uploaded as Telugu; Latin-heavy pages sent to Telugu line model) | CER 0.824, 77 % Latin for Hindi-as-Telugu; 1857 cover 0.880 with line model vs 0.002 with `tel+eng` | Application routing |
| 2 | Tesseract Telugu is a weak recognizer | 0.153 CER on clean Noto; 0.382 on real pages; line model 0.163 on real pages | Engine/model choice (already line model) |
| 3 | Global `+eng` on pure-script pages | 21 % Latin on Telugu body; Telugu consonant error +10 points; 2–3× slower | Per-page script routing |
| 4 | Line model silently drops over-wide lines | 2048-px guard; wide synthetic mean CER 0.548→0.203; 1857 cover 0.880→0.025; 19/21 real pages unchanged | Integration guard |
| 5 | No orientation/mirror handling; stale classifier docstring | One GT page is mirrored microfilm; no OSD call | Page preflight |
| 6 | Digits/punctuation are weak in every engine | Telugu digits 44–67 % error; Hindi digits 34 %; punctuation 25–41 % | Post-processing/regex |
| 7 | Historical typefaces/orthography | Old books 0.2–0.4 vs modern 0.033; font matrix 0.084–0.30 | Fine-tune / better model |
| 8 | Preprocessing is not the lever | 027: default upscale cost accuracy, now fixed; 028: line model neutral; mild degradations <0.02 | Config only |
| 9 | Detection/segmentation | Oracle vs detected line model: ~0.03 CER; front-matter line loss larger | Better detector / routing |

What can be fixed without new models: causes 1, 3, 4, 5, 6 and the configuration parts of 8. What needs model work: cause 2 (already addressed for Telugu by the line model), cause 7 (fine-tune), and the worst part of 9 (a purpose-built line detector).

## 5. Fonts, typography, and historical books

- **Typeface sensitivity is real but bounded.** On clean renders, the best-to-worst span is 0.153–0.224 for Tesseract Telugu and 0.084–0.217 for the line model. Decorative/handwriting-like Devanagari (Kalam) is ~3× worse than Noto Serif for Hindi (0.144 vs 0.045).
- **Mild degradation is not the dominant term.** Gaussian blur, low contrast, 2× downscale/upsample, and noise+1.5° skew changed CER by <0.02 on both languages. The engine's recognition floor dominates; severe warping/fading was not tested here.
- **Old books are worse.** The line model's per-book medians rise from 0.033 (2009) to 0.396 (1891). That is consistent with older type, denser/smaller text, ink spread, and historical orthography that Wikisource modernizes in the reference. The sample is 8 books; treat as a signal, not a controlled study.
- **Legacy/non-standard fonts are a glyph-style problem for OCR, not an encoding problem.** The scanner stores pixels, not the font's character map. OCR quality depends on glyph shapes and layout; a legacy font with unusual shapes is effectively an out-of-distribution typeface. Fine-tuning on representative book lines (not just synthetic modern fonts) is the way to adapt.
- **The Telugu model card explicitly says "no historical orthography".** Its training mixed synthetic 30-font renders with real Wikisource line crops. Our 1891–1956 books are a plausible distribution shift.

## 6. Alternative models and approaches (research, not local benchmarks)

| Option | Reported/measured | CPU fit (4 vCPU / 16 GB) | Licence | Verdict |
|---|---|---|---|---|
| **Current Telugu line model** | 1.34 % line CER (CTC) / 1.19 % (joint) on its own 1,044-line benchmark; our page-level 0.163 | 4–10 s/page, 0.5–0.8 GB | MIT | Keep; fix routing and wide-line guard |
| **Tesseract 5 `hin`** | 0.063 median on real printed Hindi here; ~0.072 prior | 1.7 s/page, 44 MB | Apache-2.0 | Keep for Hindi |
| IndicOCR (bodhan-ai) | Published Hindi/Telugu word accuracy ~96 % / 82 %; 0.8 B VLM + 33 M layout, 1.7 GB weights | **>12 min/page measured on 4 vCPU** | Indic Open Model (gated) | No for CPU; revisit only on GPU |
| Surya 2.5 | 689 M VLM, 4.5 pages/s on H100; 91-language pass 74.9 %; Hindi 67.6 %; Telugu (Surya 1) 9.88 % line CER, worse than Tesseract 6.64 % | CPU via `llama.cpp`; M4 Max 0.19 pages/s with 8 parallel, ~4.8 GB | OpenRAIL-M (<$5 M) | Defer; not a Telugu step-up |
| PaddleOCR 3.7 | Telugu 9.21 % line CER; prior page 0.511, 13 s/page, 1.28 GB; 3.x segfaults on this CPU | Poor | Apache-2.0 | No |
| Sarvam Vision | Hosted; Telugu 84.3 % word accuracy, Hindi 95.7 % (IndicOCR comparison) | API/GPU | Commercial | Optional cloud fallback only |
| EasyOCR / Chitrapathak-2 | Previously rejected / GPU-only | — | — | No |
| `tessdata_best` | No reliable gain here (Telugu/Hindi) | 2–2.7× slower | Apache-2.0 | No |

### Fine-tuning: necessary?

- **Not for the first fix.** The largest immediate gains are routing, the wide-line guard, and language integrity; no model training is required.
- **Likely for historical Telugu/Hindi typefaces.** The line model is already good on modern fonts (0.084 oracle) but 0.19–0.30 on decorative ones and 0.2–0.4 on old books. A PoC should fine-tune the 81 M Telugu model on ~3k line crops from our 187 verified pages (book-level held-out split), and/or fine-tune Tesseract Hindi on a real line corpus.
- **Hindi fine-tuning still needs plumbing and data.** The custom-model path is now real (`TESSERACT_TESSDATA_DIR`), but `train_tesseract_lstm.sh` has invalid flags and the corrections export does not exist ([026](026-ocr-accuracy-strategy-review.md) §B). Fix those and build Hindi page-level GT before a training claim.

## 7. Recommended architecture and configuration

### Routing matrix (the main change)

| Page type (detected from script share / cheap classifier) | Primary engine | Language flag | Fallback |
|---|---|---|---|
| Telugu body (Telugu share high) | Telugu line model, `ctc` | `tel` only | Tesseract `tel` (not `tel+eng`); flag page |
| Latin-heavy front matter / cover (Latin share high) | Tesseract page OCR, `--psm 3/4` | `tel+eng` or `eng` | `eng` |
| Mixed/bilingual page | Tesseract `tel+eng`; or run both and merge by script | `tel+eng` | Telugu line model only on Telugu lines |
| Hindi body | Tesseract `hin` | `hin` only | `hin+eng` on Latin-heavy pages |
| English | Tesseract `eng` | `eng` | — |

Implementation notes:

- Route on the **actual OCR output's script shares** (implemented): it is free and uses real text. OSD is not reliable enough as a pre-OCR language selector (measured 9/11 on Telugu pages, 1–2 s/page), so it was deferred; do not use `book.language` alone as a page-level truth.
- For the line model, split any crop whose `width/height * 64 > 2048` into overlapping pieces (~92 % of the limit, 16 px overlap), transcribe, and rejoin. If a page yields no non-empty lines, fall back to Tesseract and record `engine` + reason. **Do not add a line-count coverage threshold**: measured minimum coverage was 0.66 and a 0.70 cutoff would choose Tesseract on a page where it scores 1.35 CER vs the line model's 0.41.
- Custom models go in `TESSERACT_TESSDATA_DIR`, which now passes `--tessdata-dir`; the directory must contain every language the OCR path loads. `OCR_CUSTOM_MODEL_DIR` and `DEFAULT_OCR_LANGUAGE` are removed.
- Keep `OCR_LINE_MODEL_DECODE=ctc`. Do not switch to `joint` globally (6.4× slower, no page-level gain here); use it only if a low-confidence-line retry policy is shown to help.
- Keep 300 DPI, no upscale for 300-DPI renders, no binarization/denoise. Test the remaining deskew/border pass on Hindi specifically; on the external Hindi set it cost ~0.009 median CER (0.068→0.077), so make it per-book rather than universal if that reproduces on our scans.
- Add `pages.ocr_engine` / model version / coverage to the OCR result so review and audits can see which path ran.

### Upload language integrity

- Do **not** default to Telugu. Require an explicit choice, or show an "auto-detect from first pages" step with a confidence and a warning.
- Add a book-language edit endpoint that clears OCR text/results (or marks them superseded) and re-runs OCR; the current app cannot fix a wrong label.
- On upload/first render, run a cheap script check and warn if the selected language's script share is near zero. This one guard prevents the 0.824-CER failure mode.

## 8. Improvement roadmap

| Phase | Work | Success gate |
|---|---|---|
| **P0 — routing & guards** | Script/page-type routing; explicit upload language + edit/re-OCR; split over-wide line crops; empty-output fallback; record engine/coverage; fix `TESSERACT_TESSDATA_DIR` and remove `OCR_CUSTOM_MODEL_DIR` | Pure Telugu median ≤0.16 preserved; Hindi ≤0.07; no page with zero output silently accepted; a mislabelled Hindi book is rejected/warned, not OCR'd as Telugu |
| **P1 — page preflight** | OSD orientation + mirror/rotation flag; front-matter vs body classifier; better PSM for sparse covers (`3/4`, not `11`); page-level confidence/coverage UI | No mirrored/rotated page enters OCR unflagged; front-matter English CER ≤0.05 with Tesseract |
| **P2 — data & fine-tune PoC** | Hindi page-level GT (≥2 books); Telugu line-crop corpus from the 187 GT pages; fine-tune the 81 M model; Hindi Tesseract fine-tune only after plumbing (§026) | ≥15 % relative median CER reduction on held-out books; no >2-point regression on any book; s/page ≤+25 % |
| **P3 — detection** | Replace/augment Tesseract `--psm 6` line boxes with a purpose-built detector (OpenCV projection, Paddle DB detector, or similar); evaluate oracle-vs-detected gap | Detected-line CER within 0.03 of oracle on book pages; no line loss on dense front matter |
| **P4 — deferred** | Joint/beam only on low-confidence lines; ONNX; cloud/VLM fallback (Sarvam/Surya/IndicOCR) | Only with a measured win and an explicit GPU/cloud/licence decision |

## Reproducing the measurements

```bash
cd backend

# Telugu: same pages, only the language/PSM changes (18 body pages / 8 books)
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast .venv/bin/python \
  scripts/ocr_bench/bench_lang_config.py --lang tel --books 8 --pages 3 \
  --configs tel@3,tel+eng@3,eng@3,tel@4,tel+eng@4,tel@6

# Hindi: 24 real printed pages from IndicVisionBench
.venv/bin/python scripts/ocr_bench/fetch_indicvision_hindi.py
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast .venv/bin/python \
  scripts/ocr_bench/bench_lang_config.py --lang hin --pages-limit 24 \
  --configs hin@3,hin+eng@3,eng@3,tel+eng@3,hin@4,hin@6

# Controlled typeface + degradation matrix (same passage per font)
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast .venv/bin/python \
  scripts/ocr_bench/bench_fonts.py --lang tel --fonts-dir /tmp/ocr-eval/fonts/tel \
  --degradations clean,blur,low_contrast,low_res,noise_skew

# Line model on oracle line crops (Python 3.11 + torch/transformers 4.46)
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast ~/.cache/ocr-line-venv/bin/python \
  scripts/ocr_bench/bench_line_fonts.py --bundle /tmp/ocr-eval/font_renders/tel_narrow --decode ctc

# Wide-line split PoC (compare with and without --split-wide)
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast ~/.cache/ocr-line-venv/bin/python \
  scripts/ocr_bench/bench_lines.py --decode ctc --bundle /tmp/ocr_bundle --out /tmp/lines.json
TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast ~/.cache/ocr-line-venv/bin/python \
  scripts/ocr_bench/bench_lines.py --decode ctc --bundle /tmp/ocr_bundle --split-wide --out /tmp/lines-split.json
```

`/tmp/ocr-eval/tessdata_fast` is the `tel`/`hin`/`eng` set from `tesseract-ocr/tessdata_fast`; `/tmp/ocr_bundle` is built by `scripts/ocr_bench/build_bundle.py 8 3`; `/tmp/hin_bundle` by `fetch_indicvision_hindi.py`. The reports referenced above were produced with those exact commands and are copied into `backend/reports/ocr-*`.

## 9. Caveats

- The deployed worker image was not inspected directly; "production uses line_model" is from compose/config/docs. The fallback path was exercised locally.
- Hindi accuracy is measured on **IndicVisionBench**, not our Hindi books, because our Hindi corpus has no page-level verified text. This is the same caveat as [020](020-ocr-engine-benchmark.md); closing it is Phase 1 of [plans/019](../plans/019-ocr-accuracy-improvement.md).
- n = 21 Telugu pages / 8 books and 24 Hindi pages. Page-level CER penalizes title/cover pages and dropped spaces; medians are reported, and the 1857 cover is explicitly a layout/width failure, not a recognition score.
- The 2048-px width guard did **not** fire on the 18 body pages used by 027/028 (crop heights keep the scaled width under the limit). It does fire on wide front matter/cover lines and on synthetic wide columns — both are demonstrated here. This is not a contradiction; it is a page-type-specific failure.
- `tessdata_best` and font-matrix results are CPU-local and single-run; paired pages are used where possible, but confidence intervals are not computed. The workstation also ran a concurrent preprocessing benchmark during part of this work, so **s/page figures are indicative, not controlled throughput measurements**; accuracy comparisons use identical images and are unaffected.
- No claim is made that fine-tuning will fix historical fonts until the P2 PoC is run.

## Recommendation

**Go with the existing engines, fixed at the routing layer.** Telugu body → line model (CTC); Hindi body → Tesseract `hin`; Latin-heavy front matter → Tesseract `tel+eng`/`eng`; never apply `+eng` globally and never let a Telugu default silently process a Hindi book. Add the wide-line split and empty-output fallback. Defer new engines; fine-tune only after routing and data are fixed, and gate it on held-out-book CER.

## Implementation status (2026-11-16)

Shipped after this study, with tests:

- **Line model:** over-wide crops are split at the checkpoint's real limit (92 % + 16 px overlap) instead of silently returning `""`; a page where every detected line is empty now raises `LineModelEmptyOutput`, so `run_ocr`'s existing Tesseract fallback runs. Two split tests + an empty-output test; 381 unit tests pass.
- **Upload language:** the API now rejects a missing language with 422; the upload UI starts empty and blocks submit until a language is chosen. Tests updated (6 upload cases).
- **Language correction:** `PATCH /api/books/{id}/language` reuses the re-run OCR path (cancel, clear OCR, reset from OCR, keep PDF/pages/metadata, enqueue OCR when pages exist). Four integration tests, including a `hin` dispatch assertion. A `BookLanguageControl` on the book header exposes it with a confirmation and navigates to OCR processing when a job is queued.
- **Custom tessdata:** `TESSERACT_TESSDATA_DIR` now passes Tesseract's real `--tessdata-dir` flag; the old `pytesseract.tessdata_dir` attribute was inert. Two unit tests.
- **Latin-page reroute:** `process_page_image` now re-runs a Telugu line-model page through Tesseract when the line output is at least 80 % Latin and at most 20 % Telugu, keeping Tesseract only if it found at least half as much text. Simulated on the 21-page bundle: **3/21 pages change** (the 1857 cover 0.880→0.014, one Angleya page 0.060→0.000, one unchanged), pure Telugu pages untouched; bundle median **0.163→0.116**, mean 0.243→0.199.
- **Dominant-script reroute:** a Tesseract page that is ≥85 % of the book's script and ≤15 % Latin is re-run without `+eng` (`hin+eng`→`hin`, `tel+eng`→`tel`), keeping the narrower model only if it retains ≥90 % of the text. Simulated on the same pages: Hindi **23/24 pages change, median 0.090→0.061, mean 0.112→0.087**; Telugu Tesseract **9/21 pages change, median 0.331→0.272, mean 0.404→0.383**. Bilingual/Latin pages keep the combined model. Flag: `OCR_SCRIPT_ROUTING` (default true); 7 routing unit tests.
- **Coverage threshold — rejected.** Instrumented non-empty-line coverage on the 21 pages: minimum **0.66** (median 1.0). A 0.70 cutoff would fall back on `10879…p5`, where Tesseract is **1.35 CER vs the line model's 0.41**; a 0.5 threshold never fires. The total-empty guard is the only safe coverage rule; do not add a line-count threshold without a page-type signal.
- **Audit metadata:** migration 017 adds nullable `ocr_engine`, `ocr_route`, `ocr_coverage`, and `ocr_script` to `ocr_results`; the worker persists them and the OCR API returns them. This makes routing decisions auditable after the fact. A review-UI badge is still pending.

Deferred by evidence (not blockers): OSD preflight (9/11 Telugu; output-script routing is more reliable), automatic mirror detection (the known mirrored page needs manual review), and a purpose-built line detector (oracle-vs-detected gap ~0.03 CER; recognition dominates). Fine-tuning remains gated by Hindi page-level GT and a training run. The dead settings were removed and custom models are wired through `TESSERACT_TESSDATA_DIR`.

## Next steps

1. Build page-level Hindi GT for ≥2 of our books — the gate for any fine-tune claim ([plans/019](../plans/019-ocr-accuracy-improvement.md) Phase 1).
2. Re-run the P0 matrix through `process_page_image` on the frozen 21+24-page corpus and record before/after CER/WER, s/page, and RAM alongside the simulated results.
3. Flag mirrored/rotated pages for manual review (OSD cannot detect mirroring; auto-rotation is not justified without a measured win).
4. Revisit OSD/line-detector work only with a measured book-level gap; do not add a coverage threshold.

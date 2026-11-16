# OCR

OCR turns a page image into text plus word boxes. The project supports Tesseract for every language
and an optional fine-tuned line model for Telugu, with script-aware routing between them.

- Orchestration: `backend/app/services/ocr_service.py`
- Telugu line model: `backend/app/services/ocr_line_model.py`
- Text normalisation: `backend/app/services/ocr_postprocess.py`
- Page-type classification: `backend/app/services/page_classifier.py`
- Task: `backend/app/tasks/ocr_tasks.py`

---

## 1. The single entry point

`process_page_image(image_path, language, page_position=None, include_retry=True)` is the **only**
production path. The OCR worker and the evaluation corpus builder both call it, which matters: before
it existed the corpus called `run_ocr` directly, skipped post-processing, and therefore measured text
that production never stored.

```text
run_ocr()
  ├─ line model (Telugu only, when selected)  ── on error ─▶ Tesseract + fallback reason
  └─ Tesseract
       ↓
  script rerouting (two independent rules)
       ↓
  low-confidence word retry (Tesseract only)
       ↓
  normalisation (NFC, danda, ZWJ/ZWNJ)
       ↓
  { raw_text, cleaned_text, words, corrections, script_shares, engine, … }
```

---

## 2. Engines

Selected by `OCR_TEL_ENGINE` (default `tesseract`).

### Tesseract

| Setting | Default | Effect |
| --- | --- | --- |
| `TESSERACT_CMD` | `tesseract` | Binary path |
| `TESSERACT_OEM` | `1` | LSTM engine only |
| `OCR_RENDER_DPI` | `300` | Passed as `--dpi` |
| `TESSERACT_TESSDATA_DIR` | `""` | Enables `--tessdata-dir` when set |

Language strings come from `LANGUAGE_MAP`:

| Book language | Tesseract language |
| --- | --- |
| `tel` | `tel+eng` |
| `hin` | `hin+eng` |
| `eng` | `eng` |
| anything else | passed through |

The combined `+eng` model is the starting point because colonial-era Indian books routinely mix
English front matter with Indic body text. Routing may then narrow it — see §4.

Page segmentation mode is chosen by `page_classifier.classify_page()`; if classification fails the
code falls back to `PSM.UNIFORM_BLOCK` rather than propagating an I/O error.

The final config string is:

```text
--psm <n> --oem <oem> --dpi <dpi> [--tessdata-dir "<dir>"] [--user-words "<f>"] [--user-patterns "<f>"]
```

Dictionary files are only added when `OCR_USE_DICTIONARY` names the active language.

### Telugu line model

Enabled with `OCR_TEL_ENGINE=line_model`, and only for `language == "tel"`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `OCR_LINE_MODEL_NAME` | `harsha-desaraju/telugu-ocr-model` | Base model (baked into the worker image) |
| `OCR_LINE_MODEL_FALLBACK_NAME` | `/app/ocr_models/telugu-ocr-model` | Used when the fine-tuned path is missing |
| `OCR_LINE_MODEL_DECODE` | `ctc` | Decoding strategy |
| `OCR_LINE_MODEL_CONFIDENCE` | `50.0` | Stand-in confidence (the model emits none) |

Measured Telugu CER is materially better than Tesseract, which is why the engine exists. It emits
**line-level** boxes and no word confidences, so the stored confidence is a conservative 50.0 to make
the review UI warn rather than show a false green.

**Hard requirement:** a failure in the line model must never fail the page. Every exception falls back
to Tesseract and records `engine_fallback_reason`, which the worker stores on `pages.ocr_error` as
`Telugu line OCR fell back to Tesseract: …`.

---

## 3. Low-confidence word retry

Runs only for Tesseract output (`ocr_low_conf_retry` default `true`).

For each word with `confidence < OCR_LOW_CONF_THRESHOLD` (default 40):

1. Crop the word's bounding box.
2. Re-OCR the crop with `--psm 8` (single word).
3. Accept the new text when it is non-empty and different, and raise the confidence to at least the
   threshold.

Word-level OCR is noticeably better than a page-level pass on noisy Indic pages. This pass only
rewrites the **word boxes** the review canvas draws; it does not change `raw_text` or `cleaned_text`,
which come from the page-level pass.

The corpus builder disables it (`include_retry=False`) because it is expensive — one crop OCR per
low-confidence word — and provably cannot change the text.

---

## 4. Script routing

Two independent, opt-in-seeming rules, both gated by `OCR_SCRIPT_ROUTING` (default `true`). Each
re-OCRs a page with a different configuration and keeps the alternative only when it produced enough
text.

### Rule A — Latin page re-route (line model only)

Fires when **all** hold:

- engine is `line_model`
- language is `tel`
- Latin share ≥ 0.80 and Telugu share ≤ 0.20

Rationale: covers, half-titles and English copyright pages are exactly where a Telugu line model
drops lines. Tesseract's layout and English model win there.

Acceptance: Tesseract's text must be at least **50%** the length of the model's output. A much
shorter result usually means the page was not Latin prose after all.

### Rule B — dominant-script re-route (Tesseract only)

Fires when:

- engine is `tesseract`
- language is `hin` or `tel`
- the expected script share ≥ 0.85 and Latin ≤ 0.15
- the page is not already using the narrowed language

It re-runs with `hin` instead of `hin+eng`, or `tel` instead of `tel+eng`. Measured medians:

| Language | Combined | Narrowed |
| --- | --- | --- |
| Hindi | 0.081 CER | **0.063** with `hin` |
| Telugu | 0.331 CER | **0.272** with `tel` |

Acceptance: the narrowed text must be at least **90%** the length of the combined result.
Bilingual pages keep the combined model because their dominant-script share is below 0.85.

Both rules record `ocr_route` (`latin_page_reroute` / `dominant_script_reroute`) so a page's history
explains why its engine or language differs from the book default. Any routing failure is logged and
the primary result is kept.

---

## 5. Normalisation

`ocr_postprocess.normalize_text(raw_text, language)` returns `(cleaned, corrections)`.

| Rule | Action | Skipped when |
| --- | --- | --- |
| `nfc_normalize` | Unicode NFC | never |
| `danda_normalize` | `|` → `।`, `||` → `॥` | language is `eng` (pipes are legitimate there) |
| `strip_spurious_zwj` | remove U+200D | never |
| `strip_spurious_zwnj` | remove U+200C | never |

Every change is recorded as a `Correction{original, replacement, position, rule}` and stored in
`ocr_results.corrections.rules`, so normalisation is auditable rather than invisible.

Danda and ZWJ/ZWNJ issues are common in Indic Tesseract output and disrupt downstream tokenisation and
LLM comprehension, which is why they are corrected before extraction.

---

## 6. What gets persisted

| Column | Content |
| --- | --- |
| `raw_text` | Page-level Tesseract/model output |
| `cleaned_text` | After normalisation |
| `corrected_text` | Human edit from the review screen; **never overwritten by a worker** |
| `bounding_boxes` | `{"words": [{text, confidence, bbox, block_num, line_num, word_num}]}` |
| `confidence` | Mean word confidence (or the line model's stand-in) |
| `language_detected` | The book language used |
| `ocr_engine` | `tesseract` or `line_model` |
| `ocr_route` | Set only when routing changed the engine/model |
| `ocr_coverage` | `word_count / detected_lines` when line count is known |
| `ocr_script` | Latin / Telugu / Devanagari share of the text |
| `corrections` | `{"rules": [...]}` |

On success, `pages.ocr_error` is cleared — except it is set to the fallback notice when the Telugu
line model degraded to Tesseract.

---

## 7. Book-level orchestration

`run_ocr_for_book`:

1. Mark the job running, snapshot page ids in page order.
2. For each page: check `should_stop()`, process, capture confidence, update progress, emit SSE.
3. Aggregate mean confidence and duration, record metrics.
4. Finalise.

### Outcome rule

`ocr_outcome(total_pages, errors)` decides the terminal state:

| Situation | Job | Stage |
| --- | --- | --- |
| No errors | `completed` | `ocr` completed |
| Some pages failed | `completed`, `error_log = "Some pages failed: …"` | `ocr` completed |
| Every page failed | `failed`, `error_log = "All pages failed: …"` | `ocr` failed |

Partial success advancing is deliberate: the text that did work is reviewable, and blocking the book
would strand it. Failed pages keep their message on `pages.ocr_error` so the UI can flag them.

---

## 8. Human correction

The OCR review screen writes `corrected_text` and per-word edits. Extraction reads
`corrected_text → cleaned_text → raw_text`, first non-empty, so corrections take effect without a
separate "re-extract" trigger.

Corrections are stored alongside the automatic ones in `ocr_results.corrections`, keeping provenance
for both.

---

## 9. Limitations

1. **Tesseract is CPU-bound and slow.** Per-page OCR ranged 3–86 s on the reference host; the slowest
   four pages consumed 54% of OCR wall-clock. Page-level parallelism is not a free win because
   Tesseract's OpenMP already uses ~3.35 of 4 cores for a single page.
2. **Only Telugu, Hindi and English** are mapped. Other scripts pass through unmapped and are
   effectively unsupported.
3. **No table or multi-column layout reconstruction.** `image_to_data` output is a flat word stream.
4. **The line model emits no word confidences**, so its confidence is a fixed stand-in.
5. **No automatic language detection at page level.** The book language drives everything; script
   shares are recorded but do not change the book language.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `TesseractNotFoundError` | Binary missing or `TESSERACT_CMD` wrong. Install `tesseract-ocr` or fix the path |
| `Failed loading language 'tel'` | `tesseract-ocr-tel` not installed, or `TESSERACT_TESSDATA_DIR` lacks `tel.traineddata` |
| Every Telugu page has `ocr_error: "… fell back to Tesseract"` | `OCR_TEL_ENGINE=line_model` without torch/transformers/weights. Build with `OCR_LINE=true`, or set the engine back to `tesseract` |
| Worker OOM or very slow first page | The line model loads ~779 MB. Keep concurrency at 1 |
| Poor accuracy on body pages | Check `OCR_RENDER_DPI` is 300, disable preprocessing, and read the PSM label in the logs |
| Danda `।` appears in English text | Should not happen: `_danda_cleanup` is skipped when `language == "eng"` (regression test in `test_ocr_postprocess.py`) |
| Dictionaries ignored | `OCR_USE_DICTIONARY` must list the language (`hin,tel`) **and** the files must exist in `backend/app/services/dictionaries/` |

## 11. Adding a language

1. Add `tesseract-ocr-<lang>` to `docker/Dockerfile.backend`.
2. Add `"<lang>": "<lang>+eng"` to `LANGUAGE_MAP` in `ocr_service.py`.
3. If using dictionaries, add `<lang>.words` / `<lang>.patterns` under
   `backend/app/services/dictionaries/`.
4. Rebuild the image (`make rebuild`).

Route decisions, script thresholds and the line-model/model selection are described above; this is
only the mechanical plumbing. New languages should also be added to the evaluation corpus before being
claimed as supported — see [evaluation](../testing/evaluation.md).


# LLM Extraction — Conversation Log

This document captures the investigation, fixes, and follow-up discussions about the
LLM extraction zero-fields issue in the Indic Book Metadata Extractor.

---

## 1. Initial Report

**Symptom**: LLM extraction jobs complete "successfully" but extract **0 fields** from
book content. The UI shows "View extracted fields (0)" for every run and all fields
display "Not extracted", including the cheap-extractor fields (ISBN, Pages, Language,
Publisher) that should never depend on the LLM.

**Initial hypothesis from user**: Is it the low-intelligence LLM model or the LLM
context length?

---

## 2. Investigation Findings (Root Cause: Context-Length Truncation)

The investigation doc (`docs/llm-extraction-zero-fields-investigation.md`) concluded
that the root cause is **context-length truncation**, not low model intelligence.

### 2.1 The Math

- `num_ctx=4096` (later updated to 8192) in `docker/Modelfile.airavata`
- `max_tokens=2048` reserved for output
- Only ~1100-1700 tokens left for OCR input
- Indic script tokenizes at 2-4 chars/token (not the assumed 4 chars/token)
- Result: Ollama silently truncates OCR text; model sees only the title page

### 2.2 Suspect Ranking

| # | Suspect | Verdict |
|---|---|---|
| 2 | Context length / truncation | **ROOT CAUSE** |
| 1 | Low-intelligence model | Contributing (7B Q4_K_M on CPU) |
| 4 | Response parsing | Secondary (silent exception handlers) |
| 5 | Field definitions / schema | Not the bug |
| 6 | Data flow / storage | Correct flow, misleading UI |
| 3 | Prompt engineering | Contributing (zero few-shot examples) |

### 2.3 Recommended Fix Priority

1. Lower `max_tokens` from 2048 to 512
2. Raise `num_ctx` to 8192 (already done)
3. Fix corrupted `stop` tokens in Modelfile
4. Tighten `MAX_OCR_CHARS` from 8000 to ~2500
5. Surface "empty_response" status when LLM returns nothing
6. Add few-shot examples to prompts
7. Log per-tier resolution in hybrid.py

---

## 3. Per-Page Brute-Force Extraction Proposal (Rejected)

**User's idea**: For each page, run one LLM call extracting all user-selected fields
from that page alone. Repeat for all pages. On conflict, present options to user.

### 3.1 Merits

- Solves truncation correctly (per-page text fits in context)
- Field-by-page relevance is real (title page has title, colophon has ISBN)
- Conflicts become a feature

### 3.2 Six Failure Modes

1. **"Single page has nothing relevant" problem** — 280 pages × 40 fields = 11,200
   wasted LLM calls, 11,200 noisy "guess conflicts"
2. **OCR page boundaries ≠ semantic boundaries** — title wraps, ISBN splits, foreword
   spans pages
3. **Page-aware batching already exists** in `batch_routing.py:31-48` — the proposal
   removes it
4. **Conflict-resolution UX is unsolved** — 14,000 candidate values, 99% null
5. **Confidence becomes meaningless** — per-page confidences vary wildly for the same
   field
6. **Latency and cost explode** — 280 LLM calls vs 8, ~2.3 hours vs 4 minutes per book

### 3.3 Better Synthesis

Combine per-page granularity with what's already there:
- Field-aware page selection (already in `BATCH_PAGE_SLICES`)
- Per-field calls, not per-page calls
- True conflicts only (heuristics: plausible sources, non-null values)
- Pre-filter obvious cases with per-page regex
- Confidence-weighted aggregation

### 3.4 Actual Critical Issues to Fix First

1. `num_ctx` too small (raise to 8192)
2. `max_tokens` wastefully high (drop to 512)
3. Corrupted `stop` tokens
4. `MAX_OCR_CHARS` too large
5. Silent failure path
6. Zero few-shot examples

---

## 4. Implementation of Fixes

The user approved applying all 7 fixes from the investigation doc.

### 4.1 Sample Book Locations

- **Hindi books**: `backend/tests/fixtures/samples/hin/commons/`
- **Telugu books**: `backend/tests/fixtures/samples/tel/commons/`

### 4.2 Changes Applied

| # | Fix | File | Change |
|---|---|---|---|
| 1 | Modelfile | `docker/Modelfile.airavata` | Removed corrupted `stop` tokens; confirmed `num_ctx 8192` |
| 2 | max_tokens | `backend/app/tasks/llm_tasks.py:277` + `backend/app/schemas/metadata.py:297` | 2048 → **512** |
| 3 | OCR budget | `backend/app/services/llm_service.py:58` | `MAX_OCR_CHARS` 8000 → **2500** |
| 4 | Empty-response surfacing | `backend/app/services/llm_service.py` + `backend/app/tasks/llm_tasks.py:196-229` | New `empty_response` status when LLM succeeds but every field is None |
| 5 | Few-shot examples | `backend/app/services/prompts.py` | Added `FEW_SHOT_EXAMPLES` dict for tel/hin/eng |
| 6 | Per-tier logging | `backend/app/services/extractors/hybrid.py` | Logs tier1/tier2/tier3 resolution counts |
| 7 | Test default | `backend/tests/unit/test_metadata_schema.py:72` | Updated `max_tokens` default assertion to 512 |

### 4.3 Note on Modelfile

The file already had `num_ctx 8192` set — the investigation doc said 4096 but the
actual file was already at 8192. The `stop` tokens were corrupted and are now removed.

### 4.4 Test Results

All 152 unit tests pass after the changes. One test (`test_metadata_schema.py:72`)
required updating the `max_tokens` default assertion from 2048 to 512.

---

## 5. First Results After Fixes

After deploying the fixes, the LLM Run History showed:

- **title** extracted: "Ganga Divergence"
- **author** extracted: "Taruant India Union" (transliteration mishap)
- **publisher** extracted: "Taruण India Union" (mixed Devanagari + Latin)
- 5 other batches still returned 0

### 5.1 Observations

1. **OCR quality is the real bottleneck** — garbled "Taruण" / "Taruant" indicates OCR
   output is partially corrupted
2. **5/8 batches are still 0** — likely OCR bad on those pages or 2500 char cap cutting
   into ISBN block
3. **"Taruant India Union" artifact** — Airavata 7B on 4-bit quant confabulates when
   input script is degraded

### 5.2 Next Diagnostic Steps Suggested

- Inspect raw responses of empty batches in DB
- Check OCR text length per page
- Watch for job `error_log` surfacing empty batches

---

## 6. Future Strategy Discussion

Two ideas were proposed and critiqued:

### 6.1 Idea 1: Per-Page Type Classification + Targeted Prompts

Classify each page (cover/title/copyright/colophon/foreword/dedication/content), then
run different prompts per page type.

**Merits**:
- Solves "context diluted by irrelevant text" problem
- Lower token usage per call
- Higher accuracy per field type
- Plays well with existing `BATCH_PAGE_SLICES`

**Stress Test Failures**:
1. Page classification itself is an LLM call (or a small CNN/heuristic)
2. Page types are not mutually exclusive (copyright often contains dedication + ISBN)
3. Short books have one page doing five jobs
4. Same field can come from different page types
5. Re-introduces scaling problem (280 pages × N prompts)
6. The sample proves the real problem is the LLM, not routing

### 6.2 Idea 2: Web Search Augmentation

Once you have title or cover image, search Google Books / Open Library / WorldCat /
publisher catalogs for canonical metadata, then merge.

**Merits**:
- Solves OCR-degraded-text problem for books in catalogs
- Wikidata reconciliation becomes trivial
- Author disambiguation works
- Edition metadata is free
- Confirms OCR is correct

**Stress Test Failures**:
1. Not every book is in any catalog (especially regional-language pamphlets)
2. Web search is async, rate-limited, unreliable
3. Match scoring is hard (ISBN often absent, fuzzy match is non-trivial)
4. Copyright / legal issues for institutional users
5. Catalog data is often wrong or stale
6. Book's truth is on its pages, not the internet (edition vs copy)
7. Trust signal flips (user must verify, not correct)
8. "Taruant" output shows web search can't fix bad OCR on the source

### 6.3 Recommended Three-Tier Strategy

**Tier 1 (now)**: Make existing pipeline reliable — config fixes, few-shot examples,
empty-response surfacing.

**Tier 2 (next)**: Add per-page-type classification, but light — use cheap regex
heuristics:
- Has-ISBN regex check per page → routes ISBN batch
- Has-Copyright-header heuristic → routes publication batch
- Last-page heuristic → routes colophon/printer batch

These are 10-line regex/heuristic checks, no LLM call. Replace `BATCH_PAGE_SLICES`
with content-based routing.

**Tier 3 (after Tier 2)**: Web search for catalog reconciliation, but only as
cross-check, not primary source. Never silently overwrite extracted-from-book with
catalog.

### 6.4 What to Skip

- Full per-page-type LLM classification
- Web search as primary extraction source
- Image-based book-cover search

### 6.5 The Real Question

The "Taruant India Union" output suggests the actual problem is **OCR quality on
Hindi Devanagari text**, not extraction strategy.

---

## 7. OCR Correction Model Recommendation

The user asked which LLM model to use for OCR correction (Tesseract output → corrected
text → extraction).

### 7.1 Model Criteria

- Indic-script fluency
- Low hallucination
- Speed (called per-page, not per-book)
- Small footprint
- JSON or diff output

### 7.2 Tier 1: Best Fit — Airavata Itself, Different Prompt

**Don't add a new model. Reuse Airavata with a denoising prompt.**

Pros: zero new infra, same Ollama endpoint, same circuit breaker.
Cons: Airavata 7B Q4_K_M is weakest for this — but try first.

### 7.3 Tier 2: Better Small Indic Model

- `surya-ocr` — purpose-built, but vision model (skip)
- `Ai4Bharat/indic-llama` — Indic-specific 7B
- `Telugu-LLM-Labs/Telugu-Llama2-7B` — Indic-specific 7B
- `Hemanth-thunder/Indic-T5-XXL` — T5 encoder-decoder, fast, good for denoising

T5 models are 3-4x faster than 7B decoders, better at transformation tasks, smaller,
less likely to hallucinate.

### 7.4 Tier 3: Pre-LLM Deterministic Fixers

1. Tesseract dictionary mode (`--oem 0` + custom word list) — free, 30 min
2. Tesseract LSTM retraining / language pack update — free, 10 min
3. Re-OCR with better PSM (1 for title, 4 for copyright) — free
4. Image preprocessing (binarization, deskew, DPI bump to 400) — free

### 7.5 Tier 4: Cloud OCR Fallback

- Google Cloud Vision API (best for Hindi, ~$1.50/1000 pages)
- Azure Vision (good Indic support)
- AI4Bharat `indic-ocr` (free for research)

Per-page fallback, not replacement.

### 7.6 A/B Test Order

1. Update Tesseract lang packs + user-words file + DPI bump → measure CER
2. If CER > 8%: Add LLM correction using Airavata with denoising prompt
3. If Airavata correction makes it worse: Switch to Indic-T5 (~4 GB, 2x faster)
4. For remaining 5-10% hard pages: Add cloud-OCR fallback flag per book

### 7.7 Why Reject Other Suggestions

- **Larger model (Llama-3 70B)**: overkill, 40 GB, 10x slower, 2+ hours per book
- **Fine-tune Airavata**: needs labeled dataset you don't have
- **Vision LLM (Qwen-VL, LLaVA)**: major architecture change, not now
- **EasyOCR/PaddleOCR**: 1-week migration, not a quick win

### 7.8 Honest Answer

**Use Airavata itself for OCR correction first.** Correction is much easier than
extraction. A model that can't write JSON can denoise "Taruant" → "तरुण".

If that doesn't work, T5-size models (1-3B) are the right next step.

Don't reach for bigger models. Don't reach for cloud APIs yet. The win is in:
1. Better Tesseract config (lang packs, user-words, DPI)
2. Same-model LLM correction with denoising prompt
3. Content-based routing (Tier 2 from earlier)

---

## 8. Implementation Note

The OCR correction step would be ~50 lines: a new `correct_ocr_text()` function in
`ocr_service.py`, called between Tesseract and storage, with a `corrected_text` field
added to the `OcrResult` model.

# LLM Extraction — Zero-Fields Investigation

**Symptom**: LLM extraction jobs complete "successfully" but extract **0 fields** from book
content. The UI shows "View extracted fields (0)" for every run and all fields display
"Not extracted", including the cheap-extractor fields (ISBN, Pages, Language, Publisher)
that should never depend on the LLM.

**Verdict**: Root cause is **context-length truncation**, not low model intelligence.
The LLM is silently receiving a truncated slice of the OCR text and producing empty /
all-null JSON. A small quantized model with zero few-shot examples compounds the problem.

---

## 1. End-to-End Data Flow

```
PDF upload
  -> POST /api/books/upload (api/books.py)
  -> process_book_pipeline (tasks/pipeline_tasks.py:394)
       -> OCR (tasks/ocr_tasks.py)  -> Book.status = OCR_COMPLETE
       -> run_llm_extraction.delay() (Celery)
            -> _validate_book_context (llm_tasks.py:28)
            -> llm.run_hybrid_full_extraction
                 -> run_hybrid_extraction (services/extractors/hybrid.py:25)
                      Tier 1: regex   -> isbn, publication_date, pages
                      Tier 2: dict    -> publisher, language
                      Tier 3: LLM     -> _llm_fill (llm_service.py:343)
                          -> 8 parallel batches
                          -> each batch: extract_batch -> pydantic schema
                          -> filter to gap_fields ∩ non-None
            -> _persist_extraction_results (llm_tasks.py:113)
                 -> BookMetadata.fields (merged)
                 -> MetadataFieldEvidence rows
                 -> one LlmRun per batch with parsed_fields=parsed_filtered

Frontend
  GET /api/books/{id}/metadata           -> fields[]
  GET /api/books/{id}/metadata/evidence  -> confidenceByField{}
  GET /api/books/{id}/llm-runs           -> runs[].parsed_fields
```

---

## 2. Key Files

| File | Role |
|---|---|
| `backend/app/services/llm_service.py` | `LLMService` — extraction, hybrid orchestration, circuit breaker |
| `backend/app/services/prompts.py` | `SYSTEM_PROMPT_TEMPLATE`, `EXTRACTION_PROMPT_TEMPLATE` |
| `backend/app/services/batch_routing.py` | `BATCH_PAGE_SLICES`, `assemble_ocr_text` |
| `backend/app/services/extractors/hybrid.py` | Regex -> dictionary -> LLM orchestration |
| `backend/app/services/extractors/regex_extractors.py` | isbn, publication_date, pages, price |
| `backend/app/services/extractors/dictionary_extractors.py` | publisher, language |
| `backend/app/schemas/metadata.py` | `METADATA_BATCHES` (8 pydantic schemas), `BATCH_FIELD_ORDER`, `FIELD_TO_BATCH` |
| `backend/app/tasks/llm_tasks.py` | Celery task `run_llm_extraction` |
| `docker/Modelfile.airavata` | Ollama Modelfile with `num_ctx 4096` |

---

## 3. Model Configuration

| Setting | Value | Source |
|---|---|---|
| Default model | `airavata` (custom Ollama tag) | `llm_service.py:94,177,301` |
| Base | `hf.co/mradermacher/Airavata-GGUF:Q4_K_M` | `docker/Modelfile.airavata:1` |
| Size | ~4.1 GB | docs |
| Quantization | Q4_K_M (4-bit) | Modelfile |
| **`num_ctx`** | **4096 tokens** | `docker/Modelfile.airavata:4` |
| `temperature` | 0.3 | `docker/Modelfile.airavata:3` |
| `stop` tokens | `" candidaterespons\n"`, `"nassistant\n"` — **corrupted** | `docker/Modelfile.airavata:5–8` |

---

## 4. Root Cause: Context-Length Truncation

### 4.1 The math (why this fails for Indic script)

`backend/app/services/llm_service.py:51–56`:
```python
# Reserve tokens for: system prompt (~200), extraction template (~400), output (~256).
# That leaves ~3240 tokens for OCR input. At ~4 chars/token that's ~12960 chars,
# but we use a conservative 8000-char cap ...
MAX_OCR_CHARS = 8000
```

**The "~4 chars/token" assumption is wrong for Indic script.** Modern BPE tokenizers
(llama-based, which Airavata GGUF uses) tokenize Telugu (U+0C00–U+0C7F) and Devanagari
(U+0900–U+097F) characters as **2–4 tokens per character** because they split by Unicode
code-point fragments.

| Content | Chars | Estimated tokens |
|---|---|---|
| English prose | 8000 | ~2000 |
| Telugu prose | 8000 | 16,000–32,000 |
| Mixed Indic + English | 8000 | 10,000–20,000 |

### 4.2 The budget

With `num_ctx=4096` and `max_tokens=2048` (the caller default from
`llm_tasks.py:277` / `schemas/metadata.py:297`):

```
Total budget:           4096 tokens
Output reservation:     2048 tokens
Remaining for input:    2048 tokens

Within input:
  System prompt:        ~150–400 tokens (instructor adds JSON-schema suffix)
  Extraction template:  ~200–500 tokens (field list + bullets)
  Available for OCR:    ~1100–1700 tokens
```

At 1 token/char for Indic script that's **~1100–1700 characters** of OCR text —
roughly the title page and a bit more. The colophon (ISBN, publisher, printer, place
of publication) is **never reached**.

### 4.3 Ollama's silent truncation

Ollama does **not** raise an error on context overflow. It feeds the truncated slice
to the model. Airavata 7B on that truncated slice, with no few-shot examples, returns:

- `{}` — empty object, or
- `{label: null, author: null, ...}` — every field null.

Either way, `instructor` parses "successfully" (all defaults are valid null). The hybrid
filter then drops every field (no non-None values), `parsed_fields = {}`, and the UI
correctly renders **"View extracted fields (0)"** because that label is literally
`Object.keys(LlmRun.parsed_fields).length`.

---

## 5. Why Cheap Extractors Are Also Missing

ISBN, Pages, Language, Publisher flow through **regex/dictionary** extractors that do
not depend on the LLM. Their results land in `BookMetadata.fields` via
`_persist_extraction_results` (`llm_tasks.py:113`).

If those four are also showing "Not extracted", the cheap extractors are either:

- **Not matching the OCR text** — `extract_isbn` requires an ISBN-digit pattern, which
  Tesseract on Indic scripts often garbles. `extract_pages` needs a pattern like
  "280 pp" or "280 pages". `extract_publisher` requires the publisher name to be in
  a ~30-entry whitelist.
- **Receiving empty text** — `_validate_book_context` falls back through
  `ocr.corrected_text or ocr.raw_text or ""`. If `corrected_text` is set but empty,
  the fallback is `""` and `_validate_book_context` rejects the book entirely.

Confirm by inspecting the database:
```sql
SELECT field_name, value, confidence, source
FROM metadata_field_evidence
WHERE book_id = <id> AND field_name IN
  ('isbn', 'pages', 'publication_date', 'publisher', 'language');
```

If no rows exist, the cheap extractors ran but didn't match — likely OCR quality. If
rows exist with low-confidence values, those values did flow but were overwritten.

---

## 6. Why Failures Are Silent

### 6.1 Exception handlers swallow everything

`llm_service.py:149–169`:
```python
except InstructorRetryException:
    # fallback parse JSON from last_completion ...
    return _fallback_parse(raw_response, batch_schema, ...)
except (TimeoutException, APITimeoutError):
    return _empty_batch(batch_schema)          # all None
except Exception:
    return _empty_batch(batch_schema)          # all None
```

`_empty_batch` (`llm_service.py:558`) returns a pydantic instance with every field
None. The caller cannot distinguish "LLM errored" from "LLM returned nothing".

### 6.2 Hybrid filter erases all-null responses

`llm_service.py:468–470`:
```python
parsed_all = result.model_dump(exclude_none=False)
parsed_filtered = {k: v for k, v in parsed_all.items()
                   if k in gap_fields and v is not None}
return batch_name, parsed_filtered, raw_response, usage
```

When `parsed_all` is a dict of N `None`s, `parsed_filtered` is `{}`. This dict is
written to `LlmRun.parsed_fields` (`llm_tasks.py:185`). The job is marked COMPLETED
because `_persist_extraction_results` only marks FAILED if
`status not in ("success", "fallback")` — both `success` (all-null) and `fallback`
(count as success.

### 6.3 The "View extracted fields (0)" UI

`frontend/src/app/books/[bookId]/metadata-review/page.tsx:294–295`:
```tsx
View extracted fields (
  {Object.keys(run.parsed_fields).length})
```

This is a literal readout of the storage. It is **technically correct** but
**misleading** — the LLM call may have succeeded at the network level while producing
nothing useful.

---

## 7. Why "Not extracted" Shows for Every Field

`frontend/src/components/metadata/metadata-form.tsx:255–257`:
```tsx
placeholder={
  confidence === "empty" ? "Not extracted" : ""
}
```

`confidence` comes from `getFieldConfidence()` (lines 49–69), which returns `"empty"`
when `BookMetadata.fields[field_name]` is missing or empty. There is no distinction
in the UI between "regex couldn't find it", "LLM returned null", and "LLM errored".

---

## 8. Suspect Ranking

| # | Suspect | Verdict |
|---|---|---|
| 2 | **Context length / truncation** | **ROOT CAUSE.** 8000 chars × Indic tokens × 2048-token output reservation + 4096 num_ctx = the model sees ~1100–1700 chars of OCR text and never reaches the colophon. |
| 1 | Low-intelligence model | **CONTRIBUTING.** 7B Q4_K_M on CPU with zero few-shot examples. Alone it would give wrong fields, not zero. |
| 4 | Response parsing | **SECONDARY.** Silent exception handlers + `_fallback_parse` hide failures. |
| 5 | Field definitions / schema | **NOT THE BUG.** Pydantic schemas are correct and complete. |
| 6 | Data flow / storage | **CORRECT FLOW, MISLEADING UI.** `LlmRun.parsed_fields` is honestly empty; the issue is upstream. |
| 3 | Prompt engineering | **CONTRIBUTING.** No few-shot examples, no per-language variant. Flagged as open high-ROI improvement in `docs/known-limitations.md:121–123`. |

---

## 9. Diagnostic Steps

### 9.1 Confirm truncation in the database

```sql
SELECT id,
       batch_config,
       raw_response IS NOT NULL    AS has_raw,
       length(raw_response)         AS raw_len,
       parsed_fields,
       jsonb_object_keys(parsed_fields) AS keys
FROM llm_runs
ORDER BY created_at DESC
LIMIT 8;
```

- **`raw_response` non-null but `parsed_fields = {}`** → model produced output, hybrid filter dropped everything.
- **`raw_response = '{}'` or empty** → model itself produced nothing.
- **`raw_response` is an error string** → the LLM call failed silently.

### 9.2 Confirm the actual context window Ollama is using

```bash
curl -X POST http://localhost:11434/api/show \
  -d '{"name":"airavata"}' | jq .
```

Look for `num_ctx` in the response — confirms whether 4096 or another value is in effect.

### 9.3 Confirm token usage per call

`extract_batch` returns `usage_stats` (`llm_service.py:139`). Log
`usage_stats["total_tokens"]` per batch — if it caps at 4096 while input is much
larger, truncation is confirmed.

### 9.4 Run the manual test with verbose output

```bash
cd backend && python scripts/test_llm_extraction.py --model airavata --telugu
```

---

## 10. Recommended Fixes (priority order)

### P0 — Single-line config fix (immediate effect, no model change)

**Lower `max_tokens` from 2048 to 512** in `llm_tasks.py:277` and
`schemas/metadata.py:297`. The JSON outputs are small (one field name per key); 512
tokens is more than enough. This frees ~1500 tokens of input budget immediately.

### P0 — Raise the context window

Edit `docker/Modelfile.airavata:4`:
```dockerfile
PARAMETER num_ctx 8192
```

Re-pull the model. This is a free improvement for a CPU-only quantized model.

### P1 — Tighten the OCR cap

Reduce `MAX_OCR_CHARS` from 8000 to ~2500 in `llm_service.py:56`. Smaller per-batch
input fits more reliably within the context window and forces the per-batch routing
to stay focused on the first few pages where the data actually lives.

### P1 — Replace the corrupted `stop` tokens

Edit `docker/Modelfile.airavata:5–8`. Either remove the `stop` parameters entirely or
use ``. The current values (`" candidaterespons\n"` with a leading space,
`"nassistant\n"` missing its newline) are inert at best and harmful at worst.

### P1 — Make silence visible

Add a `status` flag on `usage_stats` for "empty response" / "all-null". Currently
`_empty_batch()` returns all-None without raising, and `_persist_extraction_results`
(`llm_tasks.py:199`) marks FAILED only if `status not in ("success", "fallback")`.
Surface "8/8 batches returned empty" in the UI rather than marking the job COMPLETED.

### P2 — Add few-shot examples

`docs/known-limitations.md:121–123` flags this as the open high-ROI improvement.
Add 2–3 worked examples per high-confidence field (`title`, `subtitle`,
`place_of_publication`, `genre`, `dedication`, `volume`, `editor`) to
`prompts.py`. Airavata needs them badly for Indic script; the current prompt has
zero examples.

### P2 — Log per-tier resolution

Add a log line in `hybrid.py:53–67` showing which fields each tier resolved. Confirms
whether the regex/dictionary extractors are running and what confidence they achieved.

### P3 — Model upgrade (long-term)

Consider switching to a higher-quality model for production. Airavata 7B Q4_K_M on
CPU is at the low end of "can follow JSON schema" reliability. A non-quantized 7B or
a 13B model would substantially improve extraction accuracy. Flagged as open risk
in `docs/known-limitations.md:185`.

---

## 11. Summary

The "0 fields extracted" symptom is the downstream effect of three compounding
issues:

1. **Context-length truncation** (root cause) — `num_ctx=4096` with `max_tokens=2048`
   leaves only ~1100–1700 tokens for OCR input. For Indic script that is roughly
   the title page. Ollama silently truncates; the model returns `{}`; the hybrid
   filter drops it; the UI shows zero.

2. **Silent failure path** (amplifier) — exception handlers return all-None without
   raising; the job is marked COMPLETED; the UI has no signal that the LLM produced
   nothing useful.

3. **Small quantized model with no few-shot examples** (compounder) — even on a
   non-truncated input, Airavata 7B Q4_K_M struggles with the JSON schema without
   examples. Together with truncation, the result is zero fields instead of wrong
   fields.

Fix order: lower `max_tokens` → raise `num_ctx` → fix `stop` tokens → tighten OCR
cap → make silence visible → add few-shot examples → model upgrade.
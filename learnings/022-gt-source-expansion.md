# 022 — Ground-Truth Source Expansion: scale, catalogue depth, and the script fix

- **Date:** 2026-11-13
- **Study context:** [plans/011](../plans/011-ground-truth-source-expansion.md) — grow the GT corpus and enrich each book, beyond Commons/Wikisource, with IA allowed, Telugu/Hindi only, CC/PD only. Also records the [plans/009](../plans/009-metadata-page-selection.md) page-detector POC.
- **Status:** Scale and depth Phase-1 done; accuracy eval running.

## Summary

Corpus grew **49 → 71 books** (844 values) with **+22 CC/PD Telugu/Hindi** books, and **Latin-vs-script** was largely fixed (**author 26 → 11 Latin; title 11 → 8**, the rest genuine English titles). The two new catalogue adapters (`ia_dc`, `pustaka_nidhi`) turned out to add **nothing to this corpus** — Pustaka Nidhi matched 17 books but their titles were already Telugu script, and IA `dc.*` fields were already captured. The page-detector POC showed the **LLM text judge is ~5× more selective** than a fixed window, but its metric was invalid because labels were keyed on exact OCR strings.

## Findings

### 1. Scale (done)

`fetch_commons_ground_truth --cc-pd-only` added **+16 Hindi + 6 Telugu** books (40 MB cap). 71 books, all schema-conformant, 844 non-null values, 39/49 fields. The user's decision (IA allowed, CC/PD only, Telugu/Hindi) bounded the pool to Commons for this pass.

### 2. Catalogue depth adds little — and why

- **`pustaka_nidhi`** ([library.opentelugu.org](https://library.opentelugu.org/data/), CC BY 4.0): 42,828 records (36k books), 15,675 DLI ids. **17/49 books matched** by IA identifier — but their `title` was **already Telugu script** (set by the earlier Wikisource pass), so no change.
- **`ia_dc`**: parses `dc.publisher` / `dc.date.citation` / `totalpages` / `dc.subject.classification` out of the DLI description HTML → **0 new fields** (already captured).
- **The 22 new books matched 0**: they are Commons-only uploads with **no Internet Archive identifier**, so identifier-keyed catalogues cannot reach them. Catalogue-based depth only helps **DLI/IA-hosted** books.

### 3. Script fix works (OpenRouter free)

`fix_script.py` transliterates Latin `title`/`label`/`author` into the book's script with **`baidu/ernie-5.5-flash-preview:free`** (other free models were rate-limited or returned empty). Examples: *Rayasam Venkata Shivudu → రాయసం వెంకట శివుడు*, *Priya Pravas → प्रिय प्रवास*. Latin **author 26 → 11**, **title 11 → 8** on the original set, **+11 fields** on the new books. Remaining Latin titles are genuine English/resource titles (e.g. *A Collection of Telugu Proverbs*) — correctly untouched.

### 4. Page-detector POC (plans/009)

On 8 books: `fixed` 8 pages · `heuristic` 10.5–14 · `llm_text` 1.5. The **heuristic barely fires on noisy OCR** (short pages never trip `is_body_page`) and keeps *more* than fixed — useless. The **`llm_text` judge is ~5× more selective**. The metric was invalid (exact-string silver labels blanked by OCR error → silver=0); a fuzzy labeller was added but not re-run.

### 5. Verification semantics kept honest

New values are `prefilled_needs_verification` with `field_source` provenance; the harness excludes `node_llm_extraction` fields from gold scoring (`evaluate_extraction.ignored_fields`). "verified" throughout means **source-verified**, not human-verified.

### 6. The evaluation harness cannot score thinking models (`think:false` ignored)

`evaluate_extraction` runs the model through `LLMService` (the **OpenAI-compatible** client), the same path where `think:false` is dropped. With `gemma4:e4b` every batch returned **empty `content`** (all budget on the `reasoning` channel, `finish_reason=length`) → the eval scored empty predictions. **Consequences:** evaluate **non-thinking models** with the harness as written (`phi4-mini`, `qwen2.5`), or route thinking models via the native `/api/chat` endpoint. This is the practical corollary of the finding in [019](019-gt-corpus-enrichment.md).

### 7. Enriched-corpus accuracy: `gemma4` (native) beats `phi4-mini` on Hindi

Re-ran the harness against the enriched corpus (field-aware: model-prefilled fields excluded), 4 Hindi books, `test-node-1`:

| Model | Micro P | Micro R | Micro F1 |
|---|---|---|---|
| `phi4-mini` (OpenAI path) | 0.448 | 0.361 | 0.400 |
| `gemma4:e4b` (`--native`, `think:false`) | 0.615 | 0.667 | **0.640** |

`gemma4` per-field: `subject` 1.00, `language` 1.00, `description_work`/`original_language`/`title` 0.86, `pages` 0.80, `author`/`publication_date` 0.67. **This is the first valid gemma4 Hindi number** — every earlier gemma4 run scored 0 via the think trap, so the prior "phi4-mini wins Hindi" conclusion was a bug artifact. Reports: `backend/reports/gt-eval-{phi4,gemma4-native}-enriched.json`.

## Recommendation / next steps

1. **Depth for Commons-only books** must come from OCR/LLM (the scans), not catalogues — or curate books from DLI/IA hosts so catalogues apply.
2. **Phase 2 (DLI Catalogue)** — the only catalogue with real `publisher`/`year`/`pages`; worth a PoC on DLI-hosted books.
3. **Re-run the page POC** with the fuzzy labeller to get valid `llm_text` recall before any MVP; do not adopt the heuristic.
4. **Human-verify** the review queue (`reports/gt-review-queue.csv`) to promote books from prefill to gold.
5. Accuracy eval numbers to be appended when `test-node-1` finishes.

## References

- Scripts: [`enrich_catalogues.py`](../backend/scripts/enrich_catalogues.py) · [`fix_script.py`](../backend/scripts/fix_script.py) · [`page_selection.py`](../backend/app/services/page_selection.py) · [`poc_page_detector.py`](../backend/scripts/poc_page_detector.py)
- Plans: [011](../plans/011-ground-truth-source-expansion.md) · [009](../plans/009-metadata-page-selection.md)
- Prior: [019](019-gt-corpus-enrichment.md) · [001](001-ground-truth-dataset-feasibility.md)
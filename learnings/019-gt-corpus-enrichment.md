# 019 — Enriching the Ground-Truth Corpus: more Hindi books, deeper catalog reads, and a node OCR+LLM fill

- **Date:** 2026-11-13
- **Study context:** the GT corpus was sparse — 308 of 1715 fields filled (18%), 12 of 49 fields ever populated — and Telugu-heavy (30 books, 5 Hindi). The user asked for more Hindi books and for the empty fields to be filled.
- **Status:** A (Hindi books) and B (catalog enrichment) done and committed (`7a95ac3`); C (node OCR+LLM fill) run over the whole corpus and merged. All numbers below are measured on the corpus at HEAD.

## Summary

The empty fields were **mostly not missing from our extraction — they are missing from the catalog sources**. For these Digital Library of India scans, Commons carries no Wikidata item and exposes only title/author/date/license; Internet Archive adds subject/publisher/pages. Fields like `printer`, `place_of_printing`, `edition_number`, `series`, `dedication` live **only in the book's own title/copyright/colophon pages**, so they can only be recovered by reading the scan. Result after three passes: **424 non-null fields across 49 books, 37 of 49 fields populated** (from 308 / 12).

## Key findings

### A. More Hindi books (`7a95ac3`)

`fetch_commons_ground_truth.py` had no license filter, so it could pull non-redistributable files. Added an opt-in `--cc-pd-only` gate (`_is_cc_pd`: PD / CC0 / CC-BY* only, rejecting NC/ND/non-free). With it, pulled **14 new CC/PD Hindi PDFs** from `Category:Hindi-language books` (246 PDFs matched; the 60 MB size cap skipped several large scans). Corpus is now **30 Telugu + 19 Hindi**.

### B. Deeper catalog enrichment (`7a95ac3`)

`enrich_ground_truth.py` now reads three more things: **Commons categories** → `genre`/`language` (curated `GENRE_HINTS`), **Internet Archive** `subject`/`publisher`/`imagecount`, and an extended **Wikisource label map** (added `ISBN`, `భాష`→language, the `ఆధారం` variant of `ఆధారము`, and a full Hindi set). Catalog-verified coverage rose **308 → 424** non-null fields; `subject` (20), `genre` (10), `publisher` (24) and `pages` (19) now populate.

### C. Node OCR+LLM fill of the scan-embedded fields

`backend/scripts/node_gt_fill.py` renders each book's front (6) and back (2) pages, OCRs them with the real pipeline, and runs one LLM extraction pass. Results merge into the scaffolds via `backend/scripts/merge_node_fill.py`.

**The load-bearing finding — the think flag does not survive the instructor path.** `LLMService.extract_batch` passes `extra_body={"think": False}` for thinking models, but on this deployment Ollama's **OpenAI-compatible** endpoint ignores it: `gemma4:e4b` spent its entire output budget on a `reasoning` channel and returned **empty `content`** (`finish_reason=length`), so every batch came back empty. The **native `/api/chat`** endpoint with `"think": false` honours the flag (verified: returns JSON, `thinking=None`, and correctly read `printer=ఆంధ్ర పత్రికా ముద్రాలయం`, `place_of_printing=మద్రాసు`). The runner therefore calls `/api/chat` directly. This supersedes the assumption in [005](005-llm-model-evaluation.md)/[018](018-llm-config-validation.md) that `think:false` via the OpenAI endpoint was sufficient.

**Cost drove the design.** The production 8-batch hybrid is ~19 min/book on 4 vCPU (`OLLAMA_NUM_PARALLEL=1` serialises the batches; gemma4 emits ~500+ tokens/batch at ~5 tok/s). A **single focused call** asking only for the ~38 fields catalogs rarely carry is ~8× cheaper. Whole run: **49 books in ≈2 h** (~160 s/book, OCR-dominated).

**Measured result (merged):**

| | before | after A+B | after C |
|---|---|---|---|
| non-null fields (all books) | 308 | 424 | **623** |
| distinct fields ever populated | 12 | 15 | **37 / 49** |
| books | 35 | 49 | 49 |

Newly populated by C (book counts): `subject` 35, `place_of_printing` 29, `printer` 26, `genre` 23, `inception` 19, `subtitle` 15, `edition_number` 8, `publisher_telugu` 8, `distributors` 5, `dedication` 4, `part_of_series` 4, `volume` 3, `compiler`/`editor`/`translator` 2 each, `based_on`/`forewords`/`isbn` 1–2. Spot-checks are correct where OCR is readable (e.g. Sadhu-Aur: `printer=लीडर प्रेस`, `place_of_printing=इलाहाबाद`, `edition_number=प्रथम संस्करण`, `subtitle`/`genre` read from the title page).

**12 fields remain empty** — `cover_artist`, `cover_page_designer`, `book_designer`, `typing_by`, `scribes`, `dedication_verbatim`, `abbreviations`, `opinions_messages`, `illustrators`, `inspired_by`, `part_of_the_set`, `first_published_in` — these are genuinely rare and usually absent from the fetched pages.

### Quality caveats (measured)

- Model output is **prefill, not truth**. `merge_node_fill.py` applies a plausibility filter (rejects fake ISBNs like `99999990069634`, year-shaped junk like `943`, and Latin/Devanagari text in `publisher_telugu`) and drops echo values; **199 of ~230 raw fills survived**.
- OCR is the ceiling (Telugu CER ≈ 0.45, [004](004-ocr-stage-cer.md)); books with unreadable front matter yield 0 fields (e.g. `1913_Ummed_Singh_Charitra` filled=0), books with clean title pages yield 10–12.
- **Status semantics:** merging sets each touched book to `verification_status=prefilled_llm_unverified` (per-field `field_source=node_llm_extraction`, `field_status=prefilled_needs_verification`), deliberately so the model is never scored against its own output. **The harness now handles this per-field** (see below): prefilled books are still scored, but only on their verified core. **8 books remain fully source-verified.**

## Recommendation / next steps

1. **Owner (user):** decide the verification depth — human-review the 199 prefilled values (or accept them as provisional prefill and leave the books out of the scored set).
2. **Harness (done):** `evaluate_extraction` is now field-aware — `prefilled_llm_unverified` books are scored by default (added to `SCOREABLE_STATUSES`), and `ignored_fields()` excludes any field whose `field_source == "node_llm_extraction"` from TP/FP/FN. Keyed on `field_source` (not `field_status`, which enrichment also sets for catalog prefill — using that wrongly ignored verified fields). Covered by unit tests in `test_extraction_validator.py` and `test_ground_truth_discovery.py`.
3. **Re-run with a larger page window** (front 10 / back 4) on books that yielded 0, if the extra OCR cost is acceptable, to catch title pages deeper than page 6.
4. **Legacy `think` note:** any future pipeline call must use the native endpoint (or verify the OpenAI path forwards `think` for the installed Ollama) — this was a silent empty-output failure.
5. **Node hygiene:** `test-node-1` was left running for this task; stop it (`gcloud compute instances stop test-node-1 --zone=asia-south1-c`) when the spend guardrail applies.

## References

- Scripts: [`node_gt_fill.py`](../backend/scripts/node_gt_fill.py) · [`merge_node_fill.py`](../backend/scripts/merge_node_fill.py) · [`node_fetch_pdfs.py`](../backend/scripts/node_fetch_pdfs.py) · [`enrich_ground_truth.py`](../backend/scripts/enrich_ground_truth.py) · [`fetch_commons_ground_truth.py`](../backend/scripts/fetch_commons_ground_truth.py) · [`build_manifest.py`](../backend/scripts/build_manifest.py)
- Corpus: [`backend/tests/fixtures/ground_truth/`](../backend/tests/fixtures/ground_truth) (manifest + frozen split `splits/gt-split-v1.0.json`)
- Node tracker: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
- Related: [001](001-ground-truth-dataset-feasibility.md) · [004](004-ocr-stage-cer.md) · [005](005-llm-model-evaluation.md) · [018](018-llm-config-validation.md)

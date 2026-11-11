# 003 — Harness Wiring + Scaling GT from Wikisource Index Pages

- **Date:** 2026-11-11
- **Context:** Continuing [learnings/002](002-gt-enrichment-sources.md) / [plans/002](../plans/002-ground-truth-poc.md) — "do both": (a) scale Telugu from `te.wikisource` Index pages (metadata + OCR ground truth), and (b) wire the harness to score the per-book GT corpus.
- **Artifacts:** [backend/scripts/fetch_from_wikisource.py](../backend/scripts/fetch_from_wikisource.py) (new), [backend/scripts/evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) (`--ground-truth` mode), `backend/scripts/fetch_wikisource_gt.py` (wiki-inference fix), `backend/tests/fixtures/ground_truth/`.

## Summary

Seeded **+5 Telugu books directly from `te.wikisource` proofread Index pages** (metadata from the Index header + Commons), bringing the corpus to **19 books (14 Telugu, 5 Hindi)**; combined with the earlier fetch, **14 books now carry page-level OCR ground truth** (`wikisource_gt.json`). The harness gained a `--ground-truth` mode that discovers the per-book corpus and reuses `extraction_validator` unchanged; a `--stub` run scored all 19 books end-to-end. **Real accuracy scoring still needs Ollama + Postgres** (neither running here), so the run validates wiring, not pipeline quality.

## Key findings

- **Wikisource Index pages are a first-class seed source.** `fetch_from_wikisource.py` enumerates `Index:` pages, maps each to its `File:<stem>.pdf` on Commons, downloads the PDF, and prefills all 49 fields from the Index header (`te.wikisource` labels via `parse_index_header`) plus Commons metadata. 5/5 seeded books wrote cleanly (incl. one CC BY-SA modern title, *1857 ముస్లింలు*).
- **OCR ground truth is cheap to add once the PDF exists.** Reusing `fetch_wikisource_gt.py` produced `wikisource_gt.json` for **14 Telugu books** — it SHA1-verifies the local PDF matches Commons before aligning `Page:` records, and only keeps proofread level 3/4 text. Coverage examples: *Abalaa sachcharitra ratnamaala* 275/286 verified pages; *A Collection of Telugu Proverbs* 213 verified (396/661 pages have records); *1857 ముస్లింలు* 305/305.
- **The harness now scores the real corpus.** `discover_ground_truth(root, only_verified=True)` walks `ground_truth/{lang}/{slug}/` (one dir per book); `--ground-truth [DIR]` switches the harness to it, `--include-unverified` includes scaffold-only books. Scoring reuses `extraction_validator.evaluate_book` (presence/absence + exact/normalized/token-F1 + script-match) with no changes.
- **GT field support across the 19-book corpus** (non-null per field): author 19, description_work 19, original_language 19, language 19, title 18, label 18, publication_date 17, form_of_creative_work 10, publisher 7, pages 7, place_of_publication 6, editor 1 — the rest genuinely absent for pre-ISBN-era books.
- **`--stub` is a wiring check, not accuracy.** `run_pipeline_on_pdf` needs DB + Ollama; with `--stub` the report prints overall F1 = 1.0 by construction. Real numbers require the pipeline services.
- **Gotchas:** a Commons filename starting with `.` yields a hidden slug skipped by shell globs (use pathlib); and a Wikisource-seeded book's `source_category` of `Index:<wiki>` broke `fetch_wikisource_gt`'s wiki inference — now fixed by recording `provenance.wiki`.

## Recommendation

- **Promote the Wikisource toggle to the primary Telugu seeder** — it targets books that *have* proofread indexes (so metadata **and** OCR GT come together), unlike Commons category order.
- **Run the real (non-stub) evaluation the moment Ollama + Postgres are up**, on `--verified-only` once the fields are human-checked.
- Keep `null` fields as correct GT; score presence/absence, not just value match.

## Next steps

1. Human-verify the prefilled fields (fastest check: the `wikisource_gt.json` title/copyright pages).
2. Stand up Ollama + Postgres and run `uv run python -m scripts.evaluate_extraction --ground-truth --verified-only` for the first *real* accuracy report.
3. Continue scaling Telugu from `te.wikisource` (`--limit N`); add `hi.wikisource` only if it gains a ProofreadPage Index namespace.

## Update (Round 3) — scaled further

- Seeded **+8 Telugu** books from `te.wikisource` Index pages → corpus **27 books** (22 have an Index page; **14 have verified OCR text**).
- **Finding:** Wikisource Index pages are not all proofread. The 8 new ones have `Page:` records at level 0/1 (not proofread), so they contribute **metadata but no OCR ground truth** — filter candidates by proofread level 3/4 to pick OCR-GT books.
- Harness re-run (stub) over 27 books — per-field GT support: author/language/original_language **27**, label/title **26**, description_work **25**, publication_date **25**, form_of_creative_work **18**, publisher **12**, place_of_publication **11**, pages **9**, editor **2**.

## Round 4 — harness runner repaired

`evaluate_extraction.run_pipeline_on_pdf` referenced **non-existent APIs** — `PDFService` and `StorageService` are modules of functions, not classes, and `render_pages` does not exist — so the import always failed, the function silently returned the `pipeline_unavailable` stub, and the pipeline had **never** actually run in the harness. Rewrote it against the real APIs (`pdf_service.render_full_page` / `get_page_count`, `ocr_service.run_ocr`, `LLMService.run_hybrid_full_extraction`) with **no DB dependency** (the hybrid extractor takes per-page text). Stub run still passes and the file is lint-clean; a real end-to-end run now needs only Ollama.

## References

- Seeder: [fetch_from_wikisource.py](../backend/scripts/fetch_from_wikisource.py) · OCR GT: [fetch_wikisource_gt.py](../backend/scripts/fetch_wikisource_gt.py) · Harness: [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py)
- Corpus: `backend/tests/fixtures/ground_truth/` (19 books, 14 with `wikisource_gt.json`)
- Report (stub): `/tmp/gt-report.json`
- Prior: [learnings/002](002-gt-enrichment-sources.md) · [learnings/001](001-ground-truth-dataset-feasibility.md) · [plans/002](../plans/002-ground-truth-poc.md)
# 002 — PoC Plan: Ground-Truth Dataset from Wikimedia Commons (Telugu + Hindi)

- **Date:** 2026-11-10
- **Status:** Plan → awaiting approval to implement
- **Depends on:** [learnings/001-ground-truth-dataset-feasibility.md](../learnings/001-ground-truth-dataset-feasibility.md) (feasibility complete)
- **Constraint:** Public **CC/PD-only**, publicly redistributable PDFs.

## Objective

Prove we can build a reliable, schema-aligned ground-truth (GT) dataset by pairing **real Telugu/Hindi book PDFs** from Wikimedia Commons with **human-verified metadata** for all **49** fields, and score the existing pipeline against it with the **existing harness**. Deliver a repeatable fetch→prefill→verify→score loop, not a one-off.

## Scope

**In scope (PoC):**
- A small fetch/annotate script ([backend/scripts/fetch_commons_ground_truth.py](../backend/scripts/fetch_commons_ground_truth.py)) that enumerates the two Commons categories, pulls per-file license + catalog metadata + Wikisource links, optionally downloads PDFs, and writes a **per-book GT scaffold** (all 49 fields, prefilled where authoritative data exists, every field flagged `needs_verification`).
- A GT fixture layout consumable by the harness, seeded with **~10 Telugu + ~5 Hindi** books (the 5 local Telugu scans are already on disk and confirmed CC/PD).
- A **minimal harness extension** to discover per-book GT (multiple books per language) and reuse `extraction_validator` unchanged.
- One end-to-end scored run + a short results learning (`learnings/003-…`).

**Out of scope (PoC):**
- Full v1 dataset (150–300 books), train split, fine-tuning.
- New metric research beyond the small extensions below.
- Any change to the production extraction pipeline.
- Copyrighted/uploaded PDFs (`storage/uploads`) — excluded by the CC/PD constraint.

## Inputs / existing assets to reuse

| Asset | Role |
|---|---|
| [Category:PDF books in Telugu](https://commons.wikimedia.org/wiki/Category:PDF_books_in_Telugu) (58 files) | Primary Telugu PDF pool; 5 already local |
| [Category:Hindi-language books](https://commons.wikimedia.org/wiki/Category:Hindi-language_books) (505 files; use subcats e.g. Tarun Bharat Sangh 75 F, Premchand) | Hindi PDF pool |
| Commons file pages (`{{Book}}`/extmetadata) + `globalusage` → te.wikisource Index | Prefill metadata + license + verification link |
| [backend/app/schemas/metadata.py](../backend/app/schemas/metadata.py) `ALL_METADATA_FIELDS` (49) | Canonical field keys for the GT scaffold |
| [backend/app/services/extraction_validator.py](../backend/app/services/extraction_validator.py) | **Reuse unchanged**: presence/absence, exact/normalized match, token-F1, script-match, micro/macro/per-field F1 |
| [backend/scripts/evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) | Extend discovery only; keep scoring + report |
| [backend/scripts/eval_model.py](../backend/scripts/eval_model.py) (Levenshtein CER) | OCR-stage CER on Wikisource-verified text (optional in PoC) |
| [reference/dataset/s1.md](../reference/dataset/s1.md) | Column/label template + annotation guideline (not direct GT) |

## Design

### GT layout (new, per-book)

```
backend/tests/fixtures/ground_truth/
  manifest.jsonl                      # one row per book: slug, lang, category, license, pdf, gt, status
  tel/<slug>/
    original.pdf                      # only if --download
    expected_metadata.json            # harness-compatible scaffold (see below)
    provenance.json                   # commons title, file URL, license, extmetadata, wikisource index URLs, retrieved_at
  hin/<slug>/ ...
```

`expected_metadata.json` (consumed by `evaluate_extraction.load_expected`, which reads `expected_metadata`):

```json
{
  "description": "<title> — Commons GT scaffold (UNVERIFIED)",
  "language": "tel",
  "quality": "commons",
  "source_category": "Category:PDF books in Telugu",
  "total_pages": null,
  "recommended_pages": null,
  "verification_status": "unverified",
  "expected_metadata": { "<all 49 fields>": "<value or null>" },
  "field_status": { "<field>": "prefilled_needs_verification | empty_needs_annotation" },
  "notes": "Prefilled from Commons catalog metadata; EVERY field must be human-verified against the PDF + Wikisource index before this counts as ground truth."
}
```

### Fetch/annotate script spec

- **API:** MediaWiki `action=query` via `httpx` (project convention). `list=categorymembers` (`cmtype=file`, filter `.pdf`); per file `prop=imageinfo|globalusage`, `iiprop=url|size|mime|extmetadata`.
- **Prefill mapping (conservative):** `Artist/Author→author`, `ObjectName→title/label`, `ImageDescription→description_work`, language from category; `LicenseShortName/LicenseUrl/Permission→provenance`. All other fields `null`. **Every prefilled value is `needs_verification`** — GT is human-verified, never auto-final.
- **Verification links:** `globalusage` → capture `*.wikisource.org` Index/Page URLs into provenance.
- **Args:** `--category` (repeatable; default the two above), `--out`, `--limit` (default 5), `--download` (opt-in; **metadata-only by default**), `--recurse` (depth-limited subcategory walk for Hindi), `--delay` (default 0.5 s), `--overwrite`, `--lang`.
- **Safety/etiquette:** descriptive `User-Agent` with repo contact; rate-limit delay; retry on 429/5xx; skip existing GT unless `--overwrite`; writes only under `--out`; never touches `storage/uploads`. Downloaded PDFs must be gitignored (add `backend/tests/fixtures/ground_truth/**/*.pdf`).
- **Run:** `cd backend && uv run python -m scripts.fetch_commons_ground_truth --limit 5` (metadata-only), add `--download` to fetch PDFs.

### Harness integration (minimal)

- Add `discover_ground_truth()` walking `ground_truth/{lang}/{slug}/` (PDF + `expected_metadata.json`), returning the same `{sample_id, pdf_path, expected_path}` shape `evaluate_extraction.main` already consumes. Gate behind a `--ground-truth` flag so the synthetic `clean` path is unchanged.
- Reuse `evaluate_book` / `OverallEvaluation` as-is. **Note:** existing micro/per-field P/R/F1 are **presence-based** (TP = both non-null); value correctness is `token_f1` / `exact_match_rate` / `normalized_match_rate`. Report both.

### Metric extensions (small, optional in PoC)

1. **Fuzzy value match ≥ 0.95** (Levenshtein, already a dependency) alongside exact/normalized — separates OCR noise from semantic error.
2. **Hallucination rate** = FP / (GT-absent fields) — derivable from existing counts; surface explicitly.
3. **Per-batch F1** (8 batches via `FIELD_TO_BATCH`) — locate weak batches.
4. **OCR-vs-LLM attribution:** score extraction on (a) human-verified Wikisource text vs (b) pipeline OCR text for the same book; delta = OCR-induced vs LLM-only error. (Stretch for PoC.)

## Split (PoC)

- PoC is a **dev** set only (~15 books): tune prompts/OCR, validate the harness. **No test-set claims** from the PoC.
- v1 (later, per learnings/001): edition-level, work-grouped, stratified (language/source/era/quality/field-density), dedup by `sha256` + Wikidata QID, frozen **dev 30% / test 70%**, double-annotated gold test subset.

## Success criteria (PoC gate — all must pass)

1. Script enumerates both categories and writes **≥ 10 Telugu + ≥ 5 Hindi** per-book GT scaffolds with license + Wikisource link captured (metadata-only run succeeds, rate-limited, no errors).
2. **≥ 10 books human-verified** across all 49 fields (present / `verified_absent` / `unknown` recorded with source-page evidence); inter-annotator spot-check on ≥ 3 books.
3. Harness discovers the per-book GT and produces a report: per-field + per-batch + micro/macro F1, exact/normalized rates, hallucination rate, on **≥ 10 verified books** end-to-end.
4. **Attribution delta computed for ≥ 3 books** (GT-text vs pipeline-OCR) — identifies the dominant loss stage.
5. Every included PDF has a recorded **CC/PD license + attribution**; manifest is reproducible (re-run yields same slugs/links).
6. Results + go/no-go for v1 documented in `learnings/003-…`; this plan updated.

## Milestones (incremental; test/lint/typecheck each)

1. ✅ Script: category enumeration + file info + GT scaffold (metadata-only). Lint + `--limit 1` smoke test — **done, see Validation status**.
2. Script: `--download` + provenance + manifest; gitignore PDFs. Fetch ~15 PDFs.
3. Harness: `discover_ground_truth()` + `--ground-truth` flag; unit test discovery.
4. Human verification of ~10 books (annotation guideline from s1.md columns).
5. Scored run + metric extensions (fuzzy/hallucination/per-batch); attribution on ≥ 3.
6. `learnings/003` results + v1 go/no-go.

## Risks / caveats / owners

| Risk | Owner | Mitigation |
|---|---|---|
| Prefill mistaken for verified GT | Annotation lead | `verification_status=unverified` + per-field flags; harness only scores `verified` books |
| CC BY-SA share-alike on released dataset | User | Record per-file license; release dataset under compatible license + attribution |
| Hindi category mixed (jpg/djvu/crops) | Script | Filter `.pdf`; `--recurse` into book subcats |
| Modern fields sparse on classical texts | User/product | Accept correct nulls; include CC BY-SA VBS JVV modern books for richer fields |
| Network/API etiquette | Script | UA + delay + retry + limit; metadata-only default |
| 52↔49 wording drift | Dev | GT uses canonical 49 from `ALL_METADATA_FIELDS`; reconcile docs separately |
| Backend `.venv` HTTP stack broken | Dev | **Resolved.** Root cause was a half-written `httpcore` package (only `py.typed` + a stray `.tmp1oPSt5`, no `__init__.py`), i.e. an interrupted install, not a lockfile problem. Fixed with `uv sync --extra dev --reinstall-package httpcore`. Note: bare `uv sync` drops the `dev` extra (ruff/pytest/black) — always use `--extra dev`. |

## Validation status (2026-11-10)

- `ruff check` + `ruff format --check`: **clean**.
- `--help` under `uv run`: **OK** (imports `ALL_METADATA_FIELDS` → 49 keys).
- **Offline logic test: PASS** — 49-field scaffold, prefill (author/title/label/description_work/language), HTML strip, license capture, Wikisource-link filter (kept `te.wikisource`, dropped `en.wikipedia`), slugify, JSON-serializable.
- **Live metadata fetch: PASS** (`--limit 1`, metadata-only, no PDFs):
  - Enumeration: **56** PDFs in `PDF books in Telugu`, **193** in `Hindi-language books`.
  - Scaffolds written: `tel/2015.328360.Andhra-Mahaniyulu`, `hin/1913_Ummed_Singh_Charitra_Hindi_PDF` + `manifest.jsonl`.
  - Per book: **49/49** canonical fields present, **49** `field_status` entries, **6** prefilled (`label`, `author`, `title`, `description_work`, `language`, `original_language`); rest `empty_needs_annotation`.
  - Devanagari + Telugu text round-trips correctly (`author` = `लज्जाराम शर्मा`); license captured as `Public domain`; mime/size/`download_url` recorded.
- **Defect found and fixed during validation:** `wikisource_index_urls` captured every proofread subpage (`Page:….pdf/1…N`) — unbounded (50 URLs for a 90-page book). Now filtered structurally (proofread subpages are the only entries containing `/`, so localised `Index:`/`Page:` namespaces need no hardcoding) → **1** real Index page, provenance 17.2 KB → 6.6 KB. Raw `globalusage` capped at 25 entries + full count kept.
- **Known gap (follow-up, not blocking):** `publication_date` stays empty even when the year is visible in title/description (`1952`, `1913`). Deliberate — naive year regex risks false positives; left for human annotation or a reviewed heuristic.


## Open questions (defaults assumed unless redirected)

- Script home: `backend/scripts/` (matches existing tooling). GT home: `backend/tests/fixtures/ground_truth/`.
- PoC languages: Telugu + Hindi (current pipeline). Default `--limit 5`, metadata-only.
- Hindi pool: direct PDFs of `Hindi-language books` + `--recurse` into Tarun Bharat Sangh/Premchand if needed.

## References

- Feasibility: [learnings/001](../learnings/001-ground-truth-dataset-feasibility.md)
- Categories: https://commons.wikimedia.org/wiki/Category:PDF_books_in_Telugu · https://commons.wikimedia.org/wiki/Category:Hindi-language_books
- MediaWiki API: https://commons.wikimedia.org/w/api.php
- Harness: [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) · [extraction_validator.py](../backend/app/services/extraction_validator.py)
- Project repo: https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2
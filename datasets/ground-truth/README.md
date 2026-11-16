# Ground-Truth Dataset

Real Indic-language book PDFs paired with bibliographic metadata, for scoring the
OCR + LLM extraction pipeline against known-correct values.

> **The PDFs themselves are not in this repository** (they are large and third-party);
> only the metadata scaffolds and provenance are committed. See *Reproducing* below.

## Contents

| | |
|---|---|
| Books | **49** — Telugu **30**, Hindi **19** |
| Licenses | Public domain **45**, CC BY-SA 4.0 **4** (CC/PD-only by construction) |
| Source | Wikimedia Commons **49** (metadata also from Wikisource Index, Internet Archive / DLI) |
| Books with scan-text OCR ground truth (`wikisource_gt.json`) | **17** |
| Verification | source-verified **8**, model-prefilled **41** (`prefilled_llm_unverified`) |
| Frozen split | dev **15** / test **34** (tel 9/21, hin 6/13) — see `splits/` |

## Layout

```
ground_truth/
  manifest.jsonl                 # one row per book (slug, lang, license, split, sha256, …)
  splits/gt-split-v1.0.json      # frozen dev/test assignment
  {tel,hin}/<slug>/
    expected_metadata.json       # the 49 fields + field_status + field_source (+ node_fill)
    provenance.json              # Commons file, license, IA/Wikisource links, retrieved_at
    wikisource_gt.json           # proofread page text (17 books) — OCR ground truth
    original.pdf                 # gitignored; fetch it (see Reproducing)
```

## Schema

The 49 predefined fields (plus an optional `custom_fields`) are defined in
`backend/app/schemas/metadata.py`; see **[docs/metadata-fields.md](../../../../docs/metadata-fields.md)**
for the full list, batches and Wikidata mappings. Every `expected_metadata.json` carries
**exactly** the 49 canonical keys — enforced by `scripts/apply_field_schema.py`.

Each value carries a source in `field_source` and a state in `field_status`:

| `field_source` | Meaning |
|---|---|
| `wikisource_index` / `internet_archive` / `commons_category` | catalog enrichment |
| `node_llm_extraction` | read from the scan by the LLM (unverified prefill) |
| *(unset)* | seed value from the original fetch scaffold |

## Verification status

- **`verified`** — source-verified (catalog + scan-text check, `scripts/verify_ground_truth.py`).
  This is *not* human double-annotation.
- **`prefilled_llm_unverified`** — a verified catalog core plus `node_llm_extraction`
  extras. The scoring harness still scores these books but **excludes the prefilled
  fields** (`scripts/evaluate_extraction.py` → `ignored_fields`), so the model is never
  scored against its own output.
- To promote a book to `verified`, work through `reports/gt-review-queue.csv`
  (`scripts/gt_review_queue.py`), then re-run `verify_ground_truth.py`.

Coverage today: **636** non-null values, **37 of 49** fields populated; 12 fields
(cover designers, typesetters, scribes, awards, …) are empty in every book. Full
per-field / per-book breakdown: **[docs/ground-truth-field-coverage.md](../../../../docs/ground-truth-field-coverage.md)**
(`scripts/gt_coverage_report.py`).

## Evaluation use

```bash
cd backend
uv run python -m scripts.evaluate_extraction --ground-truth --model <model>   # score the corpus
uv run python -m scripts.apply_field_schema --check                            # schema conformance
uv run python -m scripts.build_manifest --check                                # manifest in sync
```

Metrics: presence/absence (TP/FP/FN), token-F1, exact/normalized match, script-match,
micro/macro/per-field F1 (`app/services/extraction_validator.py`).

## Reproducing the PDFs

Only CC/PD files are admitted. Re-download from Commons (the node-side fetcher is
`scripts/node_fetch_pdfs.py`), or re-fetch from scratch:

```bash
uv run python -m scripts.fetch_commons_ground_truth --cc-pd-only --download   # + --recurse for Hindi
uv run python -m scripts.enrich_ground_truth                                  # catalog fields
uv run python -m scripts.verify_ground_truth                                  # source-verify
```

## Limitations

- The metadata is **source-verified**, not human-double-annotated; 41 books still hold
  unverified model prefill (flagged, and excluded from scoring).
- Only Telugu and Hindi; mostly pre-1900 / early-20th-century DLI scans.
- Accuracy is capped by OCR (Telugu CER ≈ 0.45) — see `learnings/004`.
- `field_source` is unset for some catalog values (recorded with the seed, not a named source).

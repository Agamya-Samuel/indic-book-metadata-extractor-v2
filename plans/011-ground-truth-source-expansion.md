# 011 — Ground-Truth Source Expansion: scale + metadata depth (Telugu/Hindi, CC/PD)

- **Date:** 2026-11-13
- **Status:** Plan — awaiting go-ahead to implement (PoC first).
- **Depends on:** [learnings/001](../learnings/001-ground-truth-dataset-feasibility.md), [learnings/019](../learnings/019-gt-corpus-enrichment.md), [plans/009](009-metadata-page-selection.md).
- **Decisions (user, 2026-11-13):** Internet Archive **allowed**; goal is **both scale and depth**; **Telugu/Hindi only**; new catalogues are **another prefill to verify**, not authoritative; **CC/PD-only** for redistribution; OpenRouter **free** models permitted (**1000 req/day**).

## Objective

Grow the ground-truth corpus **and** enrich each book, using non-Wikimedia metadata sources where they carry more than Commons/Wikisource. Two concrete gaps today (49 books, 681 values, 39/49 fields):

1. **Scale** — more CC/PD Telugu/Hindi books.
2. **Depth** — the 10 fields still empty everywhere, and the **Latin-vs-script** problem (GT `author`/`title` are often Latin transliterations of a Telugu/Devanagari title page).

## Sources & roles

| Source | Role in the plan | Access | Fields it supplies |
|---|---|---|---|
| **IA `dc.*` (DLI metadata)** | richest per-item metadata, already reachable | `archive.org/metadata/<id>` | `dc.publisher`, `dc.date.citation`, `dc.description.totalpages`, `dc.subject.classification`, `dc.subject.keywords`, `dc.source.library`, `dc.description.scanningcentre` → publisher / date / pages / subject / genre |
| **DLI Catalogue** (sanskritdocuments.org) | catalogue **with publisher + year + pages + barcode** | HTML catalogues (24 parts) → parse | title, author, year, **publisher**, pages, language, barcode |
| **Pustaka Nidhi** (library.opentelugu.org) | **Telugu-script** titles/authors, pen names | catalog JSON (`catalog-*.json`, CC BY 4.0) | `label`/`title`/`author` **in Telugu script** → fixes Latin-vs-script |
| **SoK / Sanchaya** (research.servantsofknowledge.in) | citation-grade metadata; Telugu where present | site/data | author, year, subject (verify coverage) |
| **IA collections** (`digitallibraryindia`, `JaiGyan`, `TeluguBooksFrom*`) | **scale** — candidate books | IA advancedsearch API | candidate pool, PD filter |
| Commons / Wikisource | existing pool | existing scripts | — |

**Key finding:** nearly all large Indic scan collections federate onto Internet Archive, so IA-hosted scans stay in scope; the *distinct* added value is the **metadata layer** (DLI Catalogue publisher/year/pages; Pustaka Nidhi Telugu-script titles).

## Workstreams

- **A. Depth adapters** (new): `enrich` sources → map to the 49 fields → fill **only empty** fields, with `field_source` provenance.
  - `ia_dc` adapter: extend `fetch_ia_metadata` to read `dc.subject.classification` (→ subject/genre), `dc.date.citation` (→ publication_date), `totalpages` (→ pages), `dc.publisher`.
  - `dli_catalogue` adapter: parse the Telugu/Hindi catalogue parts → match by title/author/barcode → fill `publisher`, `publication_date`, `pages`.
  - `pustaka_nidhi` adapter: fetch the CC BY catalog → match → set `label`/`title`/`author` in **Telugu script**.
- **B. Script fix**: for each book whose `title`/`label`/`author` is Latin, replace with the native-script form from Pustaka Nidhi; where no source exists, transliterate with a free OpenRouter model and **mark it prefill**.
- **C. Scale**: pull new CC/PD Telugu/Hindi books (IA collections filtered to public domain + Commons), scaffold GT, run the existing enrich + fill pipeline.
- **D. Verify & measure**: keep every new value `prefilled_needs_verification`; run `verify_ground_truth`; regenerate coverage/manifest; report deltas.

## LLM use (OpenRouter free, ≤1000 req/day)

- Transliteration / script normalisation (workstream B).
- Reconciling conflicting catalogue values (pick the most consistent across DLI/IA/Pustaka).
- Optionally the page-detector text judge ([plans/009](009-metadata-page-selection.md)) so it does not consume node CPU.
Budget: free models only; batch and cache to stay well under 1000/day.

## Phases (PoC first — no big-bang)

1. **PoC (depth, small):** implement the `ia_dc` + `pustaka_nidhi` adapters, apply to the **existing 49 books**, measure how many of the 10 empty fields fill and how many Latin titles/authors become native script. **Gate:** a measurable rise (e.g. `publisher`/`publication_date`/`pages` up; ≥60 % of Telugu titles in Telugu script).
2. **Add DLI Catalogue** and measure its incremental publisher/date/pages gain.
3. **Scale:** fetch a bounded batch of new CC/PD Telugu/Hindi books (target +30–50), scaffold + enrich + fill.
4. **Wire into scripts** (`enrich_ground_truth.py` stays the entry point) + document.

## Success criteria

- Depth: fields populated **39/49 → ≥44/49**; the 10 empty fields materially reduced.
- Script: **≥80 %** of Telugu `title`/`label`/`author` hold Telugu script (was mostly Latin).
- Scale: **+30–50** CC/PD Telugu/Hindi books, all schema-conformant, all values provenance-tagged.
- Every new value is `prefilled_needs_verification` until a human confirms; no unverified value enters gold scoring.

## Risks

| Risk | Mitigation |
|---|---|
| IA PD filter is imperfect (rights varies) | require explicit PD/CC rights + spot-check; a human owns the licence call |
| Catalogue match quality (fuzzy join) | match on barcode where present, else title+author+year; flag low-confidence matches |
| Free OpenRouter rate limits / flakiness | batch, cache, retry; fall back to local gemma4 |
| New prefills add noise | only fill empty fields; plausibility filter; never overwrite verified values |

## Deliverables

- Adapter scripts under `scripts/` (ia_dc, dli_catalogue, pustaka_nidhi) + tests.
- Updated `learnings/` with measured depth/scale deltas.
- Regenerated `docs/ground-truth-field-coverage.md`, `manifest.jsonl`, review queue.

## Next steps

1. Approve this plan (or edit the phases).
2. Build the Phase-1 PoC adapters; measure on the existing 49 books.
3. In parallel, the queued metadata-page POC ([plans/009](009-metadata-page-selection.md)) and the accuracy evaluation can run on `test-node-1`.

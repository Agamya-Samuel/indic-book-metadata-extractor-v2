# 001 — Ground-Truth Dataset for OCR + LLM Metadata Extraction: Feasibility & Source Survey

- **Date:** 2026-11-10
- **Status:** Feasibility study complete → PoC recommended (no implementation yet)
- **Decision constraint:** Dataset must be **publicly redistributable — public-domain (PD) or Creative Commons (CC) licensed PDFs only.** Copyrighted uploads are excluded from the published set.

## Study Context

The pipeline (PDF → page selection → preprocessing → Tesseract OCR → Qwen2.5 7B via Ollama → 49-field metadata → review → library/Wikibase) has no ground-truth dataset, so extraction accuracy cannot be measured. Prior consultations ([reference/chat1.md](../reference/chat1.md), [reference/chat2.md](../reference/chat2.md)) flag this as the core gap and ask "which single stage causes the largest information loss?" This study (1) pins down the real field schema, (2) surveys existing datasets/sources that pair **real book PDFs** with **structured bibliographic metadata**, (3) evaluates the local `reference/dataset` assets, and (4) proposes metrics, a split, and a build approach. Web research used the `exa` connector.

## Summary

**No drop-in dataset exists for Indic book PDFs + our exact 49-field bibliographic ground truth.** The closest book-metadata benchmarks (DOAB, BiblioPage) are English/European and cover fewer fields; the Indic resources (telugu-ocr, IndicVisionBench) provide PDFs/page-images + human-verified **OCR text** but not bibliographic **fields**. **Go** on building our own set by combining **Wikidata book items (P996 → Commons PDF, P1957 → Wikisource index) + Wikimedia Commons/Wikisource + the local `s1.md` metadata seed + manual per-field verification**, borrowing scoring rules from MESD/BiblioPage/ScienceMetaBench.

## Key Findings

### 1. The schema is 49 fields, not 52

Canonical definition: [backend/app/schemas/metadata.py](../backend/app/schemas/metadata.py) (`FullMetadata`, L83–L133; `ALL_METADATA_FIELDS`, L282–L291). The extraction prompt ([prompts.py](../backend/app/services/prompts.py) L130–L143), DB (single JSONB `fields` column), review UI, and CSV export all derive from the same keys. **Every predefined field is `str | None` (default `None`); no enums or per-field validation.** `custom_fields` is an extra `dict | None` container, excluded from the field count. The "52" in [README.md](../README.md) L138 and [docs/indic_book_metadata_extractor.md](../docs/indic_book_metadata_extractor.md) L208–L212 is stale — that spec's own numbered table stops at row 49. **Action: reconcile the 52↔49 wording before publishing a dataset schema so GT and pipeline agree.**

49 fields by batch (Wikidata property where mapped):

| Batch | Fields (Wikidata P-ID) |
|---|---|
| core_identity (9) | label, author (P50), description_work, description_edition, original_language (P364), language (P407), isbn, title, subtitle |
| contributors (8) | translator (P655), editor (P98), compiler, cover_artist (P736), cover_page_designer, typesetting_by, typing_by, book_designer |
| publication (8) | publication_date (P577), publisher (P123), publisher_telugu, place_of_publication (P291), printer (P872), place_of_printing (P2919), distributors, sponsor (P859) |
| content_classification (6) | form_of_creative_work (P7937), genre (P136), subject (P921), inception (P571), context, awards |
| edition_series (6) | volume (P478), edition_number (P393), edition_or_translation_of (P629), part_of_series, serial_number_in_series, part_of_the_set |
| relationships (3) | based_on (P144), inspired_by (P941), first_published_in |
| ancillary_content (7) | dedication, dedication_verbatim, forewords, abbreviations, authors_in_compilation, opinions_messages, scribes |
| physical_extra (2) | pages (P1104), illustrators |

22 fields map to Wikidata; 27 do not. Multi-entity in practice (treat as sets when scoring): author, editor, translator, compiler, illustrators, cover_artist, distributors, authors_in_compilation, forewords, opinions_messages, scribes.

### 2. Local assets & `reference/dataset` verdict — useful, but unpaired

| Asset | What it is | Verdict |
|---|---|---|
| [reference/dataset/s1.md](../reference/dataset/s1.md) | **109-row Telugu work/edition table; columns map exactly to all 49 fields** (Wikidata P-IDs, Work vs Edition rows). `s2.md`/`s3.md` are smaller variants. | **High-value metadata seed + annotation template.** Almost certainly a Wikidata Telugu-book export. **No PDFs**, and titles (కాశ్మీర పట్టమహిషి, అహల్యాబాయి…) don't match the local PDFs. Many are modern/copyrighted → not usable as public PDFs. |
| [backend/tests/fixtures/samples/tel/commons/](../backend/tests/fixtures/samples) (5 PDFs) + `hin/commons/` (5 PDFs) | **Real scanned Telugu/Hindi books.** Verified via `pdfinfo`/`pdftotext`: **image-only** (near-zero text layer), 20–294 pp. Telugu producers PyPDF2/SuriPDF; Hindi PFU ScanSnap. | **Ideal OCR inputs**, but **no `expected_metadata.json`** (only synthetic fixtures have one). **Provenance CONFIRMED (§5):** the 5 Telugu files are exact matches in [Category:PDF books in Telugu](https://commons.wikimedia.org/wiki/Category:PDF_books_in_Telugu); the Hindi files map to [Category:Hindi-language books](https://commons.wikimedia.org/wiki/Category:Hindi-language_books) (Tarun Bharat Sangh subcategory). Licenses are PD-India / CC BY-SA — ready to annotate. |
| `backend/tests/fixtures/samples/{tel,hin,eng}/{clean,degraded,modern}/` | Synthetic generated PDFs **with** `expected_metadata.json`. | Format template only; not real books. Existing GT shape: `{description, language, quality, total_pages, recommended_pages, expected_metadata:{field:value}, notes}`. |
| `backend/storage/uploads/<uuid>/original.pdf` (26) | Real uploaded books (app data, gitignored). | **Excluded** from public set (copyright unknown). Internal-only if lawfully held. |
| [reference/dataset/sarvam_api](../reference/dataset/sarvam_api) | **Plaintext Sarvam API key.** Gitignored; verified **never committed** (`git ls-files`/`git log --all` empty). | ⚠️ **Rotate + move to an env file.** Owner: user. |

`reference/` is gitignored and untracked. **Net:** `s1.md` = schema-aligned metadata seed; the 10 `commons` PDFs = real OCR inputs; the two are **not paired**, and pairing them under CC/PD-only requires re-sourcing.

### 3. External source survey (filtered for Public CC/PD redistributability)

**Tier A — Indic PDF + bibliographic metadata (primary build path):**

| Source | Link | Contents | Metadata coverage | PDF availability | Access / license | Limitations |
|---|---|---|---|---|---|---|
| Wikidata WikiProject Books (te) | https://wikidata.org/wiki/Wikidata:WikiProject_Books/te | Book items; **P996 → Commons PDF file**, **P1957 → Wikisource index URL**, P373 Commons category, P953 work URL | Strong: P50/P123/P577/P291/P1104/P364/P407/P655/P98/P136/P921… maps to ~22 of our fields | Via P996 (Commons) | **CC0** metadata; SPARQL + dumps | Telugu/Hindi item coverage uneven; modern fields (ISBN, cover_artist) often missing; P996 not on every item |
| Wikimedia Commons — Telugu Wikisource PDF Books | https://commons.wikimedia.org/wiki/Category:Telugu_Wikisource_PDF_Books | ~22–29 real Telugu book PDFs (e.g. Aandhrakavula-charitramu 742pp, AmaraKosam 596pp, Kanyashulkamu 203pp) | File description + linked Wikisource index + Wikidata item | **Direct PDF download** | **PD / CC** (per file) | Mostly pre-1900 classical texts → modern fields absent; verify license per file |
| Wikimedia Commons — Telugu-language literature | https://commons.wikimedia.org/wiki/Category:Telugu-language_literature | ~39 files incl. PDFs (బాటసారి, etc.) + covers | Same as above | Direct PDF | PD / CC | Mixed books/covers/images; filter to PDFs |
| Telugu Wikisource | https://te.wikisource.org | Index pages + **ProofreadPage level 3–4 human-verified text** | Title/author/etc. on index; pulls from Wikidata when module enabled | Scans served from Commons | **CC BY-SA** | Telugu index→Wikidata module not enabled by default (only bn/fr/id/pa/ta per Diff blog); manual linking needed |
| Pustaka Nidhi (Open Telugu) | https://library.opentelugu.org/about/ | Telugu catalog aggregating DLI + Internet Archive; `meta.json`, `catalog-0..3.json`, `series.json` | Title, author, year, Telugu-script titles, pen names, corrections | Links to IA scans (site stores no files) | **Catalog CC BY 4.0**; scans per IA item | Catalog only; must filter IA items to PD; weekly refresh (download ≤1×/week) |
| Internet Archive — Books | https://archive.org/details/books | 10M+ texts; e.g. [Telugu Books From 1893](https://archive.org/details/TeluguBooksFrom1893) | Item metadata API: title, creator, date, publisher, language, pages | **PDF + OCR (chocr) download** | Per item (many **PD**) | Filter to PD/CC; metadata quality varies; some restricted |
| Digital Library of India catalog | https://sanskritdocuments.org/scannedbooks/DLI_Catalog/index.html | 180k+ books, 7 languages incl. Telugu/Hindi | Catalog: title, author, year, language, pages | Via DLI Downloader → IA | Catalog open; scans per item | 2010 catalog, transliteration errors; fetch PDFs from IA |

**Tier B — Indic OCR-text ground truth (evaluate the OCR stage separately):**

| Source | Link | Contents | Coverage | PDF/images | License | Limitations |
|---|---|---|---|---|---|---|
| AlbertoChestnut/telugu-ocr | https://huggingface.co/datasets/AlbertoChestnut/telugu-ocr | **221 Telugu books**, ~25,565 page image+verified-text pairs, ~11 GB; `corpus_profile.json` gives **original Commons PDF filename**, page_count, Wikisource quality (0–4) | Page-level **OCR text** GT (levels 3–4 human-verified); per-book `meta.json` | Page JPGs; **manifest names the source Commons PDF** (downloadable) | **CC BY-SA 4.0** | GT is text, not bibliographic fields; ≥80% Telugu, ≥50 pp, ≥1 transcribed page filters; gaps where no transcription |
| IndicVisionBench (ICLR 2026) | https://iclr.cc/media/iclr-2026/Slides/10010008.pdf | OCR track: 876 printed-book-page images, **10 Indic scripts** (incl. Telugu, Hindi), Wikisource **level-4 verified** text | OCR text GT, multi-script | Page images (Wikisource dumps pipeline documented) | Check paper/repo | Page-level OCR, not book metadata; small OCR track |
| ramSeraph/indic_wikisource | https://huggingface.co/datasets/ramSeraph/indic_wikisource | Page-image URLs + annotations + proofread/validated flags, **12 Indic languages** | OCR text GT | Image URLs (Commons) | Open (verify) | URLs not bundled images; not bibliographic |
| harsha-desaraju/telugu-wikisource-text-images | https://huggingface.co/datasets/harsha-desaraju/telugu-wikisource-text-images | Telugu Wikisource line/page images + text + CER + `source_file` (261 books) | Line/page OCR GT w/ quality flags | Images | Open (verify) | OCR-level, not fields |

**Tier C — Book-metadata benchmarks (methodology + cross-lingual sanity; not Indic):**

| Source | Link | Contents | Metadata coverage | PDF availability | License | Limitations |
|---|---|---|---|---|---|---|
| DOAB metadata-extraction | https://huggingface.co/datasets/biglam/doab-metadata-extraction | **9,363 OA books**, front-matter page images + **MARC21** | title, subtitle, authors, editors, publisher, year, ISBN, subjects, abstracts, language (~10–12 of our fields) | **Page images** by default; **full PDFs on request** (open an issue); 37,673 records w/ direct PDF URLs | **CC** (71.5% CC BY) | English + some DE/IT/FR/ES; **no Indic**; fewer fields; images not full PDFs by default |
| BiblioPage (Zenodo, 2025) | https://doi.org/10.5281/zenodo.15683417 | **2,118 scanned title pages**, 14 Czech libraries, 1485–21st c.; up to **16 attributes** + bounding boxes; **test fully manually verified** | author, illustrator, translator, editor, publisher (multi-value) + 11 others | **Title-page images** (JPG), not full PDFs | **Research / non-commercial only** | ⚠️ **Cannot redistribute** in a public CC/PD set; Czech/European; use for **design/metrics comparison only** |
| ScienceMetaBench | https://huggingface.co/datasets/opendatalab/ScienceMetaBench | Papers + textbooks + ebooks; copyright-page extraction | isbn, title, author, abstract, category, pub_time, publisher | PDFs | Check repo | Scientific focus; multilingual incl. Chinese; **SequenceMatcher scoring rule** is a useful template |
| MESD shared task (CEUR Vol-3977) | https://ceur-ws.org/Vol-3977/NSLP-06.pdf | S2ORC_Exp500v1 (500/100/100) + SSOAR vision (8000+ docs, bboxes) | 9 elements: title, authors, abstract, keywords, DOI, volume/issue, pages… | Original PDFs + text + labels | Open (verify) | Scholarly articles not books; **metric template: P/R/F1 + Levenshtein≥0.95 + present/absent accuracy** |
| Open Library dumps / API | https://openlibrary.org/developers/dumps | 20M+ editions, 6M authors; monthly TSV/JSON; Read API maps ISBN→IA scans | title, author, publisher, date, ISBN, language, pages, subjects | Links to IA readable scans | Open metadata | Not bulk via API (use dumps); Indic coverage thin; cross-verification source |
| Institutional Books (Harvard) | https://huggingface.co/datasets/institutional/institutional-books-hl-metadata | 983K PD books, 254 languages, metadata-only + OCR text | title_src, author_src, volume-level metadata | Metadata-only release (pair w/ IA PDFs) | IDI early-access terms | Mostly Western; verify terms; pair via IA |

### 4. Gap analysis

- **Indic + fields + PDF together:** only achievable by **joining** Wikidata (fields) ↔ Commons (PDF) ↔ Wikisource (verification). No single pre-built Indic dataset has all three at our field granularity.
- **Copyright/coverage tension (consequence of CC/PD-only):** freely-redistributable Telugu/Hindi scans are mostly **pre-1900 classical texts**, so modern fields (isbn, publisher_telugu, cover_artist, cover_page_designer, distributors, awards, sponsor, typing_by, typesetting_by) will frequently be **genuinely absent**. Expect ~15–20 of 49 fields sparse. This is legitimate null coverage, not pipeline failure — the metrics must reward correct nulls.
- `s1.md`'s modern books largely **can't** be paired with public PDFs → use it as a **schema/annotation template + Wikidata-query seed**, not as direct public GT.

### 5. Concrete CC/PD pool confirmed — the two user-specified Commons categories

**[Category:PDF books in Telugu](https://commons.wikimedia.org/wiki/Category:PDF_books_in_Telugu)** — **58 files (~56 PDFs** + 1 jpg + 1 djvu). Mix of DLI/IA scans (filenames embed IDs like `2015.328360.*`, `*025633mbp` → directly pairable to Internet Archive metadata), classical texts, and **modern VBS JVV titles**. **The 5 local `tel/commons` PDFs are exact matches** (identical page counts: Aanandhanga Undalante 20, Acharya SV Jogarao 205, Ammayi Evaru Abbai Evaru 32, Amsumathi 75 & 294) → **provenance confirmed**.

**[Category:Hindi-language books](https://commons.wikimedia.org/wiki/Category:Hindi-language_books)** — **505 files**, but mixed (covers, jpgs, djvu, 100+ image-crop series). Cleaner book pools are its subcategories: **Hindi books published by Tarun Bharat Sangh (75 F)** (matches the local `तरुण_भारत_संघ_*` scans), Books by Premchand (10 F), Collected Works of Mahatma Gandhi Hindi (45 F), Books by Devaki Nandan Khatri (6 F), Hindi Wikisource books (2 F), Novels in Hindi. **Filter to actual book PDFs.**

**Per-file evidence (fetched via exa) — the pairing + verification + license path works:**

| File | License | Metadata exposed on file page | Verification link |
|---|---|---|---|
| [Amsumathi by Adavi Bapuraju.pdf](https://commons.wikimedia.org/wiki/File:Amsumathi_by_Adavi_Bapuraju.pdf) | **PD-India** (author d. 1952) | Author: Adavi Bapiraju; self-scanned 2019 | **te.wikisource Index** (సూచిక) + ~294 proofread Page (పుట) entries |
| [Aanandhanga Undalante VBS JVV.pdf](https://commons.wikimedia.org/wiki/File:Aanandhanga_Undalante_VBS_JVV.pdf) | **CC BY-SA** (VRT ticket #2025052310003577; "VBS Relicensed works", May 2025) | **Author: Vitapu Balasubrahmanyam (Q110262997); Title ఆనందంగా ఉండాలంటే; Publisher: Jana Vignana Vedika; Language: Telugu; Publication date: 1992; Place: India** | te.wikisource Index + work page |
| [Godan - Premchand - Hindi Novel.pdf](https://commons.wikimedia.org/wiki/File:Godan_-_Premchand_-_Hindi_Novel.pdf) | **PD** (Premchand d. 1936; US PD/URAA) | Author: Premchand (**Q174152**, Open Library OL4683A, VIAF, LCCN); date 1938; source URL | Authority IDs → Wikidata/Open Library |

**Implications:**
- Commons **file pages already carry structured bibliographic metadata** (via `{{Book}}`/author templates): author + **Wikidata QID**, title, publisher, publication_date, language, place → directly prefill ~6–10 of our 49 fields, with authority IDs for cross-verification.
- Each file links to a **te.wikisource Index page** (bibliographic header) + **proofread Page transcriptions** → verification source and OCR-text GT in one place.
- **Modern Telugu books ARE available under CC BY-SA**: the VBS JVV collection was explicitly relicensed by the rights holder (VRT, 2025). This **partially resolves** the "CC/PD-only ⇒ classical texts only" concern — e.g. Aanandhanga Undalante (1992) is CC BY-SA with publisher/date/place. Still verify per file.
- Licenses are explicit and heterogeneous (**PD-India, PD-old, CC BY-SA**) → record the exact license + attribution per book in the manifest; CC BY-SA imposes share-alike on the released dataset.

## Evaluation Metrics (proposed)

Two stages, measured separately and end-to-end, with error attribution.

**A. OCR stage** (use Tier-B verified text GT): **CER** and **WER** per language and per scan-quality tier. Diagnostic, isolates OCR from LLM.

**B. Field-extraction stage** (per field, over books):
- **Presence/absence accuracy** — confusion over {GT present/absent} × {pred non-null/null}: TP, TN, **FP = hallucination**, **FN = miss**. Critical because many fields are truly absent.
- **Precision / Recall / F1** per field (MESD primary metric). P = correct / non-null preds; R = correct / GT-present.
- **Value match** (conditional on both non-null): **normalized exact match** (Unicode NFC, whitespace collapse, case-fold, punctuation strip, Indic digit/vowel-sign canonicalization) **and fuzzy match** (Levenshtein/SequenceMatcher **≥ 0.95**, per MESD/ScienceMetaBench). Report both to separate OCR noise from semantic error. **Per-value CER** as a diagnostic.
- **Multi-value fields** → set-level P/R/F1, order-independent, per-element fuzzy match.
- **Hallucination rate** = FP / (GT-absent fields). Headline trust metric for the LLM.

**C. Aggregates:**
- **Micro-F1** (pooled) and **Macro-F1** (mean per-field) — macro so rare fields aren't drowned.
- **Per-batch F1** (8 batches) — aligns with pipeline architecture; locates weak batches.
- **Difficulty-tier accuracy** (regex-easy: isbn/publication_date/pages; high-conf: title/publisher/language; medium: author/translator/editor/place; low/often-absent: awards/series/scribes/context) — avoids the wrong "all 49 at once" target.
- **Whole-record exact-match rate** (all present fields correct) — strict stretch metric.

**D. Stage attribution (answers the prior consultation's key question):** run extraction on **(a) human-verified GT OCR text** vs **(b) pipeline OCR text** for the same books. The delta separates **LLM-only error** from **OCR-induced error**.

**E. Confidence calibration (optional):** pipeline has per-field provenance/confidence → Expected Calibration Error / reliability diagram; does confidence predict correctness (for review-UI triage)?

## Dataset Split (proposed)

- **Unit = edition (book), grouped by work.** Keep all pages of a book and all editions of a work in one split (s1.md has Work+Edition rows) → no near-duplicate leakage.
- **Stratify** by language (Telugu/Hindi), source (Commons/Wikisource/DOAB/IA), era (pre-1900 PD vs modern CC), scan quality, and **field-density** (# non-null of 49) so splits have comparable difficulty.
- **Dedup** by PDF `sha256` and Wikidata QID across sources.
- **Sizes (CC/PD-only):**
  - **PoC:** ~20–30 books (≈10 Telugu + ≈5 Hindi + a few DOAB English for cross-check) to validate annotation + scoring harness.
  - **v1 eval:** ~150–300 books → **dev 30% / test 70%** (e.g., 200 → 60 dev for prompt/OCR tuning, 140 test touched once). No train split needed initially (pipeline isn't trained on this); if few-shot/fine-tuning later, carve a **work-disjoint train** split.
  - **Gold test subset:** every field **double-annotated + adjudicated**, with source-page evidence — mirrors BiblioPage's fully-verified test.
- **Freeze versioned splits** (`v1.0`) with a manifest: `book_id, wikidata_qid, source, license, language, era, split, pdf_sha256, gt_json, annotator, verification_status, source_urls`.

### Materialized (2026-11-13)

The split above is now **materialized** for the 35-book corpus. [`backend/scripts/build_manifest.py`](../backend/scripts/build_manifest.py) derives `backend/tests/fixtures/ground_truth/manifest.jsonl` from the per-book envelopes and freezes the assignment in [`splits/gt-split-v1.0.json`](../backend/tests/fixtures/ground_truth/splits/gt-split-v1.0.json). It is deterministic (`--check` fails if the manifest would change), so re-running is a no-op.

- **Rule:** `sha256(work_key)` within each language stratum; **work-groups are disjoint** (a book joins a group when its normalized title *extends* another's — volume/part markers included, regardless of script — so `...రత్నమాల` and `...రత్నమాల, ద్వితీయ సంపుటము` share a group). 34 groups over 35 books.
- **Ratio:** dev 30% / test 70% per language → **tel dev 9 / test 21**, **hin dev 2 / test 3**.
- **Manifest schema:** `manifest_version, slug, lang, work_key, source, category, commons_title, license, publication_date, year, era, pdf, pdf_size_bytes, pdf_sha256, gt, ocr_gt, ocr_pages, field_density, field_density_ratio, verification_status, scan_confirmed, split`.
- **Reconciliation:** the previous manifest was hand-appended by two fetch scripts and had drifted — 21 Wikisource-seeded rows carried no `verification_status`, 14 carried a stale `unverified`, while every per-book file said `verified`. The builder now reads status from each book's own `expected_metadata.json`, so the manifest and the books cannot disagree.
- **Status note:** `verified` means *source-verified* (catalog + scan-text check, [`verify_ground_truth.py`](../backend/scripts/verify_ground_truth.py)); it is **not** human-verified. Treat the split as provisional until gold human annotation lands (§Caveats).


## Annotation & Verification Protocol

1. **Auto-prefill** each book's 49 fields from Wikidata (P-IDs) + Open Library/IA metadata; use `s1.md` as the column/label template.
2. **Human verify** against the PDF's title/copyright/back-cover pages; record **evidence per field** (page + region/bbox + source URL).
3. Distinguish **`verified_absent`** (field truly not in source) from **`unknown`** (not found / not checked) — both serialize to `null` but carry a status flag, so hallucination scoring is fair.
4. Extend the existing `expected_metadata.json` shape with per-field provenance: `{value, status: present|verified_absent|unknown, source_page, source_url, verified_by, confidence}`.
5. **Inter-annotator agreement** (Cohen's κ / fuzzy-match rate) on a double-annotated subset; adjudicate disagreements.

## Recommendation — GO (build our own; phased)

- **Phase 0 — PoC (~1 week):** select ~10 Telugu from [Category:PDF books in Telugu](https://commons.wikimedia.org/wiki/Category:PDF_books_in_Telugu) (5 already local) + ~5 Hindi from [Category:Hindi-language books](https://commons.wikimedia.org/wiki/Category:Hindi-language_books) subcategories (Tarun Bharat Sangh, Premchand). Download PDFs, prefill from each Commons file page's `{{Book}}` metadata + Wikidata QID, follow the te.wikisource Index link, human-verify all 49 fields, build the scoring harness, run the pipeline, produce the first **per-field / per-batch report + OCR-vs-LLM attribution**. Document in `poc/` + a follow-up learning. Success criteria: harness scores a book end-to-end; ≥1 batch measured; attribution delta computed.
- **Phase 1 — v1 eval set:** scale to ~150–300 CC/PD books, stratified, frozen split, gold test subset.
- **Phase 2 — breadth:** add DOAB (CC) as a cross-lingual sanity benchmark; expand Indic OCR-stage GT via telugu-ocr / IndicVisionBench.
- **Primary sources:** Wikidata (CC0) + Commons (PD/CC) + Telugu Wikisource (CC BY-SA) + telugu-ocr (CC BY-SA 4.0) + Pustaka Nidhi (CC BY 4.0) + IA (PD items). **Methodology only:** BiblioPage (non-commercial — don't redistribute), MESD, ScienceMetaBench.

## Next Steps

1. Resolve the caveats below (owners assigned).
2. Write `plans/002-ground-truth-poc.md` (scope + success criteria) and run Phase 0 PoC; record results in `poc/` + `learnings/002-…`.
3. Reconcile the **52↔49** field-count wording in README/spec.
4. Build the scoring harness (normalize → presence/absence → P/R/F1 → fuzzy≥0.95 → aggregates → attribution) as a small script under `backend/` or `scripts/`.

## Caveats & Owners

| Caveat | Owner | Action / worth-it |
|---|---|---|
| CC/PD-only ⇒ field coverage | User / product | Mostly classical texts, but **modern VBS JVV Telugu books are CC BY-SA** (§5) → some modern fields available. Still expect ~15–20 fields sparse; accept correct nulls for v1. |
| Plaintext Sarvam API key in `reference/dataset/sarvam_api` | User | **Rotate + move to env file.** Never committed; low blast radius but fix now. |
| `s1.md` (109 modern rows) ↔ public PDFs don't pair | Annotation lead | Use as template/seed only; re-curate metadata for the Commons books actually fetched. |
| 10 local `commons` PDFs: provenance | Annotation lead | **RESOLVED (§5):** confirmed from the two Commons categories; licenses PD-India / CC BY-SA. Record exact per-file license + attribution in the manifest. |
| BiblioPage non-commercial license | User | Borrow design/metrics only; **do not** put its images in the public set. |
| 52↔49 schema wording drift | Dev | Reconcile docs so GT schema matches code. |

## References

- Project repository (seed assets + pipeline): https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2
- Canonical schema: [backend/app/schemas/metadata.py](../backend/app/schemas/metadata.py)
- Local metadata seed: [reference/dataset/s1.md](../reference/dataset/s1.md), `s2.md`, `s3.md`
- Real scan inputs: [backend/tests/fixtures/samples/](../backend/tests/fixtures/samples) (`tel/commons`, `hin/commons`)
- Prior consultations: [reference/chat1.md](../reference/chat1.md), [reference/chat2.md](../reference/chat2.md)
- Wikidata WikiProject Books (te): https://wikidata.org/wiki/Wikidata:WikiProject_Books/te
- Wikidata↔Wikisource integration: https://diff.wikimedia.org/2021/07/07/improving-wikidata-wikisource-integration/
- Commons Telugu PDFs: https://commons.wikimedia.org/wiki/Category:Telugu_Wikisource_PDF_Books
- telugu-ocr: https://huggingface.co/datasets/AlbertoChestnut/telugu-ocr
- IndicVisionBench: https://iclr.cc/media/iclr-2026/Slides/10010008.pdf
- Pustaka Nidhi: https://library.opentelugu.org/about/
- DOAB metadata-extraction: https://huggingface.co/datasets/biglam/doab-metadata-extraction
- BiblioPage: https://doi.org/10.5281/zenodo.15683417
- ScienceMetaBench: https://huggingface.co/datasets/opendatalab/ScienceMetaBench
- MESD shared task: https://ceur-ws.org/Vol-3977/NSLP-06.pdf
- Open Library dumps: https://openlibrary.org/developers/dumps
- Internet Archive Books API: https://archive.readme.io/reference/overview-1
- GLAM AI patterns (DOAB eval case study): https://danielvanstrien.xyz/ai-patterns-for-glam/evaluating-ai-outputs.html
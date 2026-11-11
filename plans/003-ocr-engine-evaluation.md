# 003 — Evaluation Plan: OCR Engine Selection for Indic (Hindi + Telugu) Scanned Books

- **Date:** 2026-11-11
- **Status:** Plan → awaiting approval to implement
- **Depends on:** [plans/002-ground-truth-poc.md](002-ground-truth-poc.md) — **partially satisfied already**: 002 has landed a corpus of **6 Commons books** (3 Telugu + 3 Hindi) with `original.pdf`, `expected_metadata.json` (marked `unverified`) and `provenance.json` under `backend/tests/fixtures/ground_truth/`. The study does **not** need to wait on 002's metadata verification, because it needs OCR *text* GT, not metadata GT. Also depends on [learnings/001](../learnings/001-ground-truth-dataset-feasibility.md) §Tier B.
- **Relationship:** replaces the "Indic-language-specific OCR engines" open item in [docs/known-limitations.md](../docs/known-limitations.md) (the load-bearing OCR weakness) with a measured selection decision.

## Objective

Select the OCR engine(s) for the extraction pipeline on an **evidence basis**, for **Hindi (Devanagari)** and **Telugu** scanned book PDFs, under a CPU-only / 16 GB / offline / open-source envelope. Optimise for accuracy on **metadata-bearing regions** (title, copyright, colophon) with the human OCR-review UI as the safety net, and decide explicitly whether to use **one engine for all languages or per-language engines**.

## Constraints (locked with the user)

| Constraint | Value |
|---|---|
| Compute | CPU-only, 16 GB RAM, **fully offline** (no cloud OCR APIs) |
| License | **Open-source** only |
| Languages | Hindi (`hin`), Telugu (`tel`); English as bilingual fallback |
| Priority | Accuracy on metadata-bearing regions ≫ resource efficiency > integration/maintenance effort |
| Review UI | Human OCR-review **stays** — verified in code, not assumed: [`workflow-stepper.tsx`](../frontend/src/components/shared/workflow-stepper.tsx) marks step 4 `requiresHumanReview: true` and it is documented as "the safety net" in [known-limitations.md](../docs/known-limitations.md) → target is "minimise reviewer correction effort", not zero-error OCR |
| Evidence | Empirical PoC on real scans **+** published benchmarks |

## Scope

**In scope (PoC):**
- Desk research (done, see §Prior evidence) narrowing candidates to a shortlist.
- A repeatable harness: Commons PDF page → render @300 DPI → run each engine → per-page **CER / WER / exact-line rate** + **peak RSS / wall-time / model size**.
- Head-to-head on **real Commons scans**: primarily 002's 6-book ground-truth set, secondarily the 10 fixture scans; page ground truth from Wikisource level 3–4 **where it exists (Telugu)** and hand-transcribed metadata front-matter **where it doesn't (Hindi)**.
- Integration + license assessment for the winner(s).
- Recommendation, including **single vs per-language** engine choice and a migration path from the current Tesseract-only pipeline.

**Out of scope:**
- Fine-tuning any engine (that is a follow-on once an engine is chosen; existing Tesseract LSTM pipeline stays as-is).
- Full-corpus (150–300 book) evaluation — that is v1 after the PoC.
- Any change to the production pipeline in this study.
- Cloud OCR APIs (excluded by the offline-only constraint).

## Prior evidence (desk research, via `exa`)

Real-scan evidence only; synthetic-render benchmarks are explicitly discounted (a Devanagari study shows EasyOCR chrF++ falls from **93.6 synthetic → 58.3 real**, and nine of ten systems collapse from synthetic to real).

### Engines

| Engine | Indic support | License | Footprint | Evidence / note |
|---|---|---|---|---|
| **Tesseract 5** (current prod) | native `hin`, `tel` packs | Apache-2.0 | ~1 GB RAM; ~2.3 pages/s @16 cores, 0.78 @4 cores | Best *general* engine on real Telugu in the strongest head-to-head (CER 6.64% / WER 31.98% / 26.7% exact lines); Hindi CER ~9% in ICCV-2025W; historical Smith-2014 Hindi WER 69%. Weakness is conjuncts/ligatures + mixed-script lines. |
| **PaddleOCR PP-OCRv5** | official `devanagari_..._rec` (84.96% line) + `te_..._rec` (87.65%), ~2M params | Apache-2.0 | text models ~2.4 pages/s @16 cores | Officially supports both languages and is tiny, but **independent Indic results are poor/variable**: Hindi CER 0.414/WER 0.864 (ICCV-2025W), 56% (ICON-2024), Telugu CER 9.21% (worse than Tesseract); one benchmark could not even run it (PaddlePaddle segfault). Must be measured ourselves. |
| **EasyOCR** | `hi`, `te` | Apache-2.0 | heavy: ~11 GB RAM in a CPU run; slow | Weak on Indic: Hindi 56% (ICON-2024), real-print mean CER 34.3% (median 16.7%). |
| **Surya** (datalab) | 90+ langs incl. `hi`; Telugu weak | code Apache-2.0; **weights modified OpenRAIL-M (free < $5M revenue)** | ~650–689M params, ~4–5 GB RAM; ~0.19 pages/s on Apple Silicon (x86 CPU slower) | Hindi 67.6–82.2% depending on version; Telugu printed word-acc only **63.1%** (vs IndicOCR 82.3%, Gemini 85.5%); weak on degraded scans (41.8%). **Commercial license gate + slow on CPU → reference only, likely no-go.** |
| **AI4Bharat / Bodhan IndicOCR** | 22 Indian languages incl. Hindi + Telugu, printed + handwritten | Indic Open Model License v1.0 (broad free use; hosting-as-API needs sign-off) | VLM-class (PP-DocLayoutV3 + Qwen3.5 + Sarvam tokenizer); CPU cost TBD | Best published Indic numbers: printed word-acc **Hindi 96.0%, Telugu 82.3%**; OmniDocBench 92.76 (vs Surya 91.13). Strongest candidate — CPU feasibility is the open question. |
| **IIIT-H Mozhi / CVIT IndicOCR** | 13 languages incl. Hindi + Telugu | verify per model | CRNN/CTC, line/word models | Mozhi dataset (1.2M word images) + models; paper reports beating common engines in 8/13 languages. Indic-specific, likely CPU-tractable. |
| **Lipikar (IIT-D)** | dedicated Hindi + Telugu models | verify | ~365 MB per language model | Purpose-built Hi/Tel OCR; small, plausible CPU fit. |
| Reference only | **docTR** (Latin-centric), **RapidOCR** (Paddle runtime), **Indra OCR** (CPU-fast but Latin-focused) | — | — | Include only if a shortlist engine fails to run; Indra is the CPU-speed yardstick (23.7 pages/s @16 cores) but has no Indic model. |

### Ground truth: measured, and **asymmetric by language** (verified 2026-11-11)

From learnings/001 §Tier B, page/line OCR **text** GT exists and can be aligned to the exact Commons PDFs. But I queried the live Wikisource Index pages for the 6 books already fetched by 002 and the result is **not** symmetric — this is the single most decision-relevant datum in the study:

| Book (002 corpus) | Wikisource Index page | Proofread-page levels measured |
|---|---|---|
| `tel/2015.373190.Athma-Charitramu` | `సూచిక:…` | **4 × level 3, 669 × level 4 → 673 verified pages** (691 pages, 691 records) |
| `tel/2015.328360.Andhra-Mahaniyulu` | `సూచిక:…` | **52 × level 3, 32 × level 4 → 84 verified pages** (90 pages, 90 records) |
| `hin/1913_Ummed_Singh_Charitra` | `विषयसूची:1913 Ummed Singh Charitra Hindi PDF.pdf` | 258 × level 1, **4 × level 3** → ~4 usable pages |
| `hin/2015.263752.Sadhu-Aur` | `विषयसूची:2015.263752.Sadhu-Aur.pdf` | pagelist empty → **0 pages** |
| `hin/19140101_Priyapravaas` | not found | — |
| `hin/*` (4 other hi.ws books sampled) | present | 0 / 356 × level 1 → **0 verified pages** |

Consequences, and they are unequal:

- **Telugu: GT is effectively free, and now built.** **757** verified pages across two fetched books (673 + 84 — the earlier 812/86/898 figures came from Index-page HTML and double-counted), both confirmed byte-identical to their Commons files with 100% page coverage. CER/WER at scale needs **no hand transcription**; the extractor is [`fetch_wikisource_gt.py`](../backend/scripts/fetch_wikisource_gt.py) and the artefacts are `wikisource_gt.json` per book. See [poc/004](../poc/004-poc-telugu-wikisource-gt.md).
- **Hindi: there is no free verified text.** hi.wikisource book bodies are ~entirely level 1 (unproofread); only 4 verified pages exist in the whole sampled set. So the Hindi arm must use one of:
  1. **Hand-transcribe metadata front-matter only** — 2–4 pages per book × ≥ 2 books ≈ **4–8 pages**. Small, bounded, and it *is* the decision-4a target, so the effort measures exactly what we care about rather than being waste.
  2. **IndicVisionBench Hindi subset** (level-4 verified, 10 scripts) — valid for engine-vs-engine comparison, but the page images are not our Commons scans, so it cannot validate the metadata-region hypothesis (H3).
  3. Find hi.wikisource books that are actually proofread (none found so far) — not worth chasing.

  Default: **(1) for the headline metadata metric + (2) as a cross-check**.

Two operational gotchas now recorded so the harness doesn't trip on them:

- **Index/Page namespace IDs are per-wiki, not the 102/104 defaults**: telugu Wikisource uses Index **ns 106** / Page **ns 104**; hindi Wikisource uses Index **ns 252** / Page **ns 250** (its ns 104/106 are taken). Hard-coded 102/104 lookups silently return author/mainspace pages.
- **002's `wikisource_index_urls` is unreliable for Hindi**: it is populated from Commons `globalusage` backlinks and records **0** for all three Hindi books, yet the Index pages demonstrably exist (found by searching Wikisource directly). Hindi GT discovery must query the target wiki, not infer from Commons usage.

So: the empirical PoC on **real** CER/WER is affordable **for Telugu today**, and affordable for **Hindi only if scoped to metadata front-matter** — which is the region decision 4a actually targets. The plan's ≥20-verified-pages-per-language gate must therefore be met differently per language (see Success criteria).

### Local corpus

**Primary corpus — 002's ground-truth set (6 books).** `backend/tests/fixtures/ground_truth/{tel,hin}/{slug}/` each hold `original.pdf`, `expected_metadata.json` and `provenance.json` (Commons title, license, source URL, Wikisource links). This is the set to evaluate on: it carries provenance and is the set whose Wikisource GT is measured above. Metadata GT is `unverified` — irrelevant here, since OCR-text GT comes from Wikisource, not from `expected_metadata.json`.

**Secondary corpus — the 10 fixture scans.** `backend/tests/fixtures/samples/{tel,hin}/commons/` are confirmed real, image-only scans (PD-India / CC BY-SA), provenance in learnings/001 §5. Use for extra engine runs and preprocessing sweeps; they lack Wikisource links, so they are not GT-bearing.

There are also 27 `original.pdf` files under `backend/storage/uploads/` (plus 23 rendered page dirs), left over from earlier pipeline runs — but the `indic_books` Postgres DB is not running locally, so none of their `ocr_results` (raw text, reviewer corrections) are retrievable. Treat them as extra raw material for engine runs only; they carry **no** reusable ground truth or reviewer-effort labels.

## Hypotheses to test (not conclusions)

- **H1 — No single engine wins both languages.** Expect an Indic-specific model (IndicOCR / Mozhi / Lipikar) or PaddleOCR-v5 to beat Tesseract on **Telugu**, while Tesseract stays strong on **Hindi**. If true → recommend a **per-language** engine (or primary + fallback), not one global engine.
- **H2 — CPU feasibility is the real filter.** Surya/IndicOCR-class models may be accurate but too slow / too RAM-heavy for 16 GB CPU at book scale; measure pages/s and peak RSS, don't assume.
- **H3 — Metadata-region accuracy ≠ whole-page accuracy.** Front-matter (display type, mixed scripts, ornaments, small caps) is harder; a model that wins body-text CER may lose on title pages. Score by page type.

## Methodology (empirical PoC)

1. **Corpus & GT alignment.** Telugu: use 002's `Athma-Charitramu` (812 verified pages) and `Andhra-Mahaniyulu` (86); resolve their Index page on te.wikisource (ns 106), align PDF page → `Page:` ns 104 by offset check, keep only level 3–4. Hindi: use ≥ 2 of 002's books and **hand-transcribe metadata front-matter** (title/copyright/colophon) as GT, cross-checked against IndicVisionBench Hindi; no Wikisource dependency.
2. **Page sample.** Per book, take metadata-bearing pages (title, copyright, colophon, series/edition pages) **plus** a stratified body sample (clean / dense / degraded). Telugu easily clears ≥ 20 verified pages/language from Wikisource; Hindi deliberately targets **≈ 4–8 front-matter pages** across ≥ 2 books, because that is the 4a region and the only GT that exists.
3. **Render.** Single preprocessing policy for fairness: 300 DPI, no engine-specific tuning beyond documented best settings; record the exact command/config per engine (and, for Tesseract, the current per-page PSM classifier result).
4. **Run engines** (shortlist; reference engines time-boxed): Tesseract 5 (baseline), PaddleOCR PP-OCRv5 (devanagari + te), IndicOCR/Mozhi/Lipikar (best available), Surya + EasyOCR as reference. Pin versions; document weight hashes.
5. **Metrics.** Per engine × language × page-type: **CER**, **WER**, **exact-line rate**, and **metadata-region CER/WER** as the headline. Normalise Unicode NFC; compute akshara-level error alongside code-point CER (Telugu/Devanagari ligatures).
    **Reviewer-effort metric (operationalises the locked objective).** "Minimise reviewer correction effort" is measurable from data the app already stores: the per-page distance between `ocr_results.raw_text` (engine output) and `ocr_results.corrected_text` (what a human left behind after review), set by [`update_ocr_correction`](../backend/app/api/pages.py) → `PUT /pages/{id}/ocr`. A page with `corrected_text IS NULL` was never reviewed; a page with `corrected_text == raw_text` was reviewed and needed **zero** correction. Report **corrections per metadata page** (edit-rate) and the raw→corrected CER, per engine. This is in-domain and end-user-weighted, which public benchmarks are not — but note two verified gaps: (i) the `ocr_results.corrections` JSONB column exists ([ocr_result.py](../backend/app/models/ocr_result.py)) yet is **never written**, so line/bbox-level attribution is lost and only whole-page diffs are recoverable; (ii) the `GET /api/admin/ocr-corrections?language=…` export documented in [docs/ocr-training.md](../docs/ocr-training.md) **does not exist** in the API. Because no `indic_books` database is running locally, historical reviewer data is not harvestable today — so this metric is collected **prospectively** (reviewer edits during PoC runs) or derived from re-runs, not retroactively.
6. **Resources.** Peak RSS, wall-time/page, model size, cold-start — measured on the 16 GB CPU box or a GCP test node (claim per [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)).
7. **Integration.** Python API ergonomics, Docker/deploy fit, offline weight management, license terms, effort to swap into `ocr_service.py`.
8. **Reproducibility.** Harness + pinned versions + results JSON committed under `poc/`; re-runnable command in the doc.

## Success criteria (study gate — all must pass)

1. Harness runs **≥ 3 engines × 2 languages** on real Commons scans and emits a reproducible CER/WER + resource table; where a reviewer touches PoC pages, the **raw→corrected edit-rate** (§Methodology 5) is recorded alongside it.
2. Ground truth established for **≥ 20 verified pages per language** with provenance, **by the language-appropriate route**: Telugu = Wikisource level 3–4 ✅ **done** (757 verified pages across 2 books, alignment validated by SHA1 identity + 100% record coverage + visual checks — [poc/004](../poc/004-poc-telugu-wikisource-gt.md)); Hindi = hand-transcribed metadata front-matter (≥ 2 books) **plus** IndicVisionBench Hindi cross-check — still open. Alignment validated on one book per language.
3. A recommendation with **measured** per-language engine choice + a defined fallback (or a justified single engine, if H1 is false).
4. Integration + **license** assessment for the winner(s) (offline deploy, hosting/commercial terms cleared for our use).
5. Findings written to `learnings/` (next free number; 002 reserves `learnings/003` for its own results) and this plan updated with results + go/no-go.

## Milestones (incremental; test/lint/typecheck each)

1. ✅ **Telugu done.** Corpus + GT alignment validated on `Athma-Charitramu` (673 verified) and `Andhra-Mahaniyulu` (84 verified): SHA1 identity vs Commons, full `Page:` coverage, visual spot checks on title/verse/body pages ([poc/004](../poc/004-poc-telugu-wikisource-gt.md)). Artifact: [`fetch_wikisource_gt.py`](../backend/scripts/fetch_wikisource_gt.py) → `wikisource_gt.json` per book. **Hindi still open** (≥ 2 books, hand-transcribed metadata front-matter). Per-wiki Index/Page namespaces resolved at runtime (te 106/104, hi 252/250), never assumed.
2. Harness: PDF→render→engine→CER/WER + RSS/time. Two existing seeds, both verified: [`eval_model.py`](../backend/scripts/eval_model.py) already computes **CER via Levenshtein** over a `<image_path>\t<ground_truth_text>` TSV (the same manifest format `generate_training_data.py` consumes) with a regression-gate pattern (non-zero exit on CER degradation) — reuse its `_edit_distance` + TSV convention; and [`test_ocr_accuracy.py`](../backend/scripts/test_ocr_accuracy.py) already drives PDFs through the live API across a **preprocessing-config sweep**, but scores `avg_confidence` only — reuse its sweep/batch structure and add CER/WER/GT scoring.
3. Tesseract baseline recorded (current prod config) — the number to beat.
4. PaddleOCR PP-OCRv5 (devanagari + te) recorded.
5. Indic-specific candidate(s) (IndicOCR / Mozhi / Lipikar) recorded — the likely winner.
6. Reference engines (Surya, EasyOCR) — time-boxed, CPU-only.
7. Resource profiling on the 16 GB target / GCP test node.
8. Comparative matrix + per-language recommendation → `learnings/`.
9. Integration + license write-up for the winner(s); migration sketch from Tesseract-only.

## Risks / caveats / owners

| Risk | Owner | Mitigation |
|---|---|---|
| GT is Wikisource translation vs page scan mismatch (off-by-one, edition drift) | Dev | Validate page alignment on one book first; drop pages that don't align |
| **Hindi has no free Wikisource GT** — hi.ws bodies are ~all level 1; only 4 verified pages in the sampled set (measured) | Dev | Scope Hindi GT to hand-transcribed metadata front-matter (the 4a target anyway) + IndicVisionBench cross-check; don't budget Telugu-scale automation for Hindi |
| Index/Page namespace IDs differ per wiki (te Index=106/Page=104, hi Index=252/Page=250); the 102/104 defaults silently return the wrong pages | Dev | Resolve namespaces from `siteinfo` at runtime; never hard-code 102/104 |
| 002's `wikisource_index_urls` reports 0 for all Hindi books although Index pages exist (Commons `globalusage` misses them) | Dev | Query the target Wikisource directly in the harness; treat Commons usage as a hint, not the source of truth |
| Level-4 "verified" pages can still be image-only, and overlaid stamps ("Donated in memory of…") are absent from GT, so engines are penalised for text GT never had | Dev | Filter on text-present before scoring; report metadata CER with the stamp caveat (it hits every engine equally, so ranking survives, absolutes do not) |
| Duplicate scans in the source PDF (Athma pp.3 = pp.5, identical GT) | Dev | De-duplicate identical GT text before reporting per-page distributions |
| Wikisource level 1–2 (unverified) text contaminates GT | Dev | Filter to level 3–4 only; record level per page |
| Synthetic-render benchmarks mislead (again) | Dev | Only accept **real-scan** measurements for the decision |
| Surya weights license (OpenRAIL-M, <$5M) blocks commercial use | User | Treat as reference only; note before any product use |
| Indic Open Model License "hosting-as-API" condition | User | Fine for self-hosted internal use; flag if exposed as a service |
| PaddleOCR environment fragility (segfault observed elsewhere) | Dev | Pin version, isolate venv/container, document workaround |
| VLM engines too slow on CPU at book scale | Dev | Measure pages/s on target; time-box; if too slow, deprioritise |
| Offline weight fetch blocked at deploy | Dev | Prefetch + vendor weights into the image/mount; verify air-gapped run |
| Metric gaming via normalization | Dev | Report raw + normalized; keep akshara-level error for Indic |
| Reviewer-effort metric is not harvestable today: `corrections` JSONB never written, `GET /api/admin/ocr-corrections` unimplemented, no local `indic_books` DB | Dev | Collect prospectively during PoC runs from `raw_text` vs `corrected_text`; fix the endpoint + line-level capture as a separate small change (not scope of 003) if the metric becomes the headline gate |

## Open questions (defaults assumed unless redirected)

- Final shortlist: Tesseract, PaddleOCR-v5, IndicOCR/Mozhi/Lipikar (primary), Surya + EasyOCR (reference). Add docTR/RapidOCR only if a primary fails to run.
- Sample size: ≥ 2 books per language, ≥ 20 verified pages per language for the PoC (scale in v1).
- Corpus: start with the 10 local Commons PDFs; fetch more via 002's script only if coverage is thin.
- Profiling host: 16 GB target box, or a claimed GCP test node for repeatable RSS/time.

## References

- Dependency: [plans/002-ground-truth-poc.md](002-ground-truth-poc.md) · [learnings/001](../learnings/001-ground-truth-dataset-feasibility.md)
- Current OCR: [backend/app/services/ocr_service.py](../backend/app/services/ocr_service.py) · [backend/app/core/config.py](../backend/app/core/config.py) · [docs/known-limitations.md](../docs/known-limitations.md) · [backend/scripts/eval_model.py](../backend/scripts/eval_model.py)
- Real-scan benchmarks: https://github.com/harsha-desaraju/TeluguOCR · https://github.com/Aditya-PS-05/devanagari-ocr-benchmark · https://www.openaccess.thecvf.com/content/ICCV2025W/CV4DC/supplemental/Kolavi_Nayana_A_Foundation_ICCVW_2025_supplemental.pdf · https://aclanthology.org/2024.icon-1.48.pdf
- Engines: https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html · https://github.com/datalab-to/surya · https://huggingface.co/bodhan-ai/indic-ocr · https://cvit.iiit.ac.in/usodi/tdocrmil.php · https://lipikar.cse.iitd.ac.in/model/
- OCR text GT: https://huggingface.co/datasets/AlbertoChestnut/telugu-ocr · https://huggingface.co/datasets/harsha-desaraju/telugu-wikisource-text-images · IndicVisionBench (ICLR 2026)
- Resource comparisons: https://github.com/datalab-to/indra · https://github.com/joneswack/ocr-workbench · https://contracollective.com/blog/local-ocr-document-extraction-apple-silicon-m5-max-2026
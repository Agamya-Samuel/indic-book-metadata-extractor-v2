# 018 — Prompt Engineering & Optimization for 49-Field Metadata Extraction (gemma4:e4b)

- **Date:** 2026-11-15
- **Status:** Approved; harness being built. Stages 2–4 gated on the budget decision in §0.1.
- **Study context:** Systematically evaluate and optimise the system/extraction prompts used by the LLM metadata pipeline. Model is **fixed** at `gemma4:e4b`; only prompt text varies. Serves the product goal of higher extraction accuracy from noisy Indic OCR without changing the model, schema or output contract.
- **Companions:** [learnings/025](../learnings/025-prompt-optimization.md) (findings) · [todos/016](../todos/016-prompt-optimization-tracker.md) (live tracker) · [learnings/017](../learnings/017-llm-configuration-research.md) / [018](../learnings/018-llm-config-validation.md) (fixed inference profile)

## 0. Budget

### 0.1 Corrected cost model

The first estimate assumed a cold batch call (~95 s from 017 §3.1). [018](../learnings/018-llm-config-validation.md) finding 7 measured **prompt-prefix caching at ~4×**: 154 s cold → 35 s for two batches once the model and config are stable. Holding `num_ctx`/`num_thread` fixed (which this study does) keeps the system-prompt prefix cached within a variant, so the realistic figure is ~17–25 s per batch after a cold first call per variant per node.

| Arm | Calls | Cold node-hours (upper bound) | Warm node-hours (expected) |
|---|---|---|---|
| 16 variants × 71 books × 8 batches (OCR track) | 9,088 | 240 (Rs 3,357) | ~53 (Rs 740) |
| 3 finalists × 17 books (clean track) | 408 | 11 (Rs 154) | ~2.3 (Rs 32) |
| Stress set (3 variants × 18 cases × 8) | 432 | 11 (Rs 154) | ~2.5 (Rs 35) |
| Consistency reruns (3 finalists × 6 books × 2) | 288 | 8 (Rs 106) | ~1.8 (Rs 25) |
| Production-temp confirmation (3 × 12 books × 8) | 288 | 8 (Rs 106) | ~1.8 (Rs 25) |
| One-time OCR corpus build | — | 6 (Rs 79) | 6 (Rs 79) |
| **Total** | **10,504** | **≈284 (Rs 3,976)** | **≈67 (Rs 944)** |

The `llm-benchmark hard cap` is **Rs 3000 ≈ 210 node-hours**. The expected spend fits comfortably; the *upper bound does not*. Keep the cap and treat the cold-path figure as the abort threshold: if measured spend exceeds ~Rs 2,400 at the end of Stage 2, stop and re-plan rather than proceeding to Stage 3. Record actuals in §4 of [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md).

### 0.2 Capacity gates

- **Live state checked 2026-11-15** (`gcloud compute instances list`): `test-node-1` and `test-node-2` are **TERMINATED** and free; `test-node-3` is **RUNNING** with label `gt-accuracy-eval` — another agent's job, **do not claim it**. An earlier draft reserved nodes 2 and 3; that was documentation-only, no instance label was applied, and it is **withdrawn**. When the run is approved, claim **test-node-1 and test-node-2** (`task=prompt-matrix` label + tracker row) and leave node-3 to its owner.
- One heavy task per node (AGENTS rule), model warmed once per node per variant.

## 1. Analysis of the existing prompts (deliverable 1)

### 1.1 What exists today

| Piece | Location | Current state |
|---|---|---|
| System prompt | `backend/app/services/prompts.py` `SYSTEM_PROMPT_TEMPLATE` | "expert bibliographic metadata extractor" + `{{ language_name }}`, one paragraph, null rule |
| Extraction prompt | same, `EXTRACTION_PROMPT_TEMPLATE` | `- name: Description` field list, OCR block, JSON-only instruction |
| Few-shot | same, `FEW_SHOT_EXAMPLES` | 3 **synthetic** examples (tel/hin/eng), fabricated books and ISBNs |
| Field definitions | `backend/app/schemas/metadata.py` | 49 nullable `str` fields in 8 batch models; only `description=` display names — **no extraction guidance** |
| OCR text | `backend/app/services/batch_routing.py` | per-batch front/back page windows, `[Page N]` markers, 2500-char cap, per-page budget = 2500/n |
| Post-processing | `llm_service.py` | tolerant JSON parse, `_strip_schema_echoes`, retry once, circuit breaker |
| Hybrid bypass | `extractors/hybrid.py` | `isbn`, `publication_date`, `pages`, `publisher`, `language` never reach the LLM |
| Generation | `llm_service.py`, `node_cfg.py` | native `/api/chat`, `think:false` for gemma4, temp 0.3 prod / 0 harness, `num_predict` 256–512, **no pinned seed in prod** |
| Custom prompts | `ExtractionRequest.custom_*_prompt` → Celery → `render_*(override=)` | already plumbed end-to-end |

### 1.2 Baseline to reproduce (not to assume)

| Run | Books | Micro P | Micro R | Micro F1 | Macro token F1 |
|---|---|---|---|---|---|
| `reports/gt-eval-gemma4-hin-8book.json` | 8 Hindi | 0.455 | 0.727 | 0.560 | 0.376 |
| `reports/gt-eval-gemma4-tel-8book.json` | 8 Telugu | 0.707 | 0.637 | 0.670 | 0.220 |

**These measure field presence, not value correctness** (§2.5). They are the reproduction target for `V00`, not a quality claim.

### 1.3 Weaknesses this study tests

1. **Contradictory null thresholds.** System: *"If a field cannot be determined, return null."* Extraction: *"Extract your best reading for every field that appears anywhere … use null only when the information is genuinely absent."* Two bars ⇒ guessing. Likely driver of high-recall/low-precision.
2. **Zero per-field guidance.** Fields are `- title: Title (if subtitle exists)`. Ambiguous pairs (`label`/`title`, `description_work`/`description_edition`, `printer`/`place_of_printing`, `publisher`/`distributors`) are undefined, and nothing says what to *exclude*.
3. **Few-shot is synthetic and batch-misaligned.** Invented books, invented ISBNs, and the same core-identity-shaped example injected into **every** batch — including `contributors` and `relationships`, whose schemas do not contain those keys. Also pays ~250 prompt tokens per call.
4. **No conflict policy** despite real colophons carrying several dates, ISBNs and publisher entities.
5. **No script policy.** GT mixes scripts (`author` as Latin `openrouter_transliteration` while `title` is Telugu). `script_match` is computed and unused.
6. **No section precedence.** `[Page N]` markers exist; the prompt never says which page type outranks which.
7. **No OCR-repair boundary.** "Use your knowledge to interpret corrupted words" licenses invention.
8. **Frontend/backend drift.** `frontend/src/app/books/[bookId]/llm-config/page.tsx:32-49` uses `{{language}}` and `{{field_descriptions}}`; the backend provides `language_name` and a `fields` loop. Any edited prompt renders with an **empty field list**.
9. **Unpinned determinism in production.** `temperature=0.3`, no `seed`.

## 2. Design

### 2.1 Frozen corpus (`backend/prompt_eval/corpus/`)

- **OCR track (71 books):** production path (`render_full_page` @ 300 DPI + `run_ocr`, `tesseract_oem=1`, `ocr_auto_preprocess=false`, `ocr_postprocess=true`, `ocr_tel_engine=tesseract`), front pages `1..min(total,12)` plus last 3 (colophon). One JSON per book.
- **Clean track (17 books with usable `wikisource_gt.json`):** identical shape, Wikisource text — the control that separates prompt quality from OCR noise. Measured 2026-11-15: of the 30 books carrying a `wikisource_gt.json`, **13 have an empty `pages` array**, and all 30 are Telugu. So the clean control is **Telugu-only, 17 books** — Hindi has no proofread source (the same limitation recorded in [learnings/018](../learnings/018-llm-config-validation.md) §Limitations). Hindi evidence therefore rests on the OCR track alone, and no clean-vs-OCR claim may be made for Hindi.
- `backend/prompt_eval/manifest.json`: per-book SHA256, page counts, track availability, GT path, few-shot holdout list.

### 2.2 Visibility mask (`scripts/prompt_eval/build_mask.py`)

For each `(book, batch, field)`, route the frozen pages exactly as production does, then search the routed text for the GT value: `found_exact` / `found_normalized` / `found_fuzzy` (token overlap ≥ 0.6 or char ratio ≥ 0.75) / `absent`.

| Mask | Scoring rule |
|---|---|
| `visible` | must be extracted — in the recall denominator |
| `absent` | must stay null — any value is a hallucination |
| `unroutable` | GT value not in the routed text ⇒ out of the recall denominator, reported separately |

`unroutable` separates *prompt recall misses* from **page-routing defects**. The 17 books with human `verification` blocks calibrate the mask (≥ 85 % agreement required) rather than drive it, so all 71 books are treated identically.

### 2.3 Prompt profiles

`backend/app/services/prompt_profiles.py` — ordered registry; each profile `{id, system_template, extraction_template, few_shot, output_mode, techniques, notes}`. `prompts.py` keeps its public functions and delegates to `baseline`, so no caller changes and the winner is already production code. Rendering context stays production-compatible plus optional `field_guidance` / `section_priority` that default to empty.

`output_mode`: `batch_schema` (existing contract, default) or `wrapped_evidence` (`{"fields": …, "evidence": …}`; runner unwraps `fields` for scoring and uses evidence for a grounding rate — experimental arm only).

### 2.4 Variant matrix (16 OCR-track variants)

Fixed for every variant: `gemma4:e4b`, `think:false`, **`num_ctx 4096`** (018 finding 2), `num_predict 512`, `temperature 0`, `seed 42`, `repeat_penalty 1.0`, `format = <batch>.model_json_schema()`, `keep_alive 30m`, `num_thread 3`.

| ID | System | Extraction | Technique under test |
|---|---|---|---|
| **V00** | baseline | baseline | Reproduction of today's prompts |
| **V01** | role-tight | baseline | Role-based, single-purpose framing |
| **V02** | strict-verbatim | baseline | Extraction-only; no outside knowledge, no completion |
| **V03** | ocr-noise | baseline | Noise-aware; explicit repair-vs-fabricate boundary |
| **V04** | script-aware | baseline | Script policy, confusable pairs, transliteration rule |
| **V05** | context-priority | baseline | Section precedence: title > copyright > colophon > cover > body |
| **V06** | null-discipline | baseline | One calibrated null rule replacing the contradictory pair |
| **V07** | baseline | schema-driven | Typed JSON schema in-prompt + explicit key list |
| **V08** | baseline | evidence-based | Per-field `{value, quote, page}` |
| **V09** | baseline | missing-explicit | `absent` / `illegible` / `ambiguous` before deciding |
| **V10** | baseline | field-guidance | Per-field "where to look / what qualifies / what to exclude" for all 49 |
| **V11** | baseline | few-shot-real | Real held-out GT exemplars, per language, batch-matched |
| **V12** | baseline | conflict-policy | Multiple dates/ISBNs/publishers/authors → precedence + tie-break |
| **V13–V15** | best-S | best-E | Combinations selected by rule from Stage 1/2 leaderboards |

Stage 1 = V00–V06 · Stage 2 = V00, V07–V12 · Stage 3 = V13–V15 · Stage 4 = clean-track confirmation (V00 + two finalists) · Stage 5 = stress + consistency + production-temp confirmation.

**Few-shot sourcing:** 2 Hindi + 2 Telugu verified books held out of all scoring; real excerpts become V11's exemplars; holdout list lives in the manifest.

### 2.5 Metrics

Additive extension to `extraction_validator.py`. Per field: `exact`, `normalized`, `fuzzy` (token-F1 ≥ 0.8 or char ratio ≥ 0.85), `token_f1`, `script_match`, `mask`.

Per run: field-level value accuracy; presence P/R/F1; value P/R/F1 (TP = present **and** normalized match); missing-field detection accuracy; hallucination rate; conflict-resolution accuracy (stress set only); JSON validity and schema compliance; consistency across reruns; tokens in/out; latency; breakdowns by language, batch, field, track and mask bucket. Aggregates carry a **bootstrap 95 % CI over books** (1,000 resamples) — a win is only called when the interval excludes zero, and a variant may not be recommended if it helps one language while the other regresses beyond its CI.

### 2.6 Stress set

Seeded perturbations of real frozen pages (12 cases): 10/20/30 % Indic confusables; dropped lines; truncated tail; title/author block removed; injected second author/publisher/date/ISBN from the same book's front matter; cross-page scrambling; Latin transliteration mixed into Telugu; duplicated blocks. Plus 6 genuinely noisy corpus books. Run V00 + top 2 only.

### 2.7 Runner

`backend/scripts/prompt_eval/`: `build_corpus.py`, `build_mask.py`, `build_bundles.py`, `run_eval.py` (stdlib-only, resumable, records Ollama token/timing counters), `score_eval.py`, `compare.py`, `build_stress.py`, `run_matrix.sh`. Every record carries variant, book, language, track, batch, seed, temperature, num_ctx, num_predict, fmt, think_false, model, git SHA. Registry: `backend/reports/prompt-eval/registry.json`.

### 2.8 Productionisation

Only after stress + confirmation: set the winning profile as default (`DEFAULT_PROMPT_PROFILE`), keep signatures; add `GET /api/extraction/prompt-defaults` and make the frontend consume it (kills the drift class); adopt `temperature 0` + pinned `seed` (confirmed by the production-temp arm at 0.3 first); golden-prompt regression tests; populate `MetadataFieldEvidence` from the evidence payload **only if V08 wins**.

## 3. Files

**New — app:** `backend/app/services/prompt_profiles.py`; `GET /api/extraction/prompt-defaults` in `backend/app/api/extraction.py`.
**New — eval:** `backend/scripts/prompt_eval/*.py`, `run_matrix.sh`.
**New — data:** `backend/prompt_eval/{corpus,manifest.json,fewshot,stress}`.
**New — reports/docs:** `backend/reports/prompt-eval/*`, this plan, `learnings/025`, `todos/016`.
**Modified:** `prompts.py` (delegate), `extraction_validator.py` (additive metrics), frontend LLM-config page, `test_prompts.py` + new `test_prompt_profiles.py` / validator tests, `Makefile`.

## 4. Risks

| Risk | Mitigation |
|---|---|
| Cost overrun | Warm-cache model (§0.1); abort threshold at Rs 2,400 after Stage 2; nodes stopped between stages |
| Mask error on noisy Telugu | Three-tier match; calibrate on 17 human-verified books; report masked **and** unmasked |
| Gain is an OCR artifact | Dual track; per-mask breakdown |
| Few-shot leakage | 4 books held out and unscored; holdout list in the manifest |
| Winner chosen on noise | Bootstrap CIs; bilingual regression check; consistency reruns |
| Extraction arms measured against the weakest system prompt | Stage 2 holds system = baseline deliberately; Stage 3 tests real combinations |
| Prompt change hides a routing defect | `unroutable` bucket reports routing misses separately; routing unchanged during the study |

**Non-goals:** model or quantization change; fine-tuning; OCR engine change; page-routing redesign; multi-stage/hierarchical extraction unless a single-pass plateau is demonstrated; repetition/loop guard (018 next step, tracked separately).

## 5. Verification

1. Corpus determinism — rebuild one book twice, byte-identical, SHA matches.
2. Baseline reproduction — V00 within noise of 0.560 (hin) / 0.670 (tel) presence-F1.
3. Mask sanity — ≥ 85 % agreement with the 17 human-verified books' `scan_confirmed`/`not_in_scan`.
4. Metric unit tests — exact/normalized/fuzzy, hallucination, `unroutable`, scripts, empty batches.
5. Golden prompt tests — rendered prompt snapshots per `(profile, batch, language)`.
6. Runner reproducibility — same variant twice at seed 42 ⇒ identical parsed JSON.
7. Regression guard — `evaluate_extraction --ground-truth --native --limit 2` still runs.
8. Integration check — winner's prompt appears in `llm_runs.prompt_template`; `/prompt-defaults` matches the backend; unmodified UI run sends `null` overrides.

## 6. Deliverable map

| # | Ask | Where |
|---|---|---|
| 1 | Analysis of existing prompts | §1 + `learnings/025` §1 |
| 2 | Tested variations | `prompt_profiles.py` + `reports/prompt-eval/variants.md` |
| 3 | Comparative results | `reports/prompt-eval/leaderboard.md` + per-variant JSON |
| 4 | Advanced-technique analysis | `learnings/025` §4 |
| 5 | Best combination | `registry.json` + `leaderboard.md` |
| 6 | Final prompts, ready to integrate | default profile + `prompts.py` + `/prompt-defaults` |
| 7 | Reproducible process | `scripts/prompt_eval/` + `make prompt-eval` + `learnings/025` §"how to re-run" |

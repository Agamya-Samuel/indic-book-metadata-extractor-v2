# 004 — Evaluation Plan: LLM Selection for Indic Metadata Extraction (49 fields)

- **Date:** 2026-11-11
- **Status:** **In progress** — resource/speed/JSON arm **measured**; accuracy arm **measured on 1 verified Telugu book (provisional)**; wider accuracy (more books/languages, noisy OCR) pending. Provisional winner **`gemma4:e4b` (`think:false`)**. Results: [learnings/005](../learnings/005-llm-model-evaluation.md).
- **Depends on:** [plans/002-ground-truth-poc.md](002-ground-truth-poc.md) — supplies the 6-book corpus with `expected_metadata.json` (marked `unverified`) under `backend/tests/fixtures/ground_truth/`. **This plan consumes metadata GT, not OCR-text GT**, so it needs 002's metadata arm specifically — the inverse of 003. Soft dependency on [plans/003-ocr-engine-evaluation.md](003-ocr-engine-evaluation.md): the LLM's input is OCR text, so the winning engine changes the input distribution — evaluate on today's Tesseract output now, then re-validate after 003 lands.
- **Relationship:** replaces the qualitative "switch to a higher-quality model" note in [docs/llm-extraction-zero-fields-investigation.md](../docs/llm-extraction-zero-fields-investigation.md) (line 331) and the untested Airavata→Qwen rationale in [`docker/Modelfile.qwen2.5`](../docker/Modelfile.qwen2.5) with a **measured** decision. Closes the "default LLM" line in [AGENTS.md](../AGENTS.md).

## Results so far (measured 2026-11-11, test-node-2)

**Resource / speed / JSON-validity arm complete** — full table in [learnings/005](../learnings/005-llm-model-evaluation.md). Headline:

- **`qwen3:4b-instruct-2507`** — valid JSON, 2.97 GiB resident, 3.34 tok/s, 108.9 s/batch: the safest drop-in (~½ the RAM, ~1.6× the speed of the current `qwen2.5:7b` at 4.72 GiB / 2.73 tok/s / 172.8 s).
- **`qwen3.5:4b`** — fastest **only with `think:false`** (82.6 s/batch); the default returns **0 chars** (output budget spent on the thinking channel).
- The same thinking trap hits `gemma4:e4b`, `qwen3:8b`, `qwen3.5:9b` defaults → must pin `think:false`.
- **Accuracy (2 verified Telugu books, 2 batches):** mean F1 — `gemma4:e4b` (`think:false`) **0.523** › `qwen3.5:4b` (`think:false`) 0.409 › `phi4-mini` 0.182 › `hex-1` 0.168; on Athma also `qwen3:4b-instruct-2507` 0.182 (fails JSON) › `qwen2.5:7b` 0.091 (title only). **Provisional winner: `gemma4:e4b` (`think:false`)**, confirmed on both books. Hindi untested (no clean text / verified GT).

**Accuracy arm pending — and now better-quantified:** all ground-truth books are `verification_status: unverified`, and a corroboration audit ([audit_ground_truth.py](../backend/scripts/audit_ground_truth.py)) found only **50 of 140** prefilled values are actually present in the source text (90 not found; Latin-transliteration vs Indic-script mismatches + Commons/IA-sourced fields). **GT must be fixed before absolute accuracy scoring is meaningful.** Harness ready: [make_eval_bundle.py](../backend/scripts/make_eval_bundle.py) → [node_acc.py](../backend/scripts/node_acc.py).

## Objective

Select the LLM(s) for the 49-field metadata extraction step on an **evidence basis**, for **Hindi (Devanagari)** and **Telugu** OCR text (English as bilingual fallback), under a CPU-only / 16 GB / offline / open-source envelope. Optimise for **per-field extraction accuracy on metadata fields** with the human metadata-review UI as the safety net, decide explicitly whether **one model or a combination** is warranted, and determine whether **decision models (Jev-class)** have any role. The locked end-goal is **minimise reviewer correction effort**, not error-free extraction.

## Constraints (locked with the user)

| Constraint | Value |
|---|---|
| Compute | CPU-only, 16 GB RAM **shared with frontend/backend/Postgres/OCR**, no GPU |
| License | **Open-source, commercially self-hostable** only |
| Languages | Hindi (`hin`), Telugu (`tel`); English as bilingual fallback |
| Priority | Accuracy on metadata fields ≫ resource efficiency > integration/maintenance effort |
| Review UI | Human metadata review **stays** (safety net) → target is "minimise reviewer correction effort", not zero-error extraction |
| Evidence | Empirical PoC on real OCR **+** published benchmarks; no model chosen on general-purpose leaderboards alone |

## Scope

**In scope (PoC):**
- Desk research (done, see §Prior evidence) narrowing candidates to a shortlist.
- A repeatable harness: OCR text → Ollama model → per-field **F1 / exact-match** + **hallucination rate** + **peak RSS / wall-time / tokens-per-second**.
- Head-to-head on **real noisy OCR** of 002's books, scored per field and per language.
- Integration + license assessment for the winner(s).
- Recommendation including **single vs combination** model choice, and an explicit **decision-model verdict**.

**Out of scope:**
- Fine-tuning any model (follow-on once a base is chosen).
- Full-corpus (150–300 book) evaluation — that is v1 after the PoC.
- Any production pipeline change in this study (the swap is milestone-gated on results).
- Cloud/API LLMs (excluded by the offline-only constraint).
- Changing OCR quality — that is 003; here OCR is a fixed input.

## Prior evidence (desk research, via `exa`)

### Current pipeline reality (verified in code, not assumed)

- **49 fields** (50 incl. `custom_fields`) in [`FullMetadata`](../backend/app/schemas/metadata.py), extracted in **8 batches** (`core_identity`, `contributors`, `publication`, `content_classification`, `edition_series`, `relationships`, `ancillary_content`, `physical_extra`).
- **5 fields bypass the LLM** — regex `{isbn, publication_date, pages}` ([`regex_extractors.py`](../backend/app/services/regex_extractors.py)) + dictionary `{publisher, language}` ([`dictionary_extractors.py`](../backend/app/services/dictionary_extractors.py)); LLM fills only gaps ([`hybrid.py`](../backend/app/services/hybrid.py)). So **~44 fields reach the model across ≤ 8 calls**.
- **Input is NOT the whole book.** Front-matter page windows per batch + last-3-pages colophon ([`batch_routing.py`](../backend/app/services/batch_routing.py)), hard-capped at **`MAX_OCR_CHARS = 2500`** ([`llm_service.py`](../backend/app/services/llm_service.py), line 58). `num_ctx=8192`, `MAX_PARALLEL_BATCHES=2`.
- **Null rule + few-shot already exist.** The system prompt says "use your knowledge of the language to interpret corrupted words" and "if a field cannot be determined... return null", with `tel`/`hin`/`eng` few-shot examples ([`prompts.py`](../backend/app/services/prompts.py)). JSON is enforced via `instructor` (`Mode.MD_JSON`, `max_retries=2`) over Ollama's OpenAI-compatible `/v1`.
- **Current runtime:** [`docker/Modelfile.qwen2.5`](../docker/Modelfile.qwen2.5) → `qwen2.5:7b`, temp 0.3, num_ctx 8192. Old Airavata Modelfile exists but is unused.
- **Two confounders that must be fixed before any fair comparison:**
  1. Frontend sends `max_tokens=2048` ([`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts)) while backend defaults to 512 — the output-reservation mismatch implicated in the historical "zero fields" bug.
  2. [`backend/reports/baseline.json`](../backend/reports/baseline.json) is a **stub** (F1 = 1.0, predicted == expected). **No real accuracy number exists for any model.** The harness [`evaluate_extraction.py`](../backend/scripts/evaluate_extraction.py) exists but has only been run in `--stub` mode.

> Implication: each call sees only ~2,500 chars of front matter, so a **256K context window is not required**. The need is strong Indic comprehension + reliable JSON at small inputs, fast on 4 cores → points at the **4B class**, not 7B+.

### Candidate models

| Model | Params | Hindi/Telugu | RAM (Q4_K_M) | Context | Structured JSON | License | Runtime (CPU/Ollama) |
|---|---|---|---|---|---|---|---|
| **Qwen2.5-7B** (current prod) | 7B | 29 langs | ~4.9 GB | 128K | Good (baseline) | Apache-2.0 | ✅ baseline to beat |
| **Qwen3.5-4B** | 4B (multimodal) | 201 langs incl. hi/te | ~2.7 GB | 256K (→1M) | Strong (IFEval 89.8) | Apache-2.0 | ✅ `qwen3.5:4b`; hybrid linear-attn arch |
| **Qwen3-4B-Instruct-2507** | 4B text-only | 119 langs incl. hi/te | ~2.5 GB | 256K | Proven (100% valid w/ grammar) | Apache-2.0 | ✅ mature, non-thinking |
| **Dhīr 5B MoE** | 5.09B / 1.79B active | Native 10 Indic incl. hi/te | ~2.95 GB | 16K | Vendor IF measured in EN only ⚠️ | Apache-2.0 | ✅ llama.cpp 4-bit; brand new (2026-11-03) |
| **Dhīr 2B** | 2.03B dense | Native 10 Indic incl. hi/te | ~1.21 GB | 16K | Same caveat ⚠️ | Apache-2.0 | ✅ llama.cpp; very light |
| **Hex-1 4B** | 4B (Qwen3-4B finetune) | 5 Indic: hi, te, ta, kn, ml | ~2.5 GB | ~32K | Chat-tuned; extraction unproven | commercial-permissive* | ⚠️ low adoption (23 downloads) |
| **Gemma 4 E4B** (reference) | 4.5B eff. (8B total) | 140+ langs, not Indic-specialized | ~4.8 GB | 128K | Native JSON + function calling | Apache-2.0 | ✅ needs Ollama ≥0.20.6 |
| Sarvam-1 | 2B | Excellent Indic (fertility 1.4–2.1) | ~1.2 GB | 8K | Base/completion only ❌ | **Non-commercial** ❌ | Disqualified (license + base model) |
| Sarvam-M | 24B | Excellent Indic (+20%) | ~14 GB ❌ | 32K | Hybrid reasoning | Apache-2.0 | Too big for shared 16 GB |

\* Hex-1: Bud Ecosystem states "open-source with commercial usage rights"; **confirm the exact license text on the model card** before choosing it.

### Resource envelope (the binding constraint)

Other services (OS, Docker/Dokploy, frontend, backend, Postgres, Tesseract workers) consume **~5–8 GB**, spiking during OCR; a safe LLM allocation is **~6 GB** (avoid swap). Q4_K_M ≈ 0.6 GB per billion params:

| Class | Weights (Q4) | 4-core generation (approx) | Fits ~6 GB? |
|---|---|---|---|
| 2B (Dhīr 2B) | ~1.2 GB | ~15–25 tok/s | ✅ |
| 4B (Qwen3.5-4B / Qwen3-4B-2507 / Hex-1) | ~2.5–2.7 GB | ~8–15 tok/s | ✅ comfortable |
| 4.5B eff. (Gemma 4 E4B) | ~4.8 GB | ~6–12 tok/s | ✅ borderline |
| 7–8B (current) | ~4.9 GB | ~3–9 tok/s | ⚠️ tight with 2 parallel ctx |
| 12–14B | ~7–9 GB | ~1–5 tok/s | ❌ risky |
| 24B+ (Sarvam-M, 30B MoE) | ~14–18 GB | <1–3 tok/s | ❌ swaps/freezes |

CPU **prefill** (not generation) dominates on long inputs; the 2,500-char cap keeps it tractable. **Qwen3.5-4B's hybrid architecture** (24 of 32 layers are linear-attention with **no KV cache**) makes long-context memory grow slowly and q4_0 KV lossless — a structural fit for noisy long-ish OCR on a RAM-constrained CPU.

### Decision models (the "Jev" question)

**Jev** (TypeSafe AI, 2026) is a closed **"System One" decision model**: given a state + question + fixed options, it returns a **calibrated probability per option in one forward pass and generates no text**. Question types: `choice` (≤255 options), `score` (2–10 levels), `noul` (yes/no). Open reproductions: **Kev** (Qwen3.5/3.8-based, Apache-2.0, but targets CUDA/Apple-MLX, not CPU); **JevAlt/Deem-4B** (Q4_K_M runs on CPU in ~3 GB, GGUF — but **English-only**; no Indic decision model exists); **Eikos** (recipe + corpus). The "Inner Jev" result shows ordinary instruct models can produce System-One decisions by **reading letter logits**, no separate model needed.

**Verdict to test, not assume:** decision models **classify into predetermined options and cannot generate free-text values** (title, author, publisher, dedication…), so they are **unsuitable for primary extraction**. Their only plausible niche (language/script ID, page-type classification, plausibility yes/no, confidence routing) is unserved for Indic today.

### Ground truth: the gating risk

The evaluation needs **metadata** GT. 002's `expected_metadata.json` is marked **`unverified`**, and there is **no real baseline at all**. So the plan's first job is to make the GT trustworthy enough to score against, and to record the current model's real number before any swap.

## Hypotheses to test (not conclusions)

- **H1 — A 4B-class model matches or beats current Qwen2.5-7B** on metadata per-field F1 at ~½ the RAM and ~2× the speed (attacks the 10–20 min/book pain). If true → downsize to 4B.
- **H2 — Indic-native models (Dhīr / Hex-1) beat general multilingual models on Telugu/Hindi field values** but may lag on structured-JSON/instruction-following (Dhīr's IF was measured in English only). If true → per-language or hybrid choice.
- **H3 — Grammar-constrained JSON removes parse/schema failures but NOT semantic errors.** Small models invent values for required-but-missing fields; the nullable-schema + null-rule is the real anti-hallucination lever. Worth measuring **hallucination rate** separately.
- **H4 — Extra models cost more than they return** on shared 16 GB / 4-core: a single extraction model is sufficient and decision models are unsuitable for free-text extraction.

## Methodology (empirical PoC)

1. **Fix confounders first (prerequisite).** Align `max_tokens` across backend and frontend; ensure **all 49 fields are `Optional[...] = None`** in `FullMetadata` (a required string forces invention); set `temperature` to 0 for extraction; pin the Ollama version and record the effective Modelfile per model.
2. **Establish a real baseline.** Run [`evaluate_extraction.py`](../backend/scripts/evaluate_extraction.py) in **real mode** (not `--stub`) with `qwen2.5:7b` on `tel`/`hin`/`eng` — including **noisy OCR** and **missing-field** cases. This first true number is a study output in itself.
3. **GT verification.** Verify (or explicitly mark provisional) the metadata GT for ≥ 2 books per language; because metadata GT is the scoring gate, the eval is only as good as this step.
4. **Model sweep — change only `Modelfile FROM`,** keep `num_ctx 8192`, `temp 0`: Qwen3.5-4B → Qwen3-4B-Instruct-2507 → Dhīr 5B MoE → Dhīr 2B → Hex-1 4B → (time-boxed) Gemma 4 E4B. Pin versions; record weight hashes.
5. **Score per field, not per job.** For each model × language × batch: **token-F1 / exact-match / normalized match** (harness already computes) **plus a separate hallucination rate** (gold = null but model produced a value) — the failure users trust least. Aggregate micro-P/R/F1 by batch and by the 8 groups.
6. **Reuse the reviewer-effort idea from 003.** Where the metadata review trail stores the original LLM value vs the human-final value, report **corrections per field** (edit rate); a field left unchanged needed zero correction. If that trail is not persisted, collect it **prospectively** during review (verify before relying on it — not assumed).
7. **Resources.** Peak RSS **with all other services running**, wall-time/book, cold-start, and prefill + generation tok/s (`llama-bench`/Ollama eval at num_ctx 8192) — on the 16 GB target or a claimed GCP test node.
8. **Integration + license.** Ollama tag/GGUF availability, offline weight fetch, license terms for commercial self-hosting.
9. **Reproducibility.** Harness + pinned versions + results JSON committed under `poc/`; re-runnable command in the doc.

## Success criteria (study gate — all must pass)

1. Real-mode harness runs **≥ 4 models × 2 languages** on 002's books, emitting per-field F1 + hallucination-rate + resource tables; a **real baseline for Qwen2.5-7B** is recorded (none exists today).
2. Metadata GT for the evaluated books is **verified or explicitly provisional**, with provenance.
3. A recommendation with **measured** model choice + a defined fallback, plus an explicit **single-vs-combination** decision and a **decision-model (Jev) verdict**.
4. Integration + **license** assessment for the winner(s) (commercial self-host terms cleared).
5. Findings written to `learnings/` (next free number) and this plan updated with results + go/no-go.

## Milestones (incremental; test/lint/typecheck each)

1. Confounders fixed (max_tokens, nullable schema, temp 0) + **real-mode baseline recorded for `qwen2.5:7b`** — the number to beat.
2. Harness extended: per-field F1 (exists) + hallucination rate + resource capture; runs per language.
3. Qwen3.5-4B recorded (primary candidate).
4. Qwen3-4B-Instruct-2507 recorded (stable fallback).
5. Dhīr 5B MoE + Dhīr 2B recorded (Indic-native challenger).
6. Hex-1 4B recorded (Indic-finetuned challenger).
7. Gemma 4 E4B recorded (time-boxed reference; Ollama ≥0.20.6).
8. Optional variant: grammar-constrained JSON (H3) on the top model.
9. Resource profiling on the 16 GB target / GCP test node.
10. Comparative matrix + recommendation (incl. decision-model verdict) → `learnings/`.

## Risks / caveats / owners

| Risk | Owner | Mitigation |
|---|---|---|
| Metadata GT is `unverified`; scoring gate is only as good as GT | Dev → User | Verify ≥ 2 books/language front-matter metadata, or mark provisional and treat numbers as directional |
| **No real baseline exists** (`baseline.json` is a stub) | Dev | Milestone 1 records the true `qwen2.5:7b` number before any swap |
| `max_tokens` inconsistency (frontend 2048 vs backend 512) confounds output | Dev | Fix first; single source of truth for output reservation |
| Small models **invent values for required-but-missing fields** | Dev | Nullable schema + null rule; measure hallucination rate separately; code-level value validation |
| Qwen3.5 hybrid arch is new; Ollama/llama.cpp support may regress | Dev | Pin Ollama/llama.cpp versions; keep Qwen3-4B-Instruct-2507 as fallback |
| Dhīr is ~1 week old; vendor benchmarks; IF measured in English only | Dev | Treat as challenger; measure JSON + Telugu/Hindi fields on our fixtures |
| Hex-1 low adoption; license text unverified | User | Confirm license + GGUF availability before adopting |
| Gemma 4 needs Ollama ≥0.20.6; early multimodal/FA bugs | Dev | Run text-only, pin version; reference only unless it wins |
| License traps: Sarvam-1 non-commercial; hosted-API conditions | User | Excluded from primary shortlist; re-check terms for any winner |
| LLM input depends on OCR engine (003) | Dev | Evaluate on current Tesseract now; re-validate after 003's winner lands |
| Reviewer-effort metric not harvestable if review trail doesn't persist values | Dev | Verify storage; else collect prospectively during review |
| No local `indic_books` DB → historical review data unavailable | Dev | Collect forward; don't assume retroactive harvest |
| CPU prefill on a shared box distorts wall-time | Dev | Measure with other services running; watch for swap |
| Metric gaming via normalization | Dev | Report raw + normalized; NFC + akshara-level for Indic |

## Open questions (defaults assumed unless redirected)

- GT verification scope: all 6 books vs ≥ 2 per language (default: ≥ 2/language).
- Whether to raise `MAX_OCR_CHARS` (2500) for 4B + 256K models — **test**, don't assume (CPU prefill cost).
- Grammar-constrained JSON (Ollama `format=schema`) adoption — likely a **separate small change**, but measure its effect on the top model here.
- Include Gemma 4 E4B (reference) or drop to keep the sweep tight? (default: include, time-boxed.)
- Profiling host: 16 GB target box vs a claimed GCP test node.

## References

- Dependencies: [plans/002-ground-truth-poc.md](002-ground-truth-poc.md) · [plans/003-ocr-engine-evaluation.md](003-ocr-engine-evaluation.md)
- Pipeline: [`backend/app/schemas/metadata.py`](../backend/app/schemas/metadata.py) · [`backend/app/services/prompts.py`](../backend/app/services/prompts.py) · [`llm_service.py`](../backend/app/services/llm_service.py) · [`batch_routing.py`](../backend/app/services/batch_routing.py) · [`hybrid.py`](../backend/app/services/hybrid.py) · [`docker/Modelfile.qwen2.5`](../docker/Modelfile.qwen2.5)
- Evaluation: [`backend/scripts/evaluate_extraction.py`](../backend/scripts/evaluate_extraction.py) · [`backend/reports/baseline.json`](../backend/reports/baseline.json) · [docs/known-limitations.md](../docs/known-limitations.md)
- Models: [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) · [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) · [Dhīr](https://zenteiq.ai/dhir/) · [Hex-1](https://huggingface.co/budecosystem/hex-1) · [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- Structured output: https://sbeconis.com/lab/structured-output/ · https://arxiv.org/html/2609.23742v1 · https://ollama.com/blog/structured-outputs
- CPU/resource: https://aihubhq.com/guides/run-llm-without-gpu/ · https://github.com/ggml-org/llama.cpp/issues/21385
- Decision models: https://victordibia.com/papers/jev.pdf · https://github.com/jaredpalmer/kev · https://mertkayacs.github.io/jevalt/ · https://arxiv.org/abs/2610.17205

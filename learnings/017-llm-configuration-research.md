# 017 — Self-Hosted LLM Configuration: Parameter Reference and Evidence Base

- **Date:** 2026-11-12
- **Status:** Research record (provisional recommendations pending §9 validation).
- **Study context:** Configuration reference for the 49-field metadata extraction LLM on a **4-core / 16 GB, no-swap, CPU-only** host shared with frontend, backend, Postgres, Redis and OCR. Serves [plans/004-llm-model-evaluation.md](../plans/004-llm-model-evaluation.md) and the request for all relevant model, generation and runtime parameters with evidence-backed values.
- **Scope:** runtime = **Ollama 0.40.16 (Docker), llama.cpp backend, CPU-only**. Models = the measured 3.8B–12B set. Out of scope: GPU, vLLM / llama.cpp-direct, fine-tuning.
- **Evidence rule:** no new experiments were run for this document. Every number is either official documentation or already measured in 004/005/006/010/013/015 and the committed reports under `backend/reports/`.

## Summary

On this host a batch call is **~0.9–1.3 K prompt tokens and ~60–70 output tokens**, so *context is not the constraint* — **RAM residency, generated-token count and thread count are**. The measured data support a conservative profile: **`phi4-mini` (3.8B) or `gemma4:e4b` with `think:false`, Q4_K_M, `num_ctx` 4096–8192, `temperature` 0, fixed `seed`, `num_predict` 512, 3 threads, 1 parallel, f16 KV cache, 6 GiB cap**. Temperature **0**, not 0.1: extraction is deterministic transcription, every measured accuracy run used 0, and Ollama's structured-output guidance recommends 0. The accuracy ceiling is OCR (Telugu median CER ~0.42–0.45), not the sampler.

## 1. Current production configuration (verified in code, 2026-11-12)

| Layer | Setting | Value | Source |
|---|---|---|---|
| Model | preload + Modelfile | `phi4-mini` (3.8B, MIT) | [docker-compose.production.yml](../docker-compose.production.yml), [Modelfile.phi4-mini](../docker/Modelfile.phi4-mini) |
| Model params | `temperature` / `num_ctx` | `0.3` / `8192` | Modelfile.phi4-mini |
| Ollama | memory cap | `mem_limit` and `memswap_limit` = `6g` | production compose |
| Ollama | env | `KEEP_ALIVE=30m`, `MAX_LOADED_MODELS=1`, `NUM_PARALLEL=1`, `NUM_THREADS=3`, `CONTEXT_LENGTH=4096` | production compose |
| App | model / temperature / max_tokens | `phi4-mini` / `0.3` / `256` | [llm_service.py](../backend/app/services/llm_service.py) L96–98 |
| App | context budget | `MAX_OCR_CHARS=2500` per batch, `MAX_PARALLEL_BATCHES=2` | llm_service.py L58–59 |
| App | JSON contract | `instructor` `Mode.MD_JSON` (prompt + pydantic validate, 2 retries); **no** schema-constrained decoding | llm_service.py L72–79 |
| Schema | fields | 49 optional string fields + `custom_fields` dict, 8 batches | [metadata.py](../backend/app/schemas/metadata.py) |
| Hybrid | bypass LLM | `isbn`, `pages`, `publication_date` (regex) + `publisher`, `language` (dictionary) | [hybrid.py](../backend/app/services/hybrid.py) |

**Config inconsistencies to resolve (they change what the model actually sees):**

1. **Context:** Modelfile says `num_ctx 8192`; container env says `CONTEXT_LENGTH=4096`. Check `ollama ps` (CONTEXT column) for the effective value.
2. **Parallelism:** app launches `MAX_PARALLEL_BATCHES=2`, but Ollama is capped at `NUM_PARALLEL=1` — the second request only queues.
3. **Output cap:** service default `max_tokens=256` vs `ExtractionRequest` default `512` (metadata.py L294).
4. **Stale comment:** production compose still labels the service `LLM Inference (Qwen2.5 7B)`.

## 2. Parameter taxonomy

Three layers, distinguished because they are configured in different places and answer different questions.

### 2.1 Model-specific (fixed by the weights you pull)

| Parameter | What it controls | Evidence / our situation | Verdict |
|---|---|---|---|
| Family, size (3.8B–12B) | Capability vs RAM/speed | Measured table §3.1 | 3.8B–4B class |
| Quantization (Q4_K_M … FP16) | Weight precision, file size, RAM | `qwen2.5:7b` default tag = **Q4_K_M** 4.7 GB; Q5_K_M 5.4 GB; Q6_K 6.3 GB; Q8_0 8.1 GB; FP16 15 GB ([tags](https://ollama.com/library/qwen2.5/tags)). llama.cpp calls Q4_K_M/Q5_K_M recommended ([discussion 2094](https://github.com/ggml-org/llama.cpp/discussions/2094)) | Q4_K_M; Q5_K_M only with RAM headroom |
| Thinking mode (`think:false`) | Whether output first goes to a hidden reasoning channel | **Measured trap:** qwen3:8b, qwen3.5:9b and the defaults of qwen3.5:4b / gemma4:e4b returned **0 response chars with eval_count=512**; qwen3.5:4b spent 2083 thinking chars (005 §2, follow-up JSONL) | **Mandatory `think:false`** for thinking-capable models |
| Chat template | Token framing | The Modelfile explicitly warns not to override: Qwen's `im_start`/`im_end` framing differs structurally from LLaMA's | Keep native |
| Native context limit | Max prompt tokens | qwen2.5-7b: 32 K config / 128 K with YaRN; the Ollama tag lists 32 K | Stay ≤ 8 K; YaRN unnecessary |
| Tokenizer fertility | Chars per token for Indic | Measured total prompts **878–1335 tokens** for the real 2500-char batch — far below the old 2–4 chars/token fear | 2500-char cap is safe |
| License | Self-host rights | phi4-mini MIT; qwen2.5 Apache-2.0 | Cleared |

### 2.2 Inference-generation (per request; API `options` / Modelfile `PARAMETER`)

Defaults below are from the Ollama [Modelfile reference](https://docs.ollama.com/modelfile).

| Parameter | Default | What it controls | Quality / consistency | CPU · RAM · time | Relevant? |
|---|---|---|---|---|---|
| `temperature` | **0.8** | Sampling randomness | Higher = varied/creative; **0 = greedy/deterministic** | None directly (can change length) | **Yes — set 0** |
| `top_k` | **40** | Truncate to K most likely tokens | Inert at temperature 0 | None | Inert when greedy |
| `top_p` | **0.9** | Nucleus probability mass | Inert at temperature 0 | None | Inert when greedy |
| `min_p` | **0.0** | Relative probability floor | Inert at temperature 0 | None | Inert when greedy |
| `repeat_penalty` | **1.0** (docs: disabled) | Penalise tokens already in the window | **Null-heavy JSON risk:** 49 mostly-`null` fields repeat the token `null`; a penalty >1 pushes the model *away* from null toward invented values | Negligible | **Keep 1.0 (≤1.05)** — do not use 1.1 blindly |
| `repeat_last_n` | **64** | Window for the penalty | Only matters if penalty >1 | Negligible | 64 fine |
| `presence_penalty` / `frequency_penalty` | 0 | OpenAI-style penalties | Same null-repetition risk | Negligible | Keep 0 |
| `seed` | **0** | RNG seed | Makes runs reproducible | None | **Pin an explicit value** |
| `stop` | none | Hard stop strings | Prevents runaway tails | Early stop saves time | Leave empty; do **not** reuse the corrupted Airavata stops |
| `num_predict` | **-1 (infinite)** | Max generated tokens | Lower = truncation; higher = wasted loops | **Directly caps generation time** (2–6 tok/s CPU) | **512** |
| `mirostat`, `tfs_z`, `typical_p` | off / deprecated | Alternative samplers | Not needed for extraction | — | Leave off |

### 2.3 Runtime / deployment (server or container level)

| Parameter | Default | What it controls | Quality | CPU · RAM · time | Relevant? |
|---|---|---|---|---|---|
| `num_ctx` / `OLLAMA_CONTEXT_LENGTH` | **2048** | Allocated context window | Truncation if too small; silent empty JSON | **KV RAM grows linearly**; prefill grows with actual prompt, not the allocation | **4096–8192** (§4) |
| `num_thread` | auto = **physical cores** | Worker threads for matmul | None | Throughput rises to physical-core count; oversubscription hurts | **3** (leave 1 core) |
| `num_batch` | Ollama default (commonly 512; **not verified** in current docs) | Prompt-processing batch | None | Larger = faster prefill, more transient RAM | Leave default; measure |
| `OLLAMA_NUM_PARALLEL` | **1** | Concurrent requests per model | None | **Multiplies KV memory** (FAQ: context × parallel); CPU has no spare cores | **1** |
| `OLLAMA_MAX_LOADED_MODELS` | **3** (CPU) | Models resident at once | None | Each resident model holds its full RAM | **1** |
| `OLLAMA_MAX_QUEUE` | **512** | Queue depth before rejection | Availability | — | Default fine |
| `keep_alive` / `OLLAMA_KEEP_ALIVE` | **5 m** | How long the model stays loaded | None | Avoids **6.5–36 s reload** measured | **30 m** (current) |
| `OLLAMA_KV_CACHE_TYPE` | **f16** | KV precision; `q8_0` ≈ half, `q4_0` ≈ quarter | FAQ warns **GQA-heavy models (e.g. Qwen2) may lose more precision** | RAM saving | **f16** at these contexts |
| `OLLAMA_FLASH_ATTENTION` | auto | Attention kernel | Minor | Required for KV quantisation | Leave auto |
| `num_gpu` | auto | GPU layers | — | Must be all-CPU here | 0 |
| `numa`, `use_mmap`, `use_mlock` | auto | Memory placement/loading | — | NUMA irrelevant on 4 vCPU | Leave default |
| `mem_limit` / `memswap_limit` | none | Container ceiling (host has no swap) | — | Prevents host OOM | **6 GiB** |

## 3. Measured evidence already in the repo

### 3.1 Resource / speed / JSON validity

test-node-2, 4 vCPU / 16 GB, `num_ctx=8192`, `num_predict=512`, temp 0, real Telugu `core_identity` prompt. From [005](../learnings/005-llm-model-evaluation.md) and [llm-model-sweep.jsonl](../backend/reports/llm-model-sweep.jsonl):

| Model | Resident GiB | Host peak used MiB | Prefill tok/s | Gen tok/s | Wall s | Prompt tokens | Eval tokens | JSON valid |
|---|---|---|---|---|---|---|---|---|
| qwen2.5:7b | 4.72 | 6116 | 9.44 | 2.73 | 172.8 | 1334 | 61 | yes |
| qwen3:8b | 5.54 | 7306 | 8.58 | 2.06 | 413.4 | 1315 | 512 | no (0 chars) |
| qwen3.5:9b | 5.76 | 10805 | 8.27 | 2.57 | 330.9 | 983 | 512 | no (0 chars) |
| gemma4:e4b | 1.80 | 7788 | 25.39 | 4.25 | 165.8 | 883 | 512 | no (0 chars) |
| gemma3:12b | 7.51 | 10367 | 5.66 | 1.61 | 223.9 | 878 | 53 | yes |
| qwen3.5:4b | 2.93 | 4829 | 16.25 | 4.47 | 181.5 | 983 | 512 | no (0 chars) |
| qwen3:4b-instruct-2507 Q4_K_M | 2.97 | 4557 | 15.61 | 3.34 | 108.9 | 1313 | 61 | yes |

From [llm-model-followup.jsonl](../backend/reports/llm-model-followup.jsonl): with `think:false`, gemma4:e4b produced valid JSON in **63 tokens / 94.8 s** and qwen3.5:4b in **70 tokens / 82.6 s**; without it, qwen3.5:4b at `num_predict=2048` spent **2048 tokens / 562 s** on **8686 thinking chars** and returned no answer. qwen2.5:7b repeated the same 61-token answer in **276–322 s** (prefill 5.0–5.7 tok/s under contention).

### 3.2 Accuracy (verified subset)

| Study | Data | Result |
|---|---|---|
| [006](../learnings/006-first-real-accuracy.md) | qwen2.5:3b, 8 books, unverified | micro P 0.340 / R 0.281 / **F1 0.308**; structured fields strongest (publisher 0.86, date 0.77, pages 0.67); name/text fields **P≈1.0, R≈0.13** |
| [010](../learnings/010-llm-shortlist-benchmark.md) | 1 Hindi book, 4 pages | **phi4-mini 0.500** > qwen2.5:3b 0.307 > qwen3-4b-2507 0.200 = qwen2.5:7b 0.200 |
| [013](../learnings/013-verified-shortlist-and-ocr.md) | 2 **verified** books, 6 pages | **phi4-mini F1 0.333** vs qwen3-4b-2507 0.106; schema-echo bug `title=CoreIdentityBatch` |
| [005](../learnings/005-llm-model-evaluation.md) | 2 **verified** Telugu books, clean Wikisource text | **gemma4:e4b think:false 0.523 mean** > qwen3.5:4b think:false 0.409 > phi4-mini 0.182; qwen2.5:7b 0.091 |

**Cross-study reconciliation:** phi4-mini wins **Hindi**, gemma4:e4b wins **Telugu**; **no model has yet been measured on verified books in both languages**. The consistent signal is **precision ≈ 1.0 with low recall**, and recall tracks OCR quality (Telugu CER 0.453 fast / 0.419 best, [004](../learnings/004-ocr-stage-cer.md)).

### 3.3 Host budget (oki, [015](../learnings/015-service-inventory-and-gating.md))

- 4 vCPU, **15.62 GiB, no swap**; Ollama capped 6 GiB.
- Core services idle 1184 MiB; **non-essential 2522 MiB** (openrefine 1084 + elasticsearch 900); Dokploy 706 MiB.
- Under load: pipeline peaks **7713 MiB anon**, minimum **3070 MiB available**.
- Phase split on a 30-page book: **OCR 568 s (19%) vs extraction 2434 s (81%)**.
- Tesseract already uses **~3.35 of 4 cores** on a slow page — CPU is shared with OCR.

## 4. Context size and chunking — the arithmetic

**Measured, not estimated:** the real Telugu `core_identity` call (2500-char OCR cap + system prompt + field list + few-shot + schema suffix) was **878–1335 prompt tokens** depending on the tokenizer, and a valid JSON answer was **53–70 tokens**. So one batch is **~0.95–1.4 K tokens**.

| `num_ctx` | Headroom over the measured call | KV cache (qwen2.5-7b, f16) |
|---|---|---|
| 2048 (Ollama default) | ~700–1.1 K — thin; Instructor retries can overflow | ~112 MiB |
| **4096** | **~2.7 K — sufficient** | **~224 MiB** |
| **8192** (current Modelfile) | ~6.8 K — ample for schema-constrained output and longer few-shot | **~448 MiB** |
| 16384 | ~15 K — not needed | ~896 MiB |

KV arithmetic for qwen2.5-7b: 28 layers × 4 KV heads × 128 head-dim × 2 (K,V) = **28,672 elements/token**; f16 = 57,344 B/token ≈ 0.0547 MiB/token. Context and KV are *not* the binding constraint here — the measured residency of the model (1.8–4.7 GiB) dominates. phi4-mini's architecture was not verified here; its measured resident size at ctx 4096 is ~2.5 GB (010).

**Chunking:** the current design (per-batch page routing + a **2500-char cap**, [batch_routing.py](../backend/app/services/batch_routing.py)) is the right shape. A single whole-front-matter call would be roughly 10–40 K tokens; at the measured **5–25 tok/s prefill** that is minutes of prefill per book *before* generation, and it dilutes attention across unrelated pages. The per-batch approach was the fix that ended the historical zero-field failures. Keep it; if recall on late-page fields (e.g. colophon) stays low, raise the cap to ~3500 chars **as a measured A/B**, not by assumption.

**Verdict:** `num_ctx` **8192** for safety (schema-constrained output + retries), **4096** acceptable when RAM-tight. Resolve the Modelfile-8192 vs env-4096 conflict and confirm with `ollama ps`.

## 5. Temperature — 0, not 0.1

Extraction is **deterministic transcription**: identical OCR should yield identical fields, and the human reviewer must be able to trust that. `temperature 0` is greedy/argmax decoding — the opposite of "creative". `0.1` still *samples*; it merely narrows the distribution. For this task that is a downside, not a safeguard.

Evidence:
- **Ollama structured-outputs guidance** explicitly says to set temperature to 0 for deterministic output (official blog, Dec 2024).
- **Every measured accuracy run in this repo used 0** (005, 006, 010, 013); production's `0.3` has no measured benefit.
- The failure mode is **recall, not precision** (P≈1.0, R≈0.13–0.33). Randomness cannot restore a value the model did not find; it can only make outputs non-reproducible.
- Qwen's published `0.7 / top_p 0.8 / repetition_penalty 1.05` are for **chat variety**, not faithful extraction, and are not what this pipeline needs.
- At temperature 0 the `top_k` / `top_p` / `min_p` settings are inert. Keep `seed` pinned anyway so results reproduce across engine upgrades.

**Risk to watch:** greedy decoding can loop or repeat on some models. Mitigate with `num_predict 512` and `repeat_penalty 1.0` — deliberately **not** 1.1, because a penalty on repeated `null` tokens can push the model toward invented values in a mostly-null schema (hypothesis to verify in §9).

## 6. The metadata output schema (49 fields)

One JSON object per batch. **Every field is `string | null`** (plus `custom_fields: object | null` in the last batch); `null` means *not determinable from the provided text*. There are no numbers, booleans or enums — dates, page counts and edition numbers stay strings. The schema must forbid extra keys.

| Batch | Fields (all nullable strings) | # |
|---|---|---|
| core_identity | label, author, description_work, description_edition, original_language, language, isbn, title, subtitle | 9 |
| contributors | translator, editor, compiler, cover_artist, cover_page_designer, typesetting_by, typing_by, book_designer | 8 |
| publication | publication_date, publisher, publisher_telugu, place_of_publication, printer, place_of_printing, distributors, sponsor | 8 |
| content_classification | form_of_creative_work, genre, subject, inception, context, awards | 6 |
| edition_series | volume, edition_number, edition_or_translation_of, part_of_series, serial_number_in_series, part_of_the_set | 6 |
| relationships | based_on, inspired_by, first_published_in | 3 |
| ancillary_content | dedication, dedication_verbatim, forewords, abbreviations, authors_in_compilation, opinions_messages, scribes | 7 |
| physical_extra | pages, illustrators (+ `custom_fields` object) | 2 |

**Why nullability is load-bearing:** plan 004 hypothesis H3 — grammar-constrained JSON removes *syntax* errors but not *semantic* ones; a required field forces invention. Nullable fields + the explicit null rule are the anti-hallucination lever. This is also why the JSON contract, not the sampler, is the strongest correctness control.

**Enforcement today:** `instructor` `Mode.MD_JSON` prompts for JSON, validates with pydantic and retries twice. It is **not** grammar-constrained, and 013 recorded the model echoing the schema class name (`title=CoreIdentityBatch`). The proposed change is Ollama `format=<json-schema>` derived from `model_json_schema()`, keeping pydantic validation as the second gate. Cost/benefit is unmeasured (§9).

## 7. What is verified vs uncertain

**Verified (official docs):** Ollama Modelfile defaults (§2.2), env defaults and KV-cache/parallel behaviour ([FAQ](https://docs.ollama.com/faq)), `format` JSON-schema structured outputs (Dec 2024), Qwen2.5 sampling recommendation `0.7 / 0.8 / 1.05` and architecture (28 layers, 4 KV heads), 32 K config context / 128 K with YaRN, Apache-2.0, and `qwen2.5:7b` = Q4_K_M.

**Verified (this repo's measurement):** every number in §3; the thinking-trap empty responses; the 878–1335-token prompt sizes; the 6 GiB/4-core budget.

**Not verified (do not assume):**
- `num_batch` default (absent from the current docs) and the exact **repeat_penalty** default (Modelfile page says 1.0/disabled; community docs often cite 1.1).
- phi4-mini and gemma4:e4b architecture/KV size.
- Whether `q8_0` KV measurably hurts Qwen's GQA at these lengths.
- The **effect size** of temp 0 vs 0.3, repeat_penalty 1.0 vs 1.1, schema-constrained vs MD_JSON, ctx 4096 vs 8192, 3 vs 4 threads, Q4_K_M vs Q5_K_M.
- A single model that has been measured on **verified** books in **both** Hindi and Telugu. Accuracy remains OCR-limited.

## 8. Provisional production profile

Apply the values; the confidence column says what the validation must confirm.

| Setting | Value | Rationale | Confidence |
|---|---|---|---|
| Model | `phi4-mini` (Hindi) or `gemma4:e4b` + `think:false` (Telugu) | Best measured per language; cross-language winner unmeasured | Medium |
| Quantization | Q4_K_M | Default; fits 6 GiB cap; Q5_K_M optional for 4B | High |
| `num_ctx` | 8192 (4096 acceptable) | Measured call ≤1.4 K; ample headroom | High |
| `temperature` | **0** | Deterministic transcription; official guidance; all measured runs | High |
| `seed` | 42 (pinned) | Reproducibility across engine upgrades | High |
| `top_p` / `top_k` / `min_p` | inert at temp 0 | — | High |
| `repeat_penalty` | **1.0** | Avoid penalising repeated `null` | Medium |
| `repeat_last_n` | 64 | Default | High |
| `num_predict` | 512 | Measured valid output 53–70 tokens | High |
| `think` | `false` | Mandatory for thinking-capable models | High |
| `stop` | none | JSON is self-terminating | High |
| `num_thread` | **3** | Leave one core for web/DB; matches 015 | Medium |
| `num_batch` | default | Unverified; measure | Low |
| `OLLAMA_NUM_PARALLEL` | 1 | No spare cores; KV × parallel | High |
| `MAX_LOADED_MODELS` | 1 | One model at a time | High |
| `keep_alive` | 30 m | Avoids 6.5–36 s reload | High |
| `OLLAMA_KV_CACHE_TYPE` | `f16` | KV is small; GQA caveat for q8_0 | Medium |
| `mem_limit` / `memswap_limit` | `6g` | Host has no swap | High |
| `MAX_OCR_CHARS` | 2500 | Measured fit; A/B only if recall demands | High |
| App `max_tokens` | unified **512** | Remove the 256/512 mismatch | High |
| Output contract | `format=json-schema` | More reliable than JSON mode; cost unmeasured | Medium |

## 9. Next steps

### 9.1 Decision queue (one at a time, independent first)

| # | Question | Depends on | Independence |
|---|---|---|---|
| Q1 | Context window + chunking | — | independent |
| Q2 | Temperature / sampling | — | independent |
| Q3 | Model + quantization | — | independent |
| Q4 | Output contract (schema-constrained vs MD_JSON) | — | independent |
| Q5 | `num_predict` + thinking budget | Q1, Q4 | dependent |
| Q6 | Threads + concurrency | CPU budget | dependent |
| Q7 | KV-cache precision | Q1, Q3, Q6 | dependent |
| Q8 | `keep_alive` + memory cap | Q6, Q7 | dependent |

**Decisions adopted (2026-11-12).** The recommended option was taken for each: Q1 = ctx 8192 + 2500-char page-grouped windows; Q2 = temperature 0 with a pinned seed; Q3 = 3.8B–4B class at Q4_K_M (`phi4-mini` / `gemma4:e4b` + `think:false`); Q4 = schema-constrained `format` with pydantic as the second gate; Q5 = `num_predict` 512; Q6 = 3 threads, 1 parallel; Q7 = f16 KV; Q8 = `keep_alive` 30 m, 6 GiB cap. These are exactly the provisional profile in §8; the §9.2 matrix exists to confirm or overturn each one, and the deviations found (e.g. temperature/`repeat_penalty`) are recorded in `learnings/018`.

### 9.2 Validation matrix (GCP, after the theory is agreed)

One variable per run, **3 seeds**, same inputs, **2 verified Hindi + 2 verified Telugu** books, `core_identity` + `publication` batches.

| Run | Variable | Metric that decides it |
|---|---|---|
| M0 | Current prod config (record the *actual* `num_ctx` via `ollama ps`) | baseline |
| M1 | temp 0 vs 0.3 | stability + F1 |
| M2 | ctx 4096 vs 8192 | truncation/empty rate, wall time, RSS |
| M3 | repeat_penalty 1.0 vs 1.1 | **hallucination rate** (gold null → predicted value) |
| M4 | schema-constrained vs MD_JSON | JSON validity, schema compliance, latency |
| M5 | 3 vs 4 threads | wall time, host CPU |
| M6 | Q4_K_M vs Q5_K_M (4B) | F1, RSS |
| M7 | phi4-mini vs gemma4:e4b think:false, **both languages** | per-field F1, hallucination |

Metrics for every run: per-field P/R/F1, exact and normalized match, JSON validity, hallucination rate, latency, peak RSS, CPU. Node protocol: claim an idle node (node-3 to start), one heavy task per node, stop when done, update [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md). Results → `learnings/018-...`.

## 10. References

- Plans: [plans/004-llm-model-evaluation.md](../plans/004-llm-model-evaluation.md)
- Prior learnings: [004](../learnings/004-ocr-stage-cer.md) · [005](../learnings/005-llm-model-evaluation.md) · [006](../learnings/006-first-real-accuracy.md) · [010](../learnings/010-llm-shortlist-benchmark.md) · [013](../learnings/013-verified-shortlist-and-ocr.md) · [015](../learnings/015-service-inventory-and-gating.md)
- Measured reports: [llm-model-sweep.jsonl](../backend/reports/llm-model-sweep.jsonl) · [llm-model-followup.jsonl](../backend/reports/llm-model-followup.jsonl) · [pipeline-profile-oki.json](../backend/reports/pipeline-profile-oki.json)
- Official docs: [Ollama Modelfile](https://docs.ollama.com/modelfile) · [Ollama FAQ](https://docs.ollama.com/faq) · [Structured outputs](https://ollama.com/blog/structured-outputs) · [Qwen2.5 blog](https://qwenlm.github.io/blog/qwen2.5/) · [Qwen2.5-7B-Instruct card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) · [qwen2.5 tags](https://ollama.com/library/qwen2.5/tags)
- Quantization/threads: [llama.cpp discussion 2094](https://github.com/ggml-org/llama.cpp/discussions/2094) · [llama.cpp auto-threads = physical cores](https://freenode.net/article/llama-cpp-auto-thread-count-now-prefers-physical-cores)
# 005 — LLM Model Evaluation for Metadata Extraction

- **Date:** 2026-11-11
- **Study context:** [plans/004-llm-model-evaluation.md](../plans/004-llm-model-evaluation.md) — select the LLM for the 49-field metadata extraction step under a CPU-only / 16 GB / offline / open-source envelope.
- **Status:** **Resource / speed / JSON-validity arm measured** on the real target node. **Accuracy arm NOT measured** — blocked on metadata ground-truth verification (all 14 GT books are `unverified`) and on authorization to run scoring against the node.

## Summary

On a real 4 vCPU / 16 GB node, the measured comparison points to **`gemma4:e4b` with `think:false`** as the best extractor: highest token-F1 (**0.636**) on a verified Telugu book — just ahead of `qwen3.5:4b` (**0.545**) — and also the fastest (182 s / 2 batches) and lightest (~1.8 GiB). The current production **`qwen2.5:7b` (F1 0.091, title only)** and **`qwen3:4b-instruct-2507` (0.182, fails structured JSON)** are unsuitable. **Thinking-capable models must set `think:false`** or they return empty output. Provisional pick: **`gemma4:e4b` (`think:false`)**, confirmed on **2 verified Telugu books** (mean 0.523 vs `qwen3.5:4b` 0.409); Hindi untested; the dominant limiter is OCR/recall, not the model.

## Key findings

### 1. Measured resource / speed / JSON-validity (test-node-2, 4 vCPU / 16 GB)

Measured by the prior session's `bench_models.py` (Ollama-in-Docker, the **real** Telugu `core_identity` prompt, `num_ctx=8192`, `num_predict=512`, `temperature=0`, `format=json`); results in `/tmp/bench-results.jsonl` and `/tmp/followup-results.jsonl`, re-read 2026-11-11.

| Model | Resident GiB | Host peak used (MiB) | Prefill tok/s | Gen tok/s | Wall (s) | JSON valid |
|---|---|---|---|---|---|---|
| **qwen2.5:7b** (current prod) | 4.72 | 6116 | 9.44 | 2.73 | 172.8 | ✅ |
| **qwen3:4b-instruct-2507-q4_K_M** | 2.97 | 4557 | 15.61 | 3.34 | 108.9 | ✅ |
| **qwen3.5:4b** (default) | 2.93 | 4829 | 16.25 | 4.47 | 181.5 | ❌ (0 chars) |
| **qwen3.5:4b** (`think:false`) | — | ~4.7 GB | 16.19 | 4.61 | 82.6 | ✅ |
| gemma4:e4b (default) | 1.80 | 7788 | 25.39 | 4.25 | 165.8 | ❌ (0 chars) |
| qwen3:8b | 5.54 | 7306 | 8.58 | 2.06 | 413.4 | ❌ (0 chars) |
| qwen3.5:9b | 5.76 | 10805 | 8.27 | 2.57 | 330.9 | ❌ (0 chars) |
| gemma3:12b | 7.51 | 10367 | 5.66 | 1.61 | 223.9 | ✅ |

### 2. The thinking-model trap (load-bearing operational finding)

`qwen3:8b`, `qwen3.5:9b`, and the **defaults** of `qwen3.5:4b` and `gemma4:e4b` returned **0 response characters with `eval_count=512`** — they spent the entire output budget on the `thinking` channel (qwen3.5:4b: 2083 thinking chars, empty response). Superseded by the "Follow-up" retry: `qwen3.5:4b` with `think:false` returned valid 198-char JSON in 70 tokens / 82.6 s. **Consequence:** any thinking-capable model MUST be run with `think:false` (or a large `num_predict` + thinking-channel parsing), or the pipeline's batches silently come back empty and get flagged `empty_response`.

### 3. RAM fit against the shared-server budget

A 7B Q4 model peaks at ~6.1 GiB of host RAM; the 4B models peak at ~4.6–4.8 GiB. Both fit a ~6 GiB LLM allocation on the shared 16 GB server (leaving ~10 GB for OS + frontend + backend + Postgres + OCR). Nothing ≥12B is viable on CPU at usable speed (gemma3:12b: 1.61 tok/s, 224 s/batch).

### 4. Accuracy — NOT measured (the open gap)

- All 14 ground-truth books are `verification_status: unverified` (machine-prefilled from Commons/Wikisource/Internet Archive; see e.g. [`.../Athma-Charitramu/expected_metadata.json`](../backend/tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu/expected_metadata.json)). The prior session stopped for the same reason ("accuracy arm blocked on GT verification").
- The measured sweep above scored only **JSON validity**, not correctness — the harness did not store response values.
- Clean Telugu evaluation text *is* available (`wikisource_gt.json` holds proofread page text, e.g. page 3 of Athma is the title page: title, author, publisher, 1933), and an accuracy bundle + node runner are built and committed-ready (`backend/scripts/make_eval_bundle.py`, `backend/scripts/node_acc.py`).

### 4b. Ground-truth audit (2026-11-11)

A mechanical corroboration pass ([`audit_ground_truth.py`](../backend/scripts/audit_ground_truth.py)) checked whether each prefilled value actually appears in the book's proofread Wikisource text: only **50 of 140** non-null checkable values matched; 90 were not found — mainly because (a) the scaffold stores **Latin transliterations** (e.g. author "Rayasam Venkata Shivudu") while the body is **Telugu script**, and (b) several fields come from **Commons / Internet-Archive metadata** that is not in the book body at all. **Conclusion: the GT is not trustworthy enough for absolute accuracy scoring.** It must be human-verified (or rebuilt from the proofread text) before the accuracy arm is meaningful; a model-vs-model comparison against this same scaffold is still possible but must be reported as **provisional / relative-only**.

**Two books now `verified` (2026-11-11):** `tel/2015.373190.Athma-Charitramu` and `tel/2015.328360.Andhra-Mahaniyulu` — front-matter identity fields (title/label, publisher, place, date, language) checked against their proofread title pages. Athma's `publisher` was corrected from `null` to `ఆంధ్ర పత్రికా ముద్రాలయము`; `author` is kept as the Latin transliteration (source is Telugu script).

### 4c. Accuracy — first measurements (provisional, 2026-11-11)

Method: 2 batches (`core_identity`, `publication`) on the Telugu Athma book, **clean Wikisource front-matter text**, `num_ctx=8192`, `temp=0`, `think:false` for reasoning models, via [`node_acc.py`](../backend/scripts/node_acc.py); scored with [`score_acc.py`](../backend/scripts/score_acc.py) against the now-**verified** Athma GT (§4b). Re-run 2026-11-11 with a hardened runner (`num_predict=1024`, `repeat_penalty=1.1`, `keep_alive`).

| Model | Athma F1 | Andhra F1 | Mean | Notes |
|---|---|---|---|---|
| **`gemma4:e4b` (`think:false`)** | **0.636** | **0.409** | **0.523** | fastest + lightest; correct title/date/publisher/place on both books |
| `qwen3.5:4b` (`think:false`) | 0.545 | 0.273 | 0.409 | runner-up |
| `phi4-mini` (3.8B) | 0.273 | 0.091 | 0.182 | weak on Telugu |
| `hex-1` (4B, Qwen3 finetune) | 0.291 | 0.045 | 0.168 | slowest; mis-read `title`; hallucinated `printer` from the few-shot example |
| `qwen3:4b-instruct-2507` | 0.182 | – | – | Athma only; one batch returned **invalid JSON** |
| `qwen2.5:7b` (current prod) | 0.091 | – | – | Athma only; title only; `publication` all-null |

Both leaders correctly extracted title, publication_date (1933), publisher, place_of_publication (మద్రాసు), language and original_language; `gemma4:e4b` additionally got `label`. The remaining `author` miss is a **GT artifact** (the model returns Telugu script రాయసము వెంకటశివుఁడు; GT stores the Latin transliteration), and the single "hallucination" is `publisher_telugu` — a value the model read from the title page that GT leaves empty.

Takeaway: the current production `qwen2.5:7b` and the `qwen3:4b-instruct-2507` fallback are **both unsuitable** here — the 7B returns almost nothing and the 4B-2507 fails structured output. The two reasoning-capable 4B models **with `think:false`** are the credible extractors. **Provisional winner: `gemma4:e4b` (`think:false`)** — ahead of `qwen3.5:4b` on **both** verified books (mean 0.523 vs 0.409) and fastest/lightest; `phi4-mini` and `hex-1` trail on Telugu. Hindi remains untested (no clean text / verified GT).

**Cross-session reconciliation (2026-11-11):** parallel runs [learnings/006](006-first-real-accuracy.md) and [learnings/010](010-llm-shortlist-benchmark.md) scored a **Hindi** book on `test-node-3` — `phi4-mini` led (F1 0.50) over `qwen3-4b-2507`/`qwen2.5:7b` (0.20). **Neither `gemma4:e4b` nor `qwen3.5:4b` was in that run**, so no single model has yet been tested across both languages. The signal consistent across every session: **precision ≈ 1.0 with very low recall — the limiter is recall, and it tracks OCR quality** (Telugu CER ≈ 0.45, [learnings/004](004-ocr-stage-cer.md)) rather than the model.

**Indic finetunes inherit the thinking trap:** `hex-1` (a Qwen3-4B finetune) also returned empty until `think:false` was set — so that fix must be pinned for any Qwen3-family model, not just base Qwen3.x.

### 5. Decision models (Jev-class)

Confirmed from desk research: decision models (Jev, Kev, JevAlt/Deem) classify into a **fixed option set** and cannot generate free-text field values (title, author, publisher). They are **unsuitable for primary extraction**; the only open CPU-runnable one (Deem-4B) is English-only. **Verdict: out of scope for extraction.**

## Recommendation (provisional — resource arm only)

- **Provisional winner:** **`gemma4:e4b` with `think:false`** — best measured token-F1 (0.636) and the fastest/lightest (182 s / 2 batches, ~1.8 GiB resident). The `think:false` requirement MUST be pinned in the Modelfile/config — the default returns empty output. Needs Ollama ≥0.20.6 / llama.cpp ≥v2.11.
- **Runner-up:** **`qwen3.5:4b` with `think:false`** — F1 0.545, 292 s / 2 batches; its hybrid linear-attention keeps the KV cache small for longer inputs.
- **Not suitable:** `qwen2.5:7b` (current production; F1 0.091) and `qwen3:4b-instruct-2507` (F1 0.182; fails structured JSON).
- **No-go on defaults:** do not ship any thinking-capable model without `think:false` or a bigger output budget.
- **Decision models:** not pursued.

**Final model is NOT locked** — the accuracy arm is the gate and is unmeasured.

## Next steps

1. **Verify metadata GT** (or explicitly mark provisional) for ≥ 2 books per language — the scoring gate. Every field in the scaffolds needs human verification against the PDF/Wikisource index.
2. **Run the accuracy arm** on test-node-2 using the already-built `make_eval_bundle.py` → `node_acc.py` path: `think:false`, grammar-constrained JSON, per batch; score per-field token-F1/exact-match **plus a hallucination rate** (gold-null but model emitted a value).
3. **Then** set the plan's go/no-go and, if positive, change only the `Modelfile FROM` (pin `think:false`, `num_ctx 8192`, `temp 0`) and re-run the real-mode harness.
4. **Stop test-node-2** when the study ends (spend guardrail).
5. **Owner:** dev, with the user owning the GT-verification depth decision and the node-run authorization.

## References

- Plan: [plans/004-llm-model-evaluation.md](../plans/004-llm-model-evaluation.md)
- Measured results: `/tmp/bench-results.jsonl`, `/tmp/followup-results.jsonl` on `test-node-2`
- Harness: [backend/scripts/make_eval_bundle.py](../backend/scripts/make_eval_bundle.py) · [backend/scripts/node_acc.py](../backend/scripts/node_acc.py) · [backend/scripts/bench_llm_extraction.py](../backend/scripts/bench_llm_extraction.py)
- Pipeline: [backend/app/services/llm_service.py](../backend/app/services/llm_service.py) · [backend/app/services/prompts.py](../backend/app/services/prompts.py) · [backend/app/schemas/metadata.py](../backend/app/schemas/metadata.py)
- Node tracker: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
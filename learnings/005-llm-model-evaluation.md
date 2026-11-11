# 005 — LLM Model Evaluation for Metadata Extraction

- **Date:** 2026-11-11
- **Study context:** [plans/004-llm-model-evaluation.md](../plans/004-llm-model-evaluation.md) — select the LLM for the 49-field metadata extraction step under a CPU-only / 16 GB / offline / open-source envelope.
- **Status:** **Resource / speed / JSON-validity arm measured** on the real target node. **Accuracy arm NOT measured** — blocked on metadata ground-truth verification (all 14 GT books are `unverified`) and on authorization to run scoring against the node.

## Summary

On a real 4 vCPU / 16 GB node the **resource arm is complete**: `qwen3:4b-instruct-2507` and `qwen3.5:4b` run at ~½ the RAM and ~1.6× the speed of the current `qwen2.5:7b`; **thinking-capable models must set `think:false`** or they silently return empty output. **First accuracy data (provisional):** on a Telugu book `qwen3.5:4b` (`think:false`) scored token-F1 **0.50** and extracted the correct title, date, place and publisher, while the `qwen2.5:7b` baseline returned **only the title** from the same batch, and `qwen3:4b-instruct-2507` hit a **JSON truncation failure**. **No model is locked** — `qwen3.5:4b` (`think:false`) is the provisional front-runner, pending ground-truth verification.

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

### 4c. Accuracy — first measurements (provisional, 2026-11-11)

Method: 2 batches (`core_identity`, `publication`) on the Telugu Athma book, **clean Wikisource front-matter text**, `think:false`, `num_ctx=8192`, `temp=0`, via [`node_acc.py`](../backend/scripts/node_acc.py); scored with [`score_acc.py`](../backend/scripts/score_acc.py). Ground truth is unverified (§4b), so these are **relative, not absolute**, numbers.

| Model | TP | FP | FN | mean token-F1 | Notes |
|---|---|---|---|---|---|
| `qwen3.5:4b` (`think:false`) | 8 | 2 | 2 | **0.500** | Correct: title, language, original_language, publication_date (1933), place_of_publication (మద్రాసు). The 2 "hallucinations" are `publisher`/`publisher_telugu` values the model read straight from the title page that GT left null; `author` was correct in Telugu script but GT stores Latin transliteration. |
| `qwen2.5:7b` (baseline) | 1 | 0 | — | — | `core_identity` returned only `{"title": "ఆత్మచరిత్రము"}` (34 tokens) in 224 s — correct but very sparse. `publication` batch not captured (run stalled; node went SSH-unresponsive under load). |
| `qwen3:4b-instruct-2507` | — | — | — | — | `core_identity` returned **truncated, unparseable JSON** (`eval_count=512`, repeated text loop) in 421 s. A repetition/truncation failure mode under this prompt; re-run pending. |

Takeaway: on the same Telugu input, **`qwen3.5:4b` extracted 8 fields (F1 0.50), the `qwen2.5:7b` baseline returned only the title, and `qwen3:4b-instruct-2507` failed to emit valid JSON** — the smaller non-thinking 4B is the stronger *extractor* here, and JSON robustness varies sharply by model. GT gaps and script mismatches still dominate the absolute score (the model correctly read the publisher from the title page; GT left it null).

### 5. Decision models (Jev-class)

Confirmed from desk research: decision models (Jev, Kev, JevAlt/Deem) classify into a **fixed option set** and cannot generate free-text field values (title, author, publisher). They are **unsuitable for primary extraction**; the only open CPU-runnable one (Deem-4B) is English-only. **Verdict: out of scope for extraction.**

## Recommendation (provisional — resource arm only)

- **Provisional front-runner:** **`qwen3.5:4b` with `think:false` enforced** — fastest measured (82.6 s/batch vs 172.8 s for the 7B) and the only model on the measured Telugu batch to return the correct title, date, place and publisher (F1 0.50, provisional). The `think:false` requirement MUST be pinned in the Modelfile/config — the default silently returns empty output.
- **Runner-up, with a caveat:** **`qwen3:4b-instruct-2507`** — valid JSON and ~½ the RAM of the 7B in the speed sweep, but it hit a JSON truncation/repetition failure in the accuracy run; re-test before adopting.
- **Keep** `qwen2.5:7b` as the regression baseline (sparse: returned only the title on the measured batch).
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
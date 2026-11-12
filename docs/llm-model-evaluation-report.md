# LLM Model Evaluation — Consolidated Report

**Scope:** every LLM tested for the 49-field metadata extraction step under the CPU-only / 16 GB / offline / open-source envelope. **Consolidates [learnings/005](../learnings/005-llm-model-evaluation.md), [010](../learnings/010-llm-shortlist-benchmark.md), [013](../learnings/013-verified-shortlist-and-ocr.md).** Last updated 2026-11-12.

> **Status: uncontested winner not yet established.** Results are **language-dependent** and were run on small, CPU-only samples. **Cross-language head-to-head (2026-11-12):** `gemma4:e4b` leads **Telugu** (0.523 vs phi4-mini 0.182) but is operationally fragile end-to-end; `phi4-mini` leads **Hindi** (0.333) and is robust — see §6. The implemented default (`phi4-mini`) is the safe pick; `gemma4:e4b` is the Telugu candidate pending tuning.
- Note: the default `--max-tokens` for batches was raised to 1024 to accommodate verbose models; `think:false` is now sent for thinking families.

## 1. Resource / speed / JSON validity — 7-model sweep (test-node-2)

`num_ctx=8192`, `num_predict=512`, `temperature=0`, `format=json`, real Telugu `core_identity` prompt.

| Model | Resident GiB | Host peak (MiB) | Prefill tok/s | Gen tok/s | Wall (s) | JSON valid |
|---|---|---|---|---|---|---|
| qwen2.5:7b (was prod) | 4.72 | 6116 | 9.44 | 2.73 | 172.8 | ✅ |
| qwen3:4b-instruct-2507 | 2.97 | 4557 | 15.61 | 3.34 | 108.9 | ✅ |
| qwen3.5:4b (default) | 2.93 | 4829 | 16.25 | 4.47 | 181.5 | ❌ (0 chars) |
| qwen3.5:4b (`think:false`) | ~4.7 | — | 16.19 | 4.61 | 82.6 | ✅ |
| gemma4:e4b (default) | 1.80 | 7788 | 25.39 | 4.25 | 165.8 | ❌ (0 chars) |
| qwen3:8b | 5.54 | 7306 | 8.58 | 2.06 | 413.4 | ❌ (0 chars) |
| qwen3.5:9b | 5.76 | 10805 | 8.27 | 2.57 | 330.9 | ❌ (0 chars) |
| gemma3:12b | 7.51 | 10367 | 5.66 | 1.61 | 223.9 | ✅ |

## 2. Accuracy — verified Telugu (2 books, clean Wikisource text)

Method: 2 batches (`core_identity`, `publication`), `num_ctx=8192`, `temp=0`, `think:false` for reasoning models; scored against human-verified GT.

| Model | Athma F1 | Andhra F1 | Mean |
|---|---|---|---|
| **gemma4:e4b (`think:false`)** | **0.636** | **0.409** | **0.523** |
| qwen3.5:4b (`think:false`) | 0.545 | 0.273 | 0.409 |
| phi4-mini (3.8B) | 0.273 | 0.091 | 0.182 |
| qwen3:4b-instruct-2507 | 0.182 | – | – |
| hex-1 (4B, Qwen3 finetune) | 0.291 | 0.045 | 0.168 |
| qwen2.5:7b (was prod) | 0.091 | – | – |

Both leaders got title, publication_date, publisher, place, language; the residual `author` miss is a GT artifact (Latin transliteration vs Telugu-script body).

## 3. Accuracy — Hindi shortlist (end-to-end harness)

| Run | Books | phi4-mini | qwen3-4b-instruct-2507 | qwen2.5:3b | qwen2.5:7b |
|---|---|---|---|---|---|
| 010 (unverified GT) | 1 | **0.50** | 0.20 | 0.31 | 0.20 |
| 013 (verified GT) | 2 | **0.333** | 0.106 | — | — |

## 4. Measured Ollama RAM (ctx 4096, CPU)

| Model | Loaded |
|---|---|
| qwen2.5:7b | 4.83 GiB |
| qwen3-4b-instruct-2507 | 3.38 GB |
| phi4-mini | ~2.5 GB (file) |
| gemma4:e4b | ~1.8 GiB |

All ≤4B models fit the **6 GiB** oki cap with headroom; 7B is snug.

## 5. Cross-cutting findings

1. **Thinking trap (load-bearing).** `qwen3:8b`, `qwen3.5:9b`, and the **defaults** of `qwen3.5:4b` and `gemma4:e4b` return **0 content chars** (budget spent on the thinking channel). **Any thinking-capable model MUST run with `think:false`.** This applies to Qwen3 finetunes (`hex-1`) too. Implication: an `invalid-JSON`/`empty` verdict for a Qwen3-familiy model may just be a missing `think:false`, not a bad model.
2. **Recall is the limiter, not the model.** Across every run: precision ≈ 1.0 with very low recall — the models emit few fields, and it tracks **OCR quality** (Telugu CER ≈ 0.45, [004](../learnings/004-ocr-stage-cer.md)). Swapping models cannot exceed the OCR ceiling.
3. **Language-dependent results.** gemma4:e4b leads **Telugu**; phi4-mini leads **Hindi**. No single model has been tested on **both** languages with verified GT.
4. **Two now-fixed extraction bugs** ([013](../learnings/013-verified-shortlist-and-ocr.md)) confounded earlier numbers: schema-class echo (`title="CoreIdentityBatch"`) and over-nulling.

## 6. Cross-language head-to-head (executed 2026-11-12)

Attempted on `test-node-3` with the end-to-end harness (`--max-tokens 1024`):

| Language | Books | gemma4:e4b (`think:false`) | phi4-mini |
|---|---|---|---|
| Telugu (005 clean-text method) | 2 | **0.523** | 0.182 |
| Hindi (end-to-end harness) | 2 | *incomplete* | **0.333** |

**gemma4:e4b was operationally fragile end-to-end** — it kept exceeding the output budget (truncation at 1024 tokens → instructor retries), so a clean harness number could not be produced; this is the same "thinking trap" as 005 (defaults return empty/overlong). Its Telugu lead (0.523) came from the 005 clean-text runner with `think:false` + `num_predict=1024` + `repeat_penalty=1.1`. **phi4-mini is robust** under the harness and leads Hindi.

**Conclusion:** gemma4:e4b is the stronger **Telugu** extractor but needs tuning (`think:false` + a larger output budget) to deploy; **phi4-mini is the safe, robust default** and leads **Hindi**. They are complementary, not interchangeable. `think:false` support is now wired into the service ([llm_service.py](../backend/app/services/llm_service.py), thinking families only) and the harness gained `--max-tokens`.

## 7. Decision & recommendation

- **Implemented default: `phi4-mini`** (PR `964d5af`) — the Hindi leader, MIT, ~2.5 GB, fits the cap. Deploy via Dokploy (`docker/Modelfile.phi4-mini`, `OLLAMA_PRELOAD_MODEL=phi4-mini`).
- **Caveat / likely better overall pick for Telugu: `gemma4:e4b` (`think:false`)** — best measured Telugu F1 (0.523) and lightest/fastest. **Recommend a cross-language head-to-head (gemma4:e4b vs phi4-mini, ≥2 verified books per language) before finalising.**
- **Do not use:** `qwen2.5:7b` (near-empty output) or any thinking model without `think:false`.
- Re-run the [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) harness `--ground-truth` after fixing OCR and the extraction bugs, so model deltas aren't swamped by recall loss.

## 8. Reproduce

```bash
# resource/speed/JSON: node_acc.py / bench_llm_extraction.py on test-node-2
# end-to-end accuracy: test-node-3
uv run python -m scripts.evaluate_extraction --ground-truth --limit 2 --pages 6 --model <model>
```

Reports: `backend/reports/gt-bench-*.json`, `backend/reports/gt-verified-*.json`, `backend/reports/ocr-tessdata-best.json`.

## References

- [learnings/005 — LLM Model Evaluation](../learnings/005-llm-model-evaluation.md) · [plans/004](../plans/004-llm-model-evaluation.md)
- [learnings/010 — Shortlist Benchmark](../learnings/010-llm-shortlist-benchmark.md) · [learnings/013 — Verified Shortlist & OCR](../learnings/013-verified-shortlist-and-ocr.md)
- [learnings/004 — OCR CER](../learnings/004-ocr-stage-cer.md) · [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
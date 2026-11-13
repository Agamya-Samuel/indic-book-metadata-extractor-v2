# 018 — LLM Configuration Validation: Parameter Matrix on Verified Telugu Books

- **Date:** 2026-11-12
- **Study context:** Executes the validation matrix designed in [learnings/017](017-llm-configuration-research.md) §9.2, to confirm or overturn each element of the provisional configuration profile. Run on GCP `test-node-2` (4 vCPU / 15.62 GiB, **no swap**, CPU-only), the profile of the production host.
- **Status:** Complete — **32/32 calls**. Node **stopped** after the run (spend guardrail); the tracker row is updated.
- **Inputs:** 2 verified Telugu books — `tel/2015.373190.Athma-Charitramu`, `tel/2015.328360.Andhra-Mahaniyulu` — batches `core_identity` + `publication` (18 of the 49 fields), prompts built by `make_eval_bundle.py` from **proofread Wikisource page text**.
- **Models:** `gemma4:e4b` (`think:false`) and `phi4-mini` (3.8B). **Runtime:** Ollama 0.40.16 in Docker, CPU-only.

## Summary

`gemma4:e4b` (`think:false`) dominates on Telugu — **F1 0.82 (Andhra) / 0.73 (Athma)**, 2/2 valid JSON in every profile — while `phi4-mini` trails badly (**0.35 / 0.44**) and **looped into invalid JSON on one batch**. Context 4096 and 8192 gave byte-identical output; temperature 0 reproduced exactly across seeds; `repeat_penalty` 1.1 did not help and slightly hurt; 4 threads did not help. The largest operational lever is **prompt-prefix caching (~4× faster repeats)**. No memory pressure: `MemAvailable` never fell below ~2.8 GiB.

## Method (reproduce)

```bash
# local: build the offline bundles
cd backend
.venv/bin/python -m scripts.make_eval_bundle --book tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu \
    --batches core_identity,publication --output /tmp/bundle_athma.json
.venv/bin/python -m scripts.make_eval_bundle --book tests/fixtures/ground_truth/tel/2015.328360.Andhra-Mahaniyulu \
    --batches core_identity,publication --output /tmp/bundle_andhra.json
gcloud compute scp --zone=asia-south1-c scripts/node_cfg.py scripts/run_matrix.sh test-node-2:~/
# on the node
nohup bash ~/run_matrix.sh > /tmp/matrix.log 2>&1 &
nohup bash ~/memwatch.sh  > /tmp/pressure.log 2>&1 &   # 5 s MemAvailable sampler
# local: score every configuration with the repo validator
.venv/bin/python -m scripts.summarize_cfg --jsonl /tmp/cfg.jsonl \
    --bundle /tmp/bundle_athma.json --bundle /tmp/bundle_andhra.json
```

`node_cfg.py` runs the real per-batch prompt through `/api/chat` and records wall time, generated/prefill tok/s, per-call minimum `MemAvailable`, and the parsed JSON. Scoring reuses `extraction_validator.evaluate_book`, so the numbers are directly comparable with 005/006/010/013. A **hallucination** is a field predicted present while the (source-verified) GT has it absent.

## Results (32 calls; `wall_s` = both batches)

| Tag | Variable under test | Model | Book | JSON ok | wall s | gen tok/s | P | R | F1 | tok-F1 | halluc | non-null |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gem_base` | baseline (8192, t0, rep1.0, schema, 3 thr) | gemma4:e4b | Andhra | 2/2 | 154.3 | 5.55 | 0.82 | 0.82 | **0.82** | 0.46 | 2/38 | 11 |
| `gem_base` | baseline | gemma4:e4b | Athma | 2/2 | 149.3 | 5.60 | 0.73 | 0.73 | **0.73** | 0.64 | 3/38 | 11 |
| `gem_seed7` | seed 7 (determinism) | gemma4:e4b | Andhra | 2/2 | 39.7 | 5.61 | 0.82 | 0.82 | 0.82 | 0.46 | 2/38 | 11 |
| `gem_seed7` | seed 7 | gemma4:e4b | Athma | 2/2 | 34.6 | 5.73 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `gem_temp03` | temperature 0.3 | gemma4:e4b | Andhra | 2/2 | 36.9 | 5.50 | 0.90 | 0.82 | 0.86 | 0.46 | 1/38 | 10 |
| `gem_temp03` | temperature 0.3 | gemma4:e4b | Athma | 2/2 | 34.2 | 5.77 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `gem_rep11` | repeat_penalty 1.1 | gemma4:e4b | Andhra | 2/2 | 41.7 | 5.34 | 0.80 | 0.73 | 0.76 | 0.46 | 2/38 | 10 |
| `gem_rep11` | repeat_penalty 1.1 | gemma4:e4b | Athma | 2/2 | 34.7 | 5.68 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `gem_json` | JSON mode (no schema) | gemma4:e4b | Andhra | 2/2 | 39.8 | 5.59 | 0.82 | 0.82 | 0.82 | 0.46 | 2/38 | 11 |
| `gem_json` | JSON mode (no schema) | gemma4:e4b | Athma | 2/2 | 34.1 | 5.79 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `gem_thr4` | num_thread 4 | gemma4:e4b | Andhra | 2/2 | 154.0 | 4.67 | 0.82 | 0.82 | 0.82 | 0.46 | 2/38 | 11 |
| `gem_thr4` | num_thread 4 | gemma4:e4b | Athma | 2/2 | 143.3 | 4.77 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `gem_ctx4096` | num_ctx 4096 | gemma4:e4b | Andhra | 2/2 | 154.3 | 5.52 | 0.82 | 0.82 | 0.82 | 0.46 | 2/38 | 11 |
| `gem_ctx4096` | num_ctx 4096 | gemma4:e4b | Athma | 2/2 | 150.1 | 5.45 | 0.73 | 0.73 | 0.73 | 0.64 | 3/38 | 11 |
| `phi4_base` | baseline | phi4-mini | Andhra | **1/2** | 286.5 | 3.40 | 0.50 | 0.27 | **0.35** | 0.27 | 3/38 | 6 |
| `phi4_base` | baseline | phi4-mini | Athma | 2/2 | 180.3 | 3.75 | 0.57 | 0.36 | **0.44** | 0.36 | 3/38 | 7 |

## Findings

**1. Model: `gemma4:e4b` (`think:false`) is the Telugu extractor; `phi4-mini` is not.** F1 0.82/0.73 vs 0.35/0.44 — and phi4-mini was both slower (3.4–3.75 tok/s vs 5.5–5.8) and less reliable (one invalid-JSON batch). This reproduces [005](005-llm-model-evaluation.md) on Telugu and stands in contrast to [013](013-verified-shortlist-and-ocr.md), where phi4-mini led on a **Hindi** book. The language split is real: **there is still no single model measured across both languages on verified GT.**

**2. Context 4096 vs 8192: identical.** Same 11 non-null fields, same F1, same hallucinations on both books; wall time within noise (154.3/150.1 vs 154.3/149.3). The measured prompt is ≤1.34 K tokens, so 4096 is sufficient — adopt **4096** as the default and keep 8192 only as headroom.

**3. Temperature 0 is deterministic; 0.3 is not.** With temperature 0 the seed-42 and seed-7 runs were **byte-identical on both books** (differing fields: none) — determinism proven, which is what a human review trail needs. Temperature 0.3 moved one book's F1 0.82 → 0.86 (fewer hallucinations: 1 vs 2, but one fewer field emitted) and left the other unchanged: no consistent gain, and it forfeits reproducibility. **Keep temperature 0.**

**4. `repeat_penalty` 1.1 does not help.** It slightly degraded Andhra (F1 0.76 vs 0.82, non-null 11 → 10) and changed nothing on Athma. The hypothesis in [017](017-llm-configuration-research.md) §2.2 — that a penalty on repeated `null` tokens pushes the model toward invention — is consistent with this direction of travel. **Keep 1.0.**

**5. Schema-constrained decoding adds no accuracy here — and does not prevent a loop.** `gem_json` (Ollama `format=json`) produced output **identical** to `gem_base` (`format=<json-schema>`) on both books at temperature 0. More importantly, schema-constrained mode did **not** save `phi4-mini`: its Andhra `core_identity` batch returned 1029 chars of a repeated string (`"subtitle": "ఆంధ్రమహనీయులు - ఆంధ్రమహనీయులు - …"`) truncated at the `num_predict` cap → **invalid JSON despite the grammar**. Grammar constrains *shape*, not *stopping*. Conclusion: keep the schema (it is cheap and helps weaker models stay on-format), but add an explicit **repetition/loop guard** (detect a repeated n-gram and retry that batch) rather than trusting `format` alone.

**6. Threads 3 vs 4: no gain.** 154.0 / 143.3 s at 4 threads vs 149.3 / 154.3 s at 3 threads — within noise. **Keep 3**, leaving a core for the web/DB/OCR workload, consistent with [015](015-service-inventory-and-gating.md).

**7. Prompt-prefix caching is the biggest speed lever (~4×).** Identical-config consecutive calls dropped from ~150 s to ~35 s per book (prefill reported at >2000 tok/s because only the *uncached* tokens were counted, `prompt_eval_cached_count`). Changing `num_ctx` or `num_thread` evicts the runner and restores the ~150 s cold cost — visible in the table as the 150 s rows for `gem_ctx4096` and `gem_thr4`. Two consequences: (a) keep ctx/threads **stable** in production so the shared system-prompt/template prefix stays cached; (b) the "prefill tok/s" figure is only meaningful on a cold call — the cached numbers are an artifact.

**8. Memory: no pressure.** Both models stayed resident; combined `llama-server` RSS peaked at **10 992 MiB**, and host `MemAvailable` never fell below **3394 MiB** (5 s sampler) / **2812 MiB** (per-call sampler) — the pressure watcher never fired. The 6 GiB Ollama cap is validated for a 4B-class model alongside a 7B. Caveat: the 5 s sampler understates instantaneous troughs, the instrument lesson from 015.

## Limitations

- **Telugu only.** Hindi has no proofread source, so it was not exercised here; Hindi accuracy remains what 010/013 measured on OCR input.
- **Input is proofread Wikisource text, not raw Tesseract output.** With production CER ~0.42–0.45 ([004](004-ocr-stage-cer.md)), these F1s are an **upper bound** on real recall — the production limiter is still OCR.
- **2 books, 2 batches** (18 of 49 fields), one seed per profile except the determinism pair.
- GT is *source*-verified; the Roman-vs-Telugu transliteration artifacts noted in 005/013 remain (they depress `author` F1 for both models).

## Recommendations (deltas to 017)

Unchanged and now evidence-backed: **temperature 0**, pinned `seed`, **`repeat_penalty` 1.0**, `num_predict` 512, **3 threads**, 1 parallel, `keep_alive` 30 m, 6 GiB cap, `MAX_OCR_CHARS` 2500, `think:false`.

Changed:
- **`num_ctx` → 4096 by default** (8192 acceptable). No accuracy cost measured; halves KV versus 8192.
- **Add a repetition/loop guard** — do not rely on `format` alone (finding 5). A repeated-substring check that re-runs the batch is the minimum.
- **Unify app `max_tokens` to 512** (the 256/512 mismatch in 017 §1).
- **Model:** `gemma4:e4b` (`think:false`) for Telugu; keep `phi4-mini` only where Hindi dominates — and it must have the loop guard.

## Next steps

1. Re-run the matrix on **Hindi** (needs `hin` tessdata or a proofread source) to close the cross-language gap.
2. Implement the loop guard and re-measure `phi4-mini` on the same bundles.
3. Fold the 4096 decision + the guard into [plans/004](004-llm-model-evaluation.md) and the Modelfiles.
4. Keep the app's `MAX_PARALLEL_BATCHES` and Ollama's `NUM_PARALLEL` consistent (currently 2 vs 1).

## References

- Probe/plan: [learnings/017](017-llm-configuration-research.md) · [plans/004](004-llm-model-evaluation.md)
- Harness: [node_cfg.py](../backend/scripts/node_cfg.py) · [run_matrix.sh](../backend/scripts/run_matrix.sh) · [summarize_cfg.py](../backend/scripts/summarize_cfg.py) · [memwatch.sh](../backend/scripts/memwatch.sh) · [make_eval_bundle.py](../backend/scripts/make_eval_bundle.py)
- Prior: [004](004-ocr-stage-cer.md) · [005](005-llm-model-evaluation.md) · [006](006-first-real-accuracy.md) · [010](010-llm-shortlist-benchmark.md) · [013](013-verified-shortlist-and-ocr.md) · [015](015-service-inventory-and-gating.md)
- Node: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md) (`test-node-2`, stopped after the run)

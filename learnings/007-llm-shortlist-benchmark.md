# 007 — LLM Shortlist Benchmark (49-field extraction) + Ollama RAM footprint

- **Date:** 2026-11-11
- **Context:** Following [learnings/006](006-first-real-accuracy.md) and the oki capacity review. Ran on **GCP `test-node-3`** (heavy testing stays off the local PC), and pulled the model shortlist recommended for the ~6 GiB prod budget.
- **Artifacts:** run reports `backend/reports/gt-bench-*.json`; harness [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py); tracker [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md).

## Method

On `test-node-3` (4 vCPU, 16 GB, CPU-only), for each model:
```
uv run python -m scripts.evaluate_extraction --ground-truth --include-unverified \
    --limit 1 --pages 4 --model <model> --output /tmp/bench-<model>.json
```
Same book for every model: `hin/1913_Ummed_Singh_Charitra_Hindi_PDF`. 8 batches/book → 8 LLM calls.

**Bug fixed first:** the harness hardcoded `language="tel"` for OCR + extraction, so **Hindi books were being OCR'd with the Telugu model** (garbage in). It now reads each book's language from its GT envelope. Earlier Hindi numbers (learnings/006) were confounded by this.

## Results (1 Hindi book, 4 pages, unverified GT)

| Model | P | R | F1 | RAM loaded (ctx 4096) |
|---|---|---|---|---|
| **phi4-mini (3.8B)** | 1.00 | 0.333 | **0.500** | ~2.5 GB |
| qwen2.5:3b | 0.50 | 0.222 | 0.307 | ~2.0 GB |
| qwen3-4b-instruct-2507 | 1.00 | 0.111 | 0.200 | **3.38 GB (measured)** |
| qwen2.5:7b | 1.00 | 0.111 | 0.200 | 4.83 GiB (measured on oki) |

Correct fields: phi4-mini → `title`, `pages`, `publication_date`; qwen3-4b / qwen2.5:7b → only `publication_date`.

## Key findings

- **phi4-mini (3.8B) led on this sample** (F1 0.50) and is the smallest of the leaders — consistent with the exa research (it's explicitly trained for function-calling/JSON). It beat the previously-recommended `qwen3-4b-instruct-2507` (0.20 here).
- **Every model shows P≈1.0 with very low recall** — when they emit a value it is usually right, but they extract few fields. This is a **recall/extraction** problem (rough OCR evidence, small models), not precision.
- **Measured Ollama RAM (ctx 4096):** Qwen3-4B ≈ **3.38 GB** (`llama-server` RSS); qwen2.5:7b ≈ 4.83 GiB. Host `used` peaked ~4.0 GB with the 4B, `avail` never below 11.6 GB. So a 4B comfortably fits the ~6 GiB prod cap (>2 GB headroom); a 7B is snug.
- **Speed is the real constraint on CPU:** ~2–2.5 min per batch call on 4 vCPU → ~15–20 min per book. This makes multi-model, multi-book benchmarks expensive (this 4-model × 1-book run took ~1.5 h).

## Caveats (all limit confidence)
- **One book, 4 pages, unverified GT** — a directional signal only, not a verdict.
- The GT is prefilled/unverified; recall may be underestimated if GT has values the scan lacks.
- LLM cost is serial per book on CPU; results aren't throughput measurements.

## Recommendation

1. **Re-test `phi4-mini` and `qwen3-4b-instruct-2507` on ≥5 verified books** before choosing — this sample contradicts the earlier 4B-Qwen recommendation.
2. **Keep 4B-class at ctx 4096** for the oki deployment (~3–3.5 GB); the ~6 GiB cap is comfortable.
3. **Fix recall upstream:** the low recall tracks OCR quality (learnings/004) — improve OCR before expecting model swaps to help.
4. Enforce **JSON schema + recovery** regardless of model (small models emit non-parseable JSON).

## Next steps

- Verify GT, then re-run the shortlist with `--verified-only` on a larger book set.
- Add a smaller `--pages` default or a page-allowlist to cut CPU cost for sweeps.
- Test `phi4-mini` in the prod (`oki`) container to confirm the ~2.5 GB footprint there.

## References

- Reports: `backend/reports/gt-bench-{phi4-mini,qwen2.5-3b,qwen2.5-7b,qwen3-4b-instruct-2507}.json`
- Model research (exa): Qwen3-4B-Instruct-2507 (non-thinking), Phi-4-mini, Sarvam-1 (non-commercial)
- Prior: [learnings/006](006-first-real-accuracy.md) · [learnings/004](004-ocr-stage-cer.md) · [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)
# 006 — First Real End-to-End Accuracy (GT corpus, `qwen2.5:3b`, GCP node)

- **Date:** 2026-11-11
- **Context:** Heavy evaluation run on **GCP `test-node-3`** (per [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md) — no heavy loads on the local PC). Runs the repaired harness end-to-end (render → OCR → hybrid extraction) against the ground-truth corpus and scores it.
- **Command (on node):** `uv run python -m scripts.evaluate_extraction --ground-truth --include-unverified --limit 8 --model qwen2.5:3b --output /tmp/gt-node.json`
- **Report:** `backend/reports/gt-eval-qwen2.5-3b.json`

## Summary

**Micro precision 0.340, recall 0.281, F1 0.308** across 8 books (5 Hindi, 3 Telugu); macro token-F1 0.014. This is the first real multi-book accuracy number for the pipeline (previous values were the stub's 1.0-by-construction). Cheap/structured fields carry the score; name/text fields are precise but miss most values.

## Per-field (presence-based P/R/F1, support = GT-present)

| Field | P | R | F1 | n |
|---|---|---|---|---|
| publisher | 0.75 | 1.00 | **0.86** | 3 |
| publication_date | 0.71 | 0.83 | **0.77** | 6 |
| pages | 0.50 | 1.00 | 0.67 | 3 |
| form_of_creative_work | 0.50 | 0.33 | 0.40 | 3 |
| language | 1.00 | 0.25 | 0.40 | 8 |
| label | 1.00 | 0.14 | 0.25 | 7 |
| title | 1.00 | 0.14 | 0.25 | 7 |
| author | 1.00 | 0.13 | 0.22 | 8 |
| original_language | 1.00 | 0.13 | 0.22 | 8 |
| description_work | 0.00 | 0.00 | 0.00 | 8 |
| place_of_publication | 0.00 | 0.00 | 0.00 | 2 |
| editor | 0.00 | 0.00 | 0.00 | 1 |

**Overall:** micro P 0.340 · R 0.281 · F1 0.308 · macro token-F1 0.014

## Key findings

- **Structured/cheap fields work** (`publisher`, `publication_date`, `pages`, F1 0.67–0.86) — the regex/dictionary tier-1 plus easy LLM fields. These are the ones to keep rule-based.
- **Name/text fields are precise but miss most instances**: `author`, `title`, `label`, `language`, `original_language` all have **P = 1.0 but R ≈ 0.13** — when the pipeline emits a value it is usually right, but for most books it emits nothing. That is a **recall** problem (extraction not firing / OCR evidence missing), not a precision problem.
- **`description_work` never resolves** (F1 0.00 on 8 books) despite being widely present in GT. Worth a targeted prompt/field look.
- **The low micro F1 tracks the OCR bottleneck.** With Telugu CER ≈ 0.45 (learnings/004), the LLM sees corrupted evidence, so recall collapses. This run is consistent with that.
- **Caveats:** GT is **prefilled/unverified** (learnings/002–003), so treat these as *provisional*; only 8 books; Hindi-heavy; a small 3B model; the local 2-book run with `qwen2.5:0.5b` scored micro-F1 0.513 on two (easier) Hindi books, so model/book mix matters.

## Recommendation

1. **Do not chase micro-F1 yet.** The binding constraints are (a) OCR quality (CER ~0.45) and (b) recall on name/text fields.
2. **Verify the GT** (the fields above are the ones to spot-check first) so the numbers become defensible.
3. **Keep the tier-1 regex path** for structured fields — it is the strongest part.
4. Re-run the same command with a larger model (e.g. `qwen2.5:7b`) once GT is verified, for a model-vs-model read.

## Next steps

- Human-verify GT (unblocks the accuracy arm); then re-run `--verified-only`.
- Investigate `description_work` (0 F1) and the low-recall name/text fields.
- Attribute OCR vs LLM: score the LLM on verified Wikisource text (bypass OCR) for the same books.

## References

- Report: `backend/reports/gt-eval-qwen2.5-3b.json`
- Harness: [evaluate_extraction.py](../backend/scripts/evaluate_extraction.py) · Validator: [extraction_validator.py](../backend/app/services/extraction_validator.py)
- Node: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md) (`test-node-3`)
- Prior: [learnings/004](004-ocr-stage-cer.md) · [learnings/003](003-harness-and-wikisource-scaling.md)
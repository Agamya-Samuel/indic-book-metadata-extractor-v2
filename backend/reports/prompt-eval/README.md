# Prompt-evaluation reports

One JSON per `(variant, track)`, written by `scripts/prompt_eval/score_eval.py`,
plus `registry.json` (one experiment record per run), `variants.md` (every
prompt verbatim) and `leaderboard.<track>.md`.

Nothing here is committed until a real run has produced it. Stub or synthetic
scores must never be mistaken for extraction accuracy.

Re-run everything with:

```sh
cd backend
python -m scripts.prompt_eval.build_corpus --track both
python -m scripts.prompt_eval.build_mask --track ocr
python -m scripts.prompt_eval.build_fewshot --track ocr
python -m scripts.prompt_eval.build_bundles --stage 1 --track ocr
python3 scripts/prompt_eval/run_eval.py --bundles prompt_eval/bundles/*.ocr.jsonl --out results/ocr.jsonl
python -m scripts.prompt_eval.score_eval --results results/ocr.jsonl --track ocr
python -m scripts.prompt_eval.compare --track ocr
```

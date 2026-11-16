# Benchmarks

Measured **outputs**: OCR and LLM evaluation results, prompt-experiment reports, and host profiles.
Inputs live in [`../datasets/`](../datasets/); the scripts that produce these files live in
`backend/scripts/`.

These files are evidence, not configuration. Nothing reads them at runtime — they exist so a reported
number can be traced back to the run that produced it.

---

## Layout

```text
benchmarks/
├── reports/
│   ├── gt-eval-*.json           Per-book extraction evaluation
│   ├── gt-bench-*.json          Shortlist model benchmarks
│   ├── gt-verified-*.json       Verified ground-truth sets
│   ├── ocr-*.json               OCR engine, preprocessing, and font matrices
│   ├── llm-config-matrix*       Parameter sweeps
│   ├── pipeline-profile-oki.json  Host memory and timing profile
│   ├── e2e-*.json               End-to-end run output
│   └── gt-review-queue.csv      Unverified values awaiting human review
└── prompt-eval/
    ├── README.md                Report format
    └── variants.md              Prompt variant catalogue
```

---

## Producing a report

```bash
cd backend
uv run python -m scripts.evaluate_extraction --help
uv run python -m scripts.eval_ocr --help
uv run python -m scripts.bench_llm_extraction --help
```

Prompt experiments write to `benchmarks/prompt-eval/` via `REPORT_ROOT` in
`backend/scripts/prompt_eval/common.py`:

```bash
make prompt-eval prompt-report
```

---

## Reading a number

Before quoting any figure, check the track (presence vs value), the masks applied, the book count and
language, and whether the model is the one production uses. The full checklist is in
[docs/testing/evaluation.md](../docs/testing/evaluation.md).

Reports accumulate deliberately: an old result is the evidence for an old decision. Do not overwrite a
report to "refresh" it — write a new one.

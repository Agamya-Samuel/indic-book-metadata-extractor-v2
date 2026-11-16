# Datasets

Evaluation and test data for the Indic Book Metadata Extractor. This directory holds **inputs** —
ground truth, sample books, and the frozen evaluation corpus. Benchmark **outputs** live in
[`../benchmarks/`](../benchmarks/).

Nothing here is imported by the application at runtime. These files are consumed by evaluation and
harness scripts under `backend/scripts/`.

---

## Layout

```text
datasets/
├── ground-truth/
│   ├── hin/                 Hindi books: expected_metadata.json, Wikisource text, PDFs
│   ├── tel/                 Telugu books: same structure
│   ├── splits/              Evaluation split definitions
│   ├── manifest.jsonl       Per-book index (slug, language, status)
│   └── README.md            Corpus description and provenance
├── samples/
│   ├── eng/                 Small generated PDFs used by scripts and smoke tests
│   ├── hin/
│   ├── tel/
│   └── bilingual/
└── evaluation/
    ├── corpus/              Frozen OCR + clean page text (byte-identical inputs)
    ├── masks/               Per-field visibility masks for scoring
    ├── fewshot/             Held-out real exemplars for prompt profile V11
    ├── manifest.json        Per-book SHA256, coverage, few-shot holdout list
    └── bundles/             Generated; gitignored
```

---

## What is committed, and what is not

| Asset | Committed | Why |
| --- | --- | --- |
| `expected_metadata.json`, `wikisource_gt.json` | **yes** | Small, and required for reproducibility |
| `.pdf` originals | **no** | Hundreds of MB; re-fetched on demand (see `.gitignore`) |
| `evaluation/corpus`, `masks`, `fewshot` | **yes** | Frozen inputs — a moving corpus invalidates comparisons |
| `evaluation/bundles*` | **no** | Rebuildable in one command |

---

## Regenerating

Run from the repository root. Most scripts live in `backend/` and are invoked as modules.

```bash
# Ground-truth PDFs and metadata
cd backend
uv run python -m scripts.fetch_from_wikisource --help
uv run python -m scripts.enrich_ground_truth --help
uv run python -m scripts.verify_ground_truth --help

# Sample PDFs
uv run python -m scripts.generate_sample_pdf --help

# Evaluation corpus, masks, few-shot exemplars
cd .. && make prompt-corpus prompt-mask prompt-fewshot
```

Each script resolves its default root to `datasets/` — see
`backend/scripts/prompt_eval/common.py` for the canonical constants.

---

## Provenance and licensing

Ground truth is derived from public-domain and CC-licensed sources: Wikisource, Wikimedia Commons,
Internet Archive, and catalogue records (Open Library, Wikimedia Commons). Book PDFs are **not**
redistributed here; only derived metadata and reference text are committed.

Before adding a book, confirm its licence permits use and record the source in `ground-truth/README.md`.

---

## Related documentation

- [Evaluation methodology](../docs/testing/evaluation.md)
- [Testing strategy](../docs/testing/strategy.md)
- [Decisions index](../docs/architecture/decisions.md) — which study produced which corpus

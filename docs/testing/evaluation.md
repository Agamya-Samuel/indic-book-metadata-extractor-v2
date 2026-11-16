# OCR and LLM Evaluation

Quality is measured, not asserted. This document explains the corpora, the metrics, the harnesses,
and how to read a result without fooling yourself.

- Scoring: `backend/app/services/extraction_validator.py`
- Scripts: `backend/scripts/`
- Prompt harness: `backend/scripts/prompt_eval/`, `backend/prompt_eval/`
- Reports: `backend/reports/`

---

## 1. Two tracks that must not be confused

| Track | Question | Metrics |
| --- | --- | --- |
| **Presence** | Did the model fill the field at all? | `tp`/`fp`/`fn`, micro precision/recall/F1, per-field F1 |
| **Value** | Is the value correct? | `field_level_accuracy`, value precision/recall/F1 |

A model that fills every field with plausible garbage scores well on presence and badly on value. The
historical reports (`gt-eval-*`) measured presence; value scoring came later precisely because presence
overstated quality.

Both are reported. Quote the one you mean.

---

## 2. Masks

Not every ground-truth field is extractable from the supplied text. Scoring them as misses blames the
prompt for something it cannot fix.

| Mask | Meaning | Scored? |
| --- | --- | --- |
| `visible` | In the text the model was given | Yes — must be extracted |
| `absent` | Not in the text | Yes — a value is a hallucination |
| `unroutable` | In the book, but outside this batch's page window | **No** — a routing defect |
| `not_in_scan` | Nowhere in the cached text (usually catalogue-derived) | **No** |
| `script_mismatch` | Ground truth in a different script from the scan | **No** |

`unroutable` is the important one: it separates "the prompt failed" from "the batch was never shown
that page". Masks are built by `scripts/prompt_eval/build_mask.py`.

---

## 3. Ground truth

The corpus is derived from Wikisource, Wikimedia Commons, Internet Archive and catalogue data, then
verified.

| Script | Purpose |
| --- | --- |
| `fetch_from_wikisource.py`, `fetch_wikisource_gt.py` | Pull source text and page structure |
| `fetch_commons_ground_truth.py` | Commons-sourced records |
| `enrich_ground_truth.py`, `enrich_catalogues.py` | Fill gaps from catalogues |
| `verify_ground_truth.py` | Human-verification pass |
| `audit_ground_truth.py` | Structural/consistency audit |
| `gt_coverage_report.py` | Field coverage per book |
| `gt_review_queue.py` | Emit a review queue for unverified values |

Verification matters: values flagged `prefilled_needs_verification` are excluded from scoring, so the
model is never graded against its own earlier output.

---

## 4. OCR evaluation

```bash
cd backend
uv run python scripts/eval_ocr.py --help
uv run python scripts/test_ocr_accuracy.py --help
```

Metrics:

| Metric | Meaning |
| --- | --- |
| **CER** | Character error rate against reference text |
| **Word accuracy** | Token-level match |
| **Coverage** | `word_count / detected_lines` — a dropped-line signal |
| **Average confidence** | Mean word confidence (line model reports a fixed stand-in) |

Reference text is Wikisource-derived, so it reflects a *different transcription* of the same page.
Some CER is transcription variation, not OCR error. Compare variants against each other, not against
zero.

Reproduce the OCR corpus through the same path production uses (`process_page_image`) — the frozen
corpus previously diverged by skipping post-processing, which invalidated comparisons.

---

## 5. LLM evaluation

```bash
cd backend
uv run python scripts/eval_model.py --help
uv run python scripts/evaluate_extraction.py --help
uv run python scripts/bench_llm_extraction.py --help
```

Scoring produces, per book and overall:

| Output | Definition |
| --- | --- |
| `exact_match_rate` | Value identical after light normalisation |
| `normalized_match_rate` | Diacritics stripped, case-folded, whitespace collapsed |
| `token_f1` | Token overlap F1 |
| `fuzzy_match` | Token F1 ≥ 0.80 or char ratio ≥ 0.85 — free-text fields only |
| `field_level_accuracy` | Share of visible fields with a correct value |
| `hallucination_rate` | Non-null predictions where the field is absent |
| `missing_field_detection_accuracy` | Absent fields correctly left null |

### Exact-only fields

These never receive fuzzy credit, because a truncated year or one wrong ISBN digit is a wrong answer:

`isbn`, `pages`, `publication_date`, `edition_number`, `volume`, `serial_number_in_series`,
`part_of_the_set`, `inception`.

---

## 6. Uncertainty

Small corpora produce unstable means. The evaluator provides:

- `bootstrap_ci(values)` — percentile bootstrap over **books**, the independent unit.
- `paired_delta_ci(baseline, variant)` — bootstrap of the per-book difference, which controls for some
  books being harder than others.

Verdict policy is deliberately conservative:

| Verdict | Condition |
| --- | --- |
| `better` | Interval lower bound > 0 |
| `worse` | Interval upper bound < 0 |
| `inconclusive` | Interval contains zero |
| `insufficient-data` | Fewer than 2 shared books |

With one book, the interval collapses to the point estimate and says `n=1` rather than inventing a
range.

---

## 7. Prompt evaluation harness

The `prompt-*` Make targets drive a staged experiment across prompt profiles `V00`–`V12`:

```bash
make prompt-corpus        # build the evaluation corpus
make prompt-mask          # build per-field visibility masks
make prompt-fewshot       # build few-shot exemplar files
make prompt-bundles       # render prompt bundles per profile
make prompt-stress        # adversarial/edge-case bundle
make prompt-eval          # run the model over bundles
make prompt-report        # score and report
make prompt-variants      # compare variants
make prompt-consistency   # repeat-run stability
make prompt-watch         # watch a running sweep
```

Method:

1. **Stage 1** isolates the *system* prompt (`V01`–`V06`), extraction prompt held at baseline.
2. **Stage 2** isolates the *extraction* prompt (`V07`–`V12`), system held at baseline.
3. **Stage 3** combines measured winners (`V13`+), built by `combination_profile()` — never guessed.

Production runs `V00` (`DEFAULT_PROMPT_PROFILE`). An experimental profile cannot reach production
without changing that constant.

---

## 8. Reading a report

`backend/reports/` holds:

| File pattern | Contents |
| --- | --- |
| `gt-eval-*.json` | Per-book evaluation (presence-oriented, historical) |
| `gt-verified-*.json` | Verified ground-truth sets |
| `gt-bench-*.json` | Shortlist benchmarks |
| `ocr-*.json` | OCR engine/preprocessing/font matrices |
| `llm-config-matrix*` | Parameter sweeps |
| `pipeline-profile-oki.json` | Host memory/time profile |
| `e2e-*.json` | End-to-end run output |

Before quoting a number, check:

1. Which **track** (presence vs value)?
2. Which **masks** were applied?
3. How many **books**, and which languages?
4. Was the model the one production uses?
5. Is there a confidence interval, or is it a single run?

A number without those five answers is not a result.

---

## 9. Known evaluation limitations

1. **Small corpora.** Single-digit book counts per language make macro averages noisy.
2. **Reference text is itself a transcription.** Some OCR CER is transcription variance.
3. **Telugu and Hindi only.** No evaluation exists for other scripts.
4. **Catalogue-derived ground truth** can include fields no scan states — hence `not_in_scan`.
5. **No automated regression gate.** Evaluation is run on demand, not per commit.
6. **Prompt experiments cost wall-clock time** on CPU, which limits how many arms can be run.

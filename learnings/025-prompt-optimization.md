# 025 — Prompt Engineering for 49-Field Metadata Extraction (gemma4:e4b)

- **Date:** 2026-11-15
- **Status:** **Harness built and validated; accuracy arms not yet run.** This document records the prompt analysis, the harness, and the decision rules. Results are appended as each stage completes (see the run log in [todos/016](../todos/016-prompt-optimization-tracker.md)).
- **Study context:** [plans/018](../plans/018-prompt-optimization.md). Model fixed at `gemma4:e4b`; only prompt text varies. Companion config evidence: [learnings/017](017-llm-configuration-research.md), [018](018-llm-config-validation.md).
- **Scope:** system prompt + extraction prompt + prompting technique. Not in scope: model choice, quantization, fine-tuning, OCR engine, page routing, output schema.

## Summary

The production prompt pair was analysed and found to contain two mutually inconsistent null rules, no per-field guidance, a synthetic few-shot example injected into batches whose schema it does not match, and no conflict or script policy. Those are now 13 explicit variants behind a production-compatible profile registry, with a mask-aware evaluation harness that separates prompt defects from routing defects and from catalogue-only ground truth. Three things are measured and clean before any LLM spend: the refactor is **byte-identical** to the previous prompts, the visibility mask agrees with human verification on **99.6 %** of informative fields, and synthetic perfect/empty/hallucinating predictions move the new value-level metrics exactly as intended.

**No accuracy claim is made here.** The baseline numbers this study must reproduce are the presence-based figures already on file (Hindi 0.560, Telugu 0.670 micro F1) — and those measure *whether a field was filled*, not whether it was right.

## 1. What the existing prompts actually said (and why that is a problem)

| Defect | Evidence | Why it matters |
|---|---|---|
| **Two contradictory null thresholds** | System: *"If a field cannot be determined from the text, return null."* Extraction: *"Extract your best reading for every field that appears anywhere … use null only when the information is genuinely absent."* | Two different bars in one request. The model resolves the ambiguity by guessing, which is the most plausible explanation for the high-recall/low-precision profile in the Telugu runs. |
| **No per-field guidance** | Fields reach the model as `- title: Title (if subtitle exists)`. | `label` vs `title`, `description_work` vs `description_edition`, `printer` vs `place_of_printing`, `publisher` vs `distributors` are genuinely ambiguous, and nothing states what to *exclude*. |
| **Synthetic, batch-misaligned few-shot** | `FEW_SHOT_EXAMPLES` contains invented books and invented ISBNs, injected into **every** batch. | `contributors`, `relationships` and `ancillary_content` receive a core-identity-shaped example whose keys are not in their schema — at ~250 prompt tokens per call. It teaches a template, not the domain. |
| **No conflict policy** | Nothing covers multiple dates, ISBNs, publishers. | Real colophons carry the first edition, the reprint and the copyright year; a price list carries several ISBNs. |
| **No script policy** | `script_match` is computed by the validator and acted on by nothing. | Ground truth mixes scripts (`author` stored as Latin transliteration, `title` as Telugu). The metric is confounded and no prompt says which form to return. |
| **No section precedence** | `[Page N]` markers and front/back routing exist; the prompt never mentions them. | The model cannot prefer a title page over running body text when both mention the title. |
| **Unbounded OCR repair** | *"use your knowledge to interpret corrupted words"*. | Licenses inventing plausible text; no boundary between repairing a garbled word and fabricating a missing one. |
| **Frontend/backend drift, broken override variables** | UI defaults used `{{language}}` / `{{field_descriptions}}`; the renderer supplies `language_name` and a `fields` loop. | Any edited prompt rendered with an **empty field list**. Fixed by serving defaults from the backend (`GET /books/prompt-defaults`). |
| **Unpinned determinism in production** | `temperature=0.3`, no `seed`. | Production output cannot be reproduced or compared. The study runs at temperature 0 / seed 42. |

## 2. Harness

```
prompt_eval/corpus/{ocr,clean}   frozen inputs (byte-identical for every variant)
prompt_eval/masks/<track>.json   per-field visibility mask + calibration
prompt_eval/fewshot/             held-out real exemplars (V11)
scripts/prompt_eval/             build_corpus, build_mask, build_fewshot,
                                 build_bundles, run_eval, score_eval, compare,
                                 build_stress, consistency, list_variants
reports/prompt-eval/             per-variant JSON, registry.json, leaderboard
```

**The mask is the methodological core.** For every `(book, batch, field)` the frozen pages are routed exactly as production routes them, then the ground-truth value is searched for in that routed text:

| Mask | Meaning | Scoring consequence |
|---|---|---|
| `visible` | value is in the text the batch was given | must be extracted — counts in recall |
| `absent` | ground truth is null | a value here is a hallucination |
| `unroutable` | value is in the book but outside this batch's pages | **routing** defect, excluded from prompt scoring |
| `not_in_scan` | value appears nowhere in the cached text (catalogue-derived) | excluded; the model could not extract it from this input |

Without this, the model is punished for `not_in_scan` fields such as `genre` (a Commons category) and for `unroutable` fields such as a title printed after the routed window — neither of which any prompt can fix.

### Harness validation actually performed

| Check | Result |
|---|---|
| Baseline prompts unchanged by the refactor | **0 mismatches** across 4 languages × 8 batches, compared against the committed module |
| Mask vs human `verification` blocks — clean track | **99.6 %** agreement on informative statuses (281 fields across 17 books) |
| Mask vs human `verification` blocks — **OCR track** | **85.8 %** informative agreement after letting human labels override the matcher (100 % on `not_in_scan`, 74.2 % on `scan_confirmed`) |
| Perfect synthetic predictions | accuracy 1.000, hallucination 0.000 — the scoring path does not invent errors |
| Empty synthetic predictions | accuracy 0.000, hallucination 0.000, missing-field detection 1.000 |
| Hallucinating synthetic predictions | hallucination rate 0.056, detection 0.945 — the two are measured independently |
| Validator + prompt + harness unit tests | **81 passing** (34 validator, 25 profile, 22 harness) |

**Mask behaviour on OCR text is materially worse than on clean text, and this constrains what the OCR-track numbers mean.** With ~42 % Telugu CER the matcher cannot recognise a value a human can read, so it under-calls visibility: 223 fields are `visible` out of 844 non-null ground-truth values across 71 books (~3.1 per book). Two consequences, both documented rather than hidden:

1. **Human labels override the matcher.** A `not_in_scan` verdict from a person is authoritative; before the override, 36 of 126 such fields scored as "visible", i.e. the model would have been punished for correctly staying silent. `scan_confirmed` is *not* overridden, because a confirmed value can still sit outside the batch's page window — that is a routing fact, not visibility.
2. **The mask is conservative, so absolute accuracy is optimistic and statistical power is limited.** Excluding rubble-prone fields raises the apparent level for every variant equally, so variant *ranking* stays fair (same field set for all 13), but a 5 % difference on ~223 fields is ~11 fields — hence paired bootstrap CIs over books, and an unmasked score reported alongside.

### Two coverage limitations found while building it

1. **The clean control track is Telugu-only and 17 books, not 30.** Of the 30 books carrying a `wikisource_gt.json`, 13 have an empty `pages` array, and all 30 are Telugu. Hindi has no proofread source. No clean-vs-OCR claim may be made for Hindi; Hindi evidence rests on the OCR track alone. This matches the limitation already recorded in [018](018-llm-config-validation.md).
2. **Clean-track pages are sparse** (proofread pages only, e.g. `[5,6,7,8,67..72]`), so position-based routing occasionally lands outside the page that carries the title. Those fields surface as `unroutable` rather than as prompt failures — visible in the mask, not hidden in the score.

### Why the first OCR corpus was unusable — three causes, not one

The first freeze (Tesseract 4.1.1 on the nodes, pages `1..12` + last 3, `run_ocr` only) left only **33.5 %** of core fields findable, with 27 of 71 books showing none. An initial attribution to the node's Tesseract version was **wrong** and is withdrawn. Same-image tests settled it: `ubuntu:22.04` (4.1.1) and 5.5 produce the *same* readable Hindi on a body page, and PSM 3/4/6 all give Devanagari share 0.69–0.73 there. The real causes:

| # | Cause | Evidence | Fix |
|---|---|---|---|
| 1 | **`--psm 11` chosen for 25 of 72 front-matter pages.** `page_classifier` mapped "few components" to SPARSE. | On a normal body page PSM 11 returns Latin rubble; PSM 3/4/6 return readable Hindi. Re-running at PSM 4 raised Devanagari share from 0.46–0.69 to 0.57–0.75. | `PSM.SPARSE` removed from the enum; sparse pages now get `SINGLE_COLUMN`, guarded by a test. |
| 2 | **Wrong pages.** Production OCRs the pages a human selected; the corpus hardcoded `1..12`, which in these scans are library accession slips, stamps and rotated book-post labels. | In `1913_Ummed_Singh_Charitra_Hindi_PDF`, pages 1–9 are library forms; the book's own text starts at page 10. In one book the title page sits **after page 12** (found in 13–30 only). | Wider window (24 + last 4), scoped noise filter, keep 16 front + 4 tail. |
| 3 | **Ground truth in the wrong script.** 50 of 110 Hindi core values are Latin transliterations (`Sadhu Aur Vaishya`, `Leader Press, Allahabad`) while the scan is Devanagari. Telugu is 108 Telugu vs 21 Latin. | Literal/fuzzy matching can never confirm those, so the mask called them `not_in_scan` — i.e. it reported an OCR failure where the GT format made verification impossible. | New `script_mismatch` mask bucket, excluded from scoring and reported separately: **210 fields** moved out of `not_in_scan`. |

A fourth, smaller difference: the corpus called `run_ocr` directly and stored `full_text`, while production stores `cleaned_text` (post-normalisation) and the LLM prefers `corrected_text`. The corpus builder now calls `ocr_service.process_page_image()` — the same function the OCR worker calls — so the frozen text and production text cannot drift again.

**The first noise filter was itself a measurement defect.** Re-measuring the pages it dropped found three false positives, all fixed before the second re-freeze:

| Dropped page | Rule that fired | Why it was wrong | Fix |
|---|---|---|---|
| `यह गली बिकाऊ नहीं` (17 chars) | `MIN_PAGE_CHARS = 60` | This **is the book's half-title**. Sparse pages are the metadata pages. | Floor lowered to 12 characters. |
| 2 000-character body page containing `पुस्तकालय` | unscoped `LIBRARY_MARKERS` | "Library" in running text is not a library slip; the page carries no catalogue fields and costs nothing to keep. | Markers only apply to pages ≤ 600 characters. |
| English title page, 100 % Latin | `MAX_LATIN_SHARE` alone | Latin-dominant is exactly what a Latin-transliterated Hindi GT can match; dropping it guarantees the field is unrecoverable. | Latin-dominant pages are dropped only when form cues are present (URL, licence, `accession`/`class no`, book-post label). |

A stale-file path was fixed at the same time: when a rebuild produced no usable pages it returned without writing, leaving the previous build's file in place, so the merge would have treated PSM-11-era text as current. A `--force` rebuild now deletes that file.

Still true and separate: production's `corrected_text` is **human-reviewed**, so production text will always look better than any automated run. A frozen corpus can match production's *pipeline*, never its reviewers.

## 3. Variants

13 static profiles (§"Prompt variants under test" in `reports/prompt-eval/variants.md`), plus `V13`–`V15` generated from the leaderboard:

| Stage | Variants | Variable isolated |
|---|---|---|
| 0 | `V00` | reproduction of current prompts |
| 1 | `V01`–`V06` | system prompt only (role, strict-verbatim, OCR-noise, script-aware, context-priority, null-discipline) |
| 2 | `V07`–`V12` | extraction prompt only (schema-driven, evidence-based, missing-explicit, field-guidance, few-shot-real, conflict-policy) |
| 3 | `V13`–`V15` | best system × best/runner-up extraction, chosen by rule |
| 4 | finalists | clean track (Telugu only) |
| 5 | finalists | stress set |

Fixed for every variant: `gemma4:e4b`, `think:false`, `num_ctx 4096`, `num_predict 512`, `temperature 0`, `seed 42`, `repeat_penalty 1.0`, `format = <batch schema>`, `num_thread 3`. Values follow [018](018-llm-config-validation.md); changing them mid-study would invalidate the comparison and evict the prefix cache.

## 4. Techniques and how each is decided

Each row states the hypothesis and the measurement that settles it. **No verdict is recorded until a run exists.**

| Technique | Hypothesis | Deciding measurement |
|---|---|---|
| Zero-shot vs few-shot (real, batch-matched) | Synthetic global examples actively mislead non-identity batches | value accuracy + hallucination rate for `V11` vs `V00`, per batch group |
| Per-field guidance (`V10`) | Disambiguating `label`/`title`, `printer`/`place_of_printing` raises precision without cost | value precision/recall delta, paired over books |
| Evidence-based extraction (`V08`) | Requiring a quote and page for every value suppresses invention | hallucination rate, plus quote-grounding rate; **cost** measured because output grows |
| Explicit missing-field handling (`V09`) | Making "absent vs damaged" explicit increases abstention where it should | missing-field detection accuracy vs recall traded against it |
| Context prioritisation (`V05`) | Section precedence fixes conflicts without extra calls | conflict cases in the stress set |
| Conflict policy (`V12`) | Stated precedence beats implicit behaviour on multi-date/ISBN books | stress-set accuracy on the injected-value cases |
| Script policy (`V04`) | A stated non-transliteration rule raises `author`/`title` accuracy | value accuracy on same-script ground truth, `script_match` rate |
| Null discipline (`V06`) | Removing the contradiction alone recovers precision | value precision + hallucination rate, no other change |
| Multi-stage / hierarchical extraction | Extra passes fix what one pass cannot | **only pursued if single-pass plateaus** and the gap is field-group specific; each extra pass must beat its own latency cost |

Statistical rule: a variant is only called better when the paired bootstrap CI of `variant − baseline` over books excludes zero, and it may not be recommended if one language regresses beyond its CI.

## 5. How to re-run

```bash
cd backend
python -m scripts.prompt_eval.build_corpus --track both          # once; needs Indic Tesseract packs
python -m scripts.prompt_eval.build_mask --track ocr
python -m scripts.prompt_eval.build_fewshot --track ocr
python -m scripts.prompt_eval.build_bundles --stage 1 --track ocr
python3 scripts/prompt_eval/run_eval.py --bundles prompt_eval/bundles/V0*.ocr.jsonl --out results/ocr.jsonl
python -m scripts.prompt_eval.score_eval --results results/ocr.jsonl --track ocr
python -m scripts.prompt_eval.compare --track ocr --emit-stage3
python -m scripts.prompt_eval.build_bundles --stage 3 --track ocr   # reads stage3.json
python -m scripts.prompt_eval.build_stress --track ocr --variants V00,V13,V14
python -m scripts.prompt_eval.consistency results/a.jsonl results/b.jsonl   # determinism check
```

`run_eval.py` is stdlib-only and resumable; `--shard i/N` splits books across nodes. Cost model and the spend guardrail are in [plans/018](../plans/018-prompt-optimization.md) §0.

## 6. Next steps

1. Build the OCR corpus on `test-node-2` / `test-node-3` (claimed 2026-11-15), then run Stage 1.
2. Reproduce the baseline: `V00` must land near 0.560 (hin) / 0.670 (tel) presence-F1, else the harness diverged and no other number is meaningful.
3. Stage 2, then Stage 3 from `--emit-stage3`, then clean-track and stress confirmation.
4. Promote the winner (`DEFAULT_PROMPT_PROFILE`) and adopt temperature 0 / pinned seed in production, after the production-temp confirmation arm.
5. Append results here and to the tracker; keep `reports/prompt-eval/registry.json` as the experiment record.

## References

- Plan: [plans/018](../plans/018-prompt-optimization.md) · Tracker: [todos/016](../todos/016-prompt-optimization-tracker.md)
- Code: [`prompt_profiles.py`](../backend/app/services/prompt_profiles.py) · [`prompts.py`](../backend/app/services/prompts.py) · [`extraction_validator.py`](../backend/app/services/extraction_validator.py) · [`scripts/prompt_eval/`](../backend/scripts/prompt_eval/)
- Prior: [005](005-llm-model-evaluation.md) · [006](006-first-real-accuracy.md) · [010](010-llm-shortlist-benchmark.md) · [013](013-verified-shortlist-and-ocr.md) · [017](017-llm-configuration-research.md) · [018](018-llm-config-validation.md) · [022](022-gt-source-expansion.md)
- Node inventory: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)

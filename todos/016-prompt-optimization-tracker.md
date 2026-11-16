# 016 — Prompt Optimization Tracker (gemma4:e4b)

**Plan:** [plans/018](../plans/018-prompt-optimization.md) · **Findings:** [learnings/025](../learnings/025-prompt-optimization.md)
**Status:** harness implementation in progress; Stages 1–5 not started.

## Build checklist

| # | Item | State |
|---|---|---|
| 1 | `plans/018` + this tracker + node claims | done |
| 2 | `app/services/prompt_profiles.py` — 13 static profiles, production-compatible render context | done |
| 3 | `prompts.py` delegates to the profile registry (signatures unchanged, baseline byte-identical) | done |
| 4 | `extraction_validator.py` — mask-aware + value-aware metrics + bootstrap CI | done |
| 5 | `scripts/prompt_eval/build_corpus.py` — frozen OCR + clean corpus | done (clean built; OCR needs Indic Tesseract packs → node) |
| 6 | `scripts/prompt_eval/build_mask.py` — visibility mask + calibration | done (clean: 99.6 % informative agreement) |
| 7 | `scripts/prompt_eval/build_bundles.py` — render prompts per (book, variant, batch) | done |
| 8 | `scripts/prompt_eval/run_eval.py` — stdlib runner, resumable, token/timing capture | done (not exercised against a live Ollama yet) |
| 9 | `scripts/prompt_eval/score_eval.py` — merge + score + per-variant report | done (validated with synthetic predictions) |
| 10 | `scripts/prompt_eval/compare.py` — leaderboard, CIs, regression flags, stage-3 pick | done |
| 11 | `scripts/prompt_eval/build_stress.py` — seeded perturbations + per-case masks | done |
| 12 | `scripts/prompt_eval/run_matrix.sh` — node sharding | done |
| 13 | `GET /books/prompt-defaults` + frontend consumes it | done (backend tested; `tsc --noEmit` and `eslint` clean via the `node:22-alpine` container) |
| 14 | Makefile targets (`prompt-corpus`, `prompt-mask`, `prompt-bundles`, `prompt-eval`, `prompt-report`, `prompt-variants`, `prompt-fewshot`, `prompt-stress`) | done |
| 15 | Tests: golden prompts, profile registry, mask/value metrics, harness | done (81 passing) |
| 16 | `scripts/prompt_eval/consistency.py` — repeated-run determinism check | done |

## Experiment run log

**Started 2026-11-15 on all three nodes** (user instruction: stop other work, provision all three, test all prompts).

| Stage | Variants | Dataset | Calls | Node(s) | Status | Report |
|---|---|---|---|---|---|---|
| P0 — provision | — | — | — | 1, 2, 3 | **done** — ollama 0.40.16 + `gemma4:e4b` (6.6 GB), tesseract `tel`/`hin`, venv `~/peval/venv`, code + PDF shard unpacked at `~/peval` | — |
| P1 — OCR corpus | — | 71 books, sharded 24/24/23 | — | 1, 2, 3 | **superseded by P1b** — first freeze was unusable (PSM 11 + wrong pages + Latin GT) | `/tmp/old-corpus` |
| P2 — copy corpus back + merge | — | 71 books | — | local | **done** — 71 unique books, no duplicates | `prompt_eval/corpus/ocr/` |
| P3 — mask + few-shot + bundles | 13 | 71 books, OCR | — | local | **rebuilt 2026-11-16 06:16 from the merged 20-page corpus** — 226 visible / 105 unroutable / 298 not_in_scan / **215 script_mismatch**, informative agreement **89.3 %**. 7,384 bundle records (568/variant, 20 pages/book) | `prompt_eval/masks/ocr.json`, `prompt_eval/bundles/` |
| P4 — all variants | V00–V12 | 71 books, OCR | 7,384 | 1, 2, 3 | **RUNNING since 2026-11-16 06:18** on the 20-page bundles: 2,496 / 2,496 / 2,392, first calls 35–57 s. The 21:22 launch was stopped at 1,343 calls (~Rs 360): its bundles embedded **12 pages/book** from an older local corpus, so those results were archived, not reused | `~/results/matrix.<i>_3.jsonl` |
| P1b/P1c — corpus re-freeze | — | 71 books, sharded | — | 1, 2, 3 | **done** — four fixes: PSM 11 removed, wider window + noise filter (refined: markers only on ≤600-char pages, Latin pages only with form cues), shared `process_page_image`, 3000 px render cap. Final: **71 books, 1,381 pages, 1.35 M chars**, PSM only 3/4; findability **33.5 %→37.5 %**, zero-signal books **27→22** | `prompt_eval/corpus/ocr/` |
| P5 — mask/score/leaderboard | — | — | — | local | pending | — |
| P6 — Stage 3 combos | V13–V15 | 71 books, OCR | 1,704 | 1, 2, 3 | pending | — |
| P7 — clean track | finalists | 17 books | — | 1, 2, 3 | pending | — |
| P8 — stress | finalists | 12 cases + 6 noisy books | — | 1, 2, 3 | pending | — |
| P9 — consistency | finalists | 6 books × 2 | — | 1, 2 | pending | — |

Node cost while running: 3 × Rs 14/h ≈ **Rs 42/h**. Measured rate is 25–80 s per call (mean ≈ 65 s), so P4 is **≈ 45–50 h wall ⇒ ≈ Rs 2,000**. That lands at the Rs 2,400 abort threshold, so Stages 6–9 need a budget decision once P4 finishes. The original 13.7 h estimate assumed the warm-cache figure from learnings/018, which these longer prompts do not reach.

## Watchdog (long run)

`backend/scripts/prompt_eval/node_watch.sh` (or `make prompt-watch FIX=1`) checks, per node: instance status, runner process, result growth, JSON validity of the last 20 records, Ollama HTTP, CPU load and free disk.

- **Process died** → `--fix` relaunches `run_eval.py`, which resumes from the existing JSONL (verified: killed node-3 mid-run at 23/2392, restarted, resumed at 3/2369, **0 duplicate keys**).
- **Ollama unresponsive** → `--fix` restarts the service.
- **Instance TERMINATED / low disk / repeated invalid JSON** → reported only. Starting a machine is a spend decision, so the watchdog never starts or stops instances.
- Exit code 1 = attention needed (including "was broken, now fixed"), so alerts also fire on recoveries.

**Phase awareness (added 2026-11-15 after a real misfire).** The watchdog is now rebuild-aware and restart-gated:

- A running `build_corpus` puts the node in the **rebuild phase**; `run_eval.py` is never launched from that branch.
- `run_eval.py` is only restarted when `~/results/.matrix_expected` exists — a marker written at launch. An idle node is reported `⏸ idle`, not "runner dead".
- A rebuild is only restarted when `~/results/.corpus_expected` exists and `~/ocr5.log` has not printed its final `manifest ->` summary; completed books are reused (no `--force` on restart).
- Ollama health is only asserted while an eval runner is actually alive.

**Incident 2026-11-15/16:** the previous watchdog treated "no `run_eval.py`" as a dead matrix and relaunched extraction on all three nodes while the corpus rebuild was running. That run lasted ~8.5 h against the *old* bundles before it was found and killed. **Its `matrix.*.jsonl` files are stale and must be deleted before the next matrix launch** (`run_eval.py` resumes by key, so leaving them would silently skip calls and mix corpora).

Scheduled: cron job `731e02ca`, every 10 minutes at `:03 :13 :23 :33 :43 :53`, durable, auto-expires after 7 days. Manual check: `make prompt-watch FIX=1`.

## Decisions

| Date | Decision | Rationale |
|---|---|---|
| 2026-11-15 | `num_ctx` 4096, not 8192 | `learnings/018` finding 2: identical output, half the KV, keeps the prefix cache stable |
| 2026-11-15 | Cost model uses warm-cache timing | `learnings/018` finding 7: ~4× speedup once config is stable |
| 2026-11-15 | Abort threshold Rs 10,000 after Stage 2 | Hard cap is Rs 10,000; leaves headroom for Stages 3–7 |
| 2026-11-15 | Routing frozen during the study | Routing defects are reported via the `unroutable` mask, not fixed mid-experiment |
| 2026-11-15 | Clean track re-scoped to 17 Telugu books | 13 of the 30 `wikisource_gt.json` files have an empty `pages` array and all 30 are Telugu; no Hindi control track exists |
| 2026-11-15 | V13–V15 are generated, not pre-registered | Their text is whatever the Stage 1/2 leaderboard selects (`compare.py --emit-stage3` → `stage3.json`); pre-picking them would be a guess |
| 2026-11-15 | Few-shot holdout = 2 richest books per language | `build_fewshot.py` writes the holdout list into `manifest.json`; `score_eval.py` excludes those books, so exemplars cannot leak into scores |
| 2026-11-15 | Stress cases get their own mask | Scoring a removed title as a recall miss would be wrong; `masks/stress.json` is recomputed on the perturbed text |
| 2026-11-15 | P4 stopped at 2 % and the corpus re-frozen | The first corpus measured PSM-11 rubble on library-slip pages. Root cause was **not** the node's Tesseract version (withdrawn); it was PSM 11 + wrong page window + Latin-transliterated GT. See learnings/025 |
| 2026-11-15 | `PSM.SPARSE` removed from the enum | PSM 11 produced unusable Indic text on 25/72 front-matter pages; a unit test now forbids reintroducing it |
| 2026-11-15 | Corpus uses `process_page_image(..., include_retry=False)` | One shared function with the worker; the retry pass only rewrites review boxes and cannot change text, so skipping it is free |
| 2026-11-15 | P1b output discarded; noise filter scoped | Measured false positives: `MIN_PAGE_CHARS=60` dropped a 17-character half-title (`यह गली बिकाऊ नहीं`) that *is* the book's title; an unscoped marker regex dropped 2 000-character body pages that merely contain `पुस्तकालय`; and the Latin-share rule dropped English title pages that a Latin-transliterated GT can only match. Dropping is now limited to near-empty pages and pages with form evidence |

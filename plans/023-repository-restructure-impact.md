# 023 — Restructure Impact Analysis (Deliverable 3)

- **Date:** 2026-11-17
- **Status:** Analysis for review. **No files moved.**
- **Inputs:** `plans/021-…` (audit), `plans/022-…` (proposal).
- **Purpose:** enumerate exactly what breaks if the D2 plan is executed, and what must change first.

---

## 1. Verdict

| Area | Risk | Finding |
| --- | --- | --- |
| Automated tests | **None** | No test reads `fixtures/`, `samples/` or `ground_truth/` on disk; discovery tests use `tmp_path` |
| CI/CD | **None** | Both workflows use only `working-directory: backend` / `frontend`; no `paths:` filters, no artefact uploads |
| Docker builds | **None** | `Dockerfile.backend` copies `app/`, `scripts/`, `alembic/`; nothing from `tests/` or `reports/` |
| Evaluation scripts | **Medium** | 8 hardcoded path constants across 7 files |
| Report writers | **Low** | 2 defaults |
| Markdown links | **Low** | 15 inbound links, 13 of them inside files that are themselves moving |
| `.gitignore` | **Low** | 3 anchored rules + one local `.gitignore` must move with the data |

The restructure is safe to execute. The cost is almost entirely bookkeeping, not behaviour.

---

## 2. Test coupling

**No test reads any moving data path.** `backend/tests/unit/test_ground_truth_discovery.py` calls
`discover_ground_truth(tmp_path)` with a temporary directory, so the real corpus is never opened
during a test run.

**One import coupling exists and matters:**
`backend/tests/unit/test_ground_truth_discovery.py:14` does
`from scripts.evaluate_extraction import discover_ground_truth, ignored_fields`.

That confirms the D2 decision to leave `backend/scripts/` in place — moving it would break a unit test
that currently passes.

---

## 3. Code constants that must change when data moves

All paths are relative to the repo root unless stated.

| File:line | Current | Required |
| --- | --- | --- |
| `backend/scripts/prompt_eval/common.py:23` | `GT_ROOT = BACKEND_ROOT / "tests" / "fixtures" / "ground_truth"` | point at `datasets/ground-truth` |
| `common.py:24` | `EVAL_ROOT = BACKEND_ROOT / "prompt_eval"` | `datasets/evaluation` |
| `common.py:25–30` | `CORPUS_ROOT`, `BUNDLE_ROOT`, `MASK_ROOT`, `STRESS_ROOT`, `FEWSHOT_ROOT`, `MANIFEST_PATH` derived from `EVAL_ROOT` | follow the new root |
| `common.py:31` | `REPORT_ROOT = BACKEND_ROOT / "reports" / "prompt-eval"` | `benchmarks/prompt-eval` |
| `backend/scripts/merge_node_fill.py:33` | `parents[1] / "tests" / "fixtures" / "ground_truth"` | `parents[2] / "datasets" / "ground-truth"` |
| `backend/scripts/verify_ground_truth.py:30` | same shape | same change |
| `backend/scripts/apply_field_schema.py:31` | same shape | same change |
| `backend/scripts/ocr_bench/bench_lang_config.py:43` | `parents[2] / "tests" / "fixtures" / "ground_truth"` | `parents[3] / "datasets" / "ground-truth"` |
| `backend/scripts/ocr_bench/build_line_corpus.py:26` | same shape | same change |
| `backend/scripts/gt_review_queue.py:26` | `parents[1] / "reports"` | `parents[2] / "benchmarks" / "reports"` |
| `backend/scripts/evaluate_extraction.py` | `GT_ROOT` default (referenced at line 267) | repoint |
| `backend/scripts/generate_sample_pdf.py:830` | default output `tests/fixtures/samples` | `datasets/samples` |
| `backend/scripts/load_samples.py:65` | expects `samples/{lang}/{quality}/sample.pdf` | unchanged structure, new root |

**Docstring examples that would become wrong** (cosmetic, but they are the documented usage):
`node_gt_fill.py:24`, `poc_page_detector.py:14`, `probe_openrouter_extractions.py:21`,
`score_acc.py:8`, `ocr_bench/bench_lines_preprocess.py:26`.

The `parents[N]` index shifts are the only non-mechanical part: `prompt_eval` sits two levels under
`backend/`, `ocr_bench` sits two levels under `backend/scripts/`, and the new roots are at repository
level. Each index must be recomputed, not pattern-replaced.

---

## 4. Pre-existing defects found during this analysis

Not caused by the restructure, but they will silently survive it unless fixed.

| # | Defect | Where |
| --- | --- | --- |
| P1 | **Machine-specific absolute path** in a published script: `/run/media/agamya/Storage/WikiProjects/OKI/Indic-Book-Metadata-Extractor/...` | `backend/scripts/ocr_bench/build_bundle.py:20` |
| P2 | **Windows absolute links** `d:/WikiProjects/OKI/...` — already broken on every other machine | `docs/implementation_plan.md:5` |
| P3 | `AGENTS.md` documents `probing/` and `fixtures/` directories that do not exist | `AGENTS.md:25,27` |
| P4 | `AGENTS.md` points at `plans/001-project-architecture.md`, which does not exist (plans begin at 002) | `AGENTS.md:68` |

P1 is the only one with a functional consequence: the script works on exactly one machine.

---

## 5. CI/CD

Both workflows were checked for path sensitivity:

| Workflow | Path coupling | Change required |
| --- | --- | --- |
| `.github/workflows/ci.yml` | `working-directory: backend` / `frontend` only | **None** |
| `.github/workflows/security.yml` | no path filters | **None** |

No `paths:` triggers, no `upload-artifact` of reports, no cache keyed on moved directories. Moving
`datasets/`, `benchmarks/` and `docs/` does not affect CI.

**Caveat:** if a future job is added that runs `make prompt-eval`, it would depend on the new
`datasets/evaluation` path. Nothing does today.

---

## 6. `.gitignore`

| Rule | Location | Action |
| --- | --- | --- |
| `backend/tests/fixtures/samples/**/*.pdf` | `.gitignore:59` | rewrite for `datasets/samples/**/*.pdf` |
| `backend/tests/fixtures/ground_truth/**/*.pdf` | `.gitignore:63` | rewrite for `datasets/ground-truth/**/*.pdf` |
| `backend/tests/fixtures/ground_truth/**/*.part` | `.gitignore:64` | rewrite alongside |
| `bundles/`, `bundles-*/`, `stress/`, `results/` | `backend/prompt_eval/.gitignore` | move with `datasets/evaluation/`, or re-anchor |

⚠️ **Order matters.** If the data is moved before the ignore rules are updated, GitHub will accept a
`git add -A` containing ~1.1 GB of PDFs. The rules must be updated in the same commit as the move, and
the commit verified with `git status` before pushing.

---

## 7. Markdown links that break

Thirteen of the fifteen are inside documents that are themselves moving or being archived, so they are
rewritten as part of the merge rather than tracked separately.

| Link location | Target | Handling |
| --- | --- | --- |
| `docs/known-issues.md:90` | `api-reference.md` | file is consolidated → link disappears |
| `docs/metadata-fields.md:19,155` | `indic_book_metadata_extractor.md` | archived → point at `history/` |
| `docs/metadata-fields.md:154` | `wikidata-workflow.md`, `wikibase-reference.md` | merged/moved |
| `docs/local-development-guide.md:674,733` | `monitoring.md` | merged |
| `docs/local-development-guide.md:731,732` | `admin-bulk.md` | moved to `operations/bulk-operations.md` |
| `docs/tech_stack.md:227` | `monitoring.md` | archived doc; no fix needed beyond the archive banner |
| `docs/developer-guide.md:522` | `monitoring.md` | merged |
| `docs/user-guide.md:296` | `admin-bulk.md` | update to new path |
| `learnings/026-…:5` | `../docs/ocr-training.md` | update to `../docs/processing/ocr-training.md` |
| `learnings/001-…:19` | `../docs/indic_book_metadata_extractor.md` | update to `../docs/history/…` |
| `docs/implementation_plan.md:5` | `d:/…` absolute | P2 — archive as-is or strip |

**Stable:** `docs/README.md` → `operations/runbook.md`, `docs/architecture/system-architecture.md` →
`../known-limitations.md`, and every `plans/`↔`learnings/` cross-reference. Those paths do not change.

**Not a link but must change:** `docs/testing/evaluation.md:174` and `docs/testing/strategy.md:115,127`
name `backend/reports/` as prose; `docs/development/repository-structure.md` describes the old tree.

---

## 8. Docker

`docker/Dockerfile.backend` copies `app/`, `scripts/`, `alembic/`, `alembic.ini`, `newrelic.ini`. No
reference to `tests/`, `reports/` or `prompt_eval/`. Compose files bind only
`docker/scripts/backend-entrypoint.sh`.

**No change required**, and no build context needs to widen.

---

## 9. Execution order (D4), with the reason for each step

| Step | Action | Why this order |
| --- | --- | --- |
| 1 | Write `datasets/README.md` and `benchmarks/README.md` | Documents the destination before content arrives |
| 2 | Update `.gitignore` rules | Prevents accidentally staging 1.1 GB |
| 3 | `git mv` ground truth, samples, evaluation corpus | Preserves history; rules already in place |
| 4 | Patch the 8 path constants + docstrings | Scripts must work immediately after the move |
| 5 | `git mv backend/reports → benchmarks/reports` | Independent of the data move |
| 6 | Patch `REPORT_ROOT` and `gt_review_queue` default | Same commit as step 5 |
| 7 | Merge legacy content into the structured docs | Content exists before originals are archived |
| 8 | `git mv` the merged originals into `docs/history/` | Only after their content is preserved |
| 9 | Move `user-guide`, `bulk-operations`, `wikidata-workflow`, `ocr-training`, `ocr-postdeploy`, `changelog` | Pure relocations |
| 10 | Rewrite `docs/README.md`, `README.md`, `docs/development/repository-structure.md` | Index must reflect reality |
| 11 | Fix inbound links and the three prose references | Last, once paths are final |

---

## 10. Verification per step

| After step | Verify |
| --- | --- |
| 3 | `git status` shows no PDFs staged; `du -sh datasets` matches |
| 4 | `cd backend && uv run python -m scripts.verify_ground_truth --help`, `python -m scripts.prompt_eval.build_corpus --help` |
| 6 | `cd backend && uv run python -m scripts.gt_review_queue --help` |
| 4+6 | `uv run pytest tests/unit` and `npm test` |
| 10 | Link check over `docs/` — every relative link resolves |
| 11 | `grep -r 'backend/reports\|tests/fixtures' docs/` returns nothing |

No step requires the running stack, so the whole sequence can be verified offline.

---

## 11. Residual risks

1. **Untracked files dominate the data move.** 91 PDFs are untracked; `git mv` cannot move what git
   does not know about. The move must be done on the filesystem and then verified, not assumed.
2. **`prompt_eval/bundles*` (118 MB, gitignored).** Left in place by D2; if the directory moves, the
   local `.gitignore` must travel or the bundles become visible to `git status`.
3. **Archived docs remain accurate-looking.** `docs/history/README.md` is the only signal; every
   archived file should open with a one-line banner.
4. **`CHANGELOG.md` is stale on arrival.** Moving it to root makes it more visible, not more correct.
5. **Reference docs grow.** `docs/reference/api.md` going from 252 to ~900 lines may warrant a
   per-router table of contents to stay navigable.

# 022 — Repository Restructure Proposal (Deliverable 2)

- **Date:** 2026-11-17
- **Status:** Proposal for review. **No files moved.**
- **Inputs:** `plans/021-repository-audit-and-reorganization.md` (D1).
- **Carried decision:** merge unique legacy content **before** archiving the originals.
- **Next:** D3 impact analysis must validate every move listed in §6 before anything is executed.

---

## 1. Design principles

1. **One home per fact.** A fact lives in exactly one document; others link to it.
2. **No new top-level directories without a consumer.** `datasets/` and `benchmarks/` are justified by
   volume and by being data rather than documentation. Nothing else is added at root.
3. **Keep test-colocated fixtures where they are.** Only assets consumed primarily by evaluation
   scripts move. Judge by *consumer*, not by directory name.
4. **Do not move `backend/scripts/`.** ~50 modules are invoked as `python -m scripts.X` from the
   `backend/` working directory and referenced by `Makefile` targets. Moving them is a large blast
   radius for cosmetic gain. This is an explicit trade-off, recorded in §7.
5. **Archive, do not delete.** Legacy documents with the same information as a current doc move to
   `docs/history/`. Deletion is D5 and requires proof of identity first.
6. **No fragmentation.** Merging into existing documents is preferred over creating siblings. The one
   new document (`docs/operations/bulk-operations.md`) is a relocation of an existing one, not a split.

---

## 2. Proposed tree

```text
.
├── README.md                     ← updated: points at docs/, status, quickstart
├── AGENTS.md                     ← corrected: remove probing/, fixtures/ conventions that don't exist
├── CLAUDE.md                     unchanged
├── CHANGELOG.md                  ← from docs/changelog.md, refreshed
├── DEPLOY.md                     unchanged pointer
├── Makefile
├── backend/                      unchanged layout
│   ├── app/
│   ├── alembic/
│   ├── tests/fixtures/           ← keeps only what pytest reads
│   ├── scripts/                  ← unchanged (see §7)
│   └── uv.lock, pyproject.toml
├── frontend/                     unchanged (delete boilerplate README)
├── docker/                       unchanged
├── docs/
│   ├── README.md                 ← rewritten index; links verified
│   ├── architecture/             3 docs, unchanged
│   ├── application/              4 docs, unchanged
│   ├── processing/               6 docs + ocr-training.md
│   ├── development/              4 docs (local-development absorbs native setup)
│   ├── operations/               5 docs + bulk-operations.md + wikidata-workflow.md
│   ├── testing/                  3 docs + results/
│   │   └── results/              llm-model-evaluation.md, ground-truth-coverage.md
│   ├── reference/                3 docs (api.md absorbs request/response detail)
│   ├── user-guide.md             ← from docs/user-guide.md
│   ├── known-limitations.md      ← consolidated: known-issues + known-limitations + todos/015
│   └── history/                  archived: plans, superseded prose, investigations
├── datasets/                     ← NEW: data, not documentation
│   ├── README.md                 producer scripts, regeneration, licensing
│   ├── ground-truth/{hin,tel}/   ← from backend/tests/fixtures/ground_truth/
│   ├── manifest.jsonl            ← from backend/tests/fixtures/ground_truth/
│   ├── samples/{eng,hin,tel,bilingual}/  ← from backend/tests/fixtures/samples/
│   └── evaluation/{corpus,masks,fewshot}/ ← from backend/prompt_eval/
├── benchmarks/                   ← NEW: results, not inputs
│   ├── README.md
│   ├── reports/                  ← from backend/reports/
│   └── prompt-eval/              ← from backend/reports/prompt-eval/
├── learnings/                    unchanged
├── plans/                        unchanged (+ 021, 022)
├── todos/                        unchanged
├── poc/                          unchanged
├── infra/                        unchanged
├── reference/                    gitignored, unchanged
└── scripts/                      root-level tooling only
    ├── deploy/dokploy-deploy.sh
    └── README.md
```

Deliberately **not** added: `getting-started/`, `guides/`, `assets/`, `tools/`, `evaluation/` at root.
Each would hold one or two items or duplicate an existing directory.

---

## 3. Merge plan — the four oversized legacy docs

Section-level: what exists in the legacy file, where it lands, and what is redundant.

### 3.1 `docs/api-reference.md` (1008) → `docs/reference/api.md` (252)

| Legacy section | Destination | Why |
| --- | --- | --- |
| Overview / Authentication / Pagination / Error Responses | `reference/api.md` §Conventions | Current doc has a thinner conventions table |
| Per-endpoint request + response bodies (Register … Change password, ~20 endpoints) | `reference/api.md`, new "Request and response bodies" subsection per router | **Only source of body schemas** |
| Health, Books, Dashboard, Admin, Pages, Extraction, Metadata, Catalog, Bulk, Notifications | `reference/api.md` endpoint tables (already present) — bodies appended | Tables exist; detail does not |
| `## Catalog & Book Detail` | `reference/api.md` | Route renamed to `/books/{id}/detail`; verify before merge |

### 3.2 `docs/local-development-guide.md` (750) → `docs/development/local-development.md` (148)

| Legacy section | Destination | Why |
| --- | --- | --- |
| Hardware Requirements | `development/local-development.md` §Prerequisites | Current doc says "16 GB recommended" only |
| Option A: Docker Compose (6 steps) | existing §First run | Already substantially present |
| Option B: Native setup — Linux/macOS/Windows, per-OS package tables, pgvector, Redis, Ollama | `development/local-development.md`, new §Native setup (Linux/macOS/Windows) | **Only source of native instructions** |
| Running Tests (backend/frontend/E2E) | `testing/running-tests.md` | Duplicates a dedicated doc |
| Common Development Tasks (migrations, reset, model download, logs, lint, shell, scaling) | `development/local-development.md` §Day-to-day | Partially present |
| Port Reference | `development/configuration.md` §Ports | Belongs with configuration |
| Troubleshooting (10 entries) | `development/local-development.md` §Troubleshooting | Current doc has 7 rows; legacy has more |
| Architecture Quick Reference | drop | Duplicates `architecture/system-architecture.md` |

### 3.3 `docs/monitoring.md` (376) → `docs/operations/monitoring.md` (144)

| Legacy section | Destination | Why |
| --- | --- | --- |
| Architecture Overview / The 3 New Relic agents | `operations/monitoring.md` §New Relic | **Only source of agent topology** |
| Environment Variables (shared, frontend, infra) | `development/configuration.md` + monitoring | Config table lives in one place |
| Docker Compose Configuration (backend/worker/frontend/infra) | `operations/monitoring.md` | Only source of the wiring |
| What Gets Tracked / Custom Business Events | merge with current §Custom events | Both cover this; current is shorter |
| In-app admin monitoring | `operations/monitoring.md` (current §Admin system metrics) | Already covered |
| Local Development (disable/enable, verification) | `operations/monitoring.md` §Local | Missing today |
| Troubleshooting | `operations/monitoring.md` | Missing today |

### 3.4 `docs/ocr-setup.md` (445) → three destinations

| Legacy section | Destination | Why |
| --- | --- | --- |
| 1. What gets installed (system pkgs, python pkgs, line-model weights) | `development/local-development.md` §OCR installation | **Only source of install + weight provenance** |
| 2. Local development setup (Linux/macOS/no-Docker) | same, §Native setup | Duplicates 3.2 |
| 3. Docker setup (dev, staging/prod, build args) | `operations/deployment.md` §Images | Only source of `OCR_LINE=true` build arg |
| 4. Configuration reference | `development/configuration.md` §OCR | Duplicates the config table |
| 5. How a page is OCR'd (5.1–5.6) | `processing/ocr.md` | Current doc covers this more accurately; merge only if legacy is more specific |
| 6. Triggering OCR | `processing/pipeline-overview.md` | Duplicates |
| 7. Verification and evaluation | `testing/evaluation.md` | Dubious commands; verify before merging |
| 8. Troubleshooting / Adding a language | `processing/ocr.md` §Limitations + troubleshooting | Unique |

---

## 4. Consolidation plan — remaining legacy files

| Legacy file | Action | Target |
| --- | --- | --- |
| `runbook.md` (229) | **merge** | `operations/runbook.md` — legacy holds the restore-drill SQL and container-name conventions |
| `developer-guide.md` (559) | **merge then archive** | Dev setup → `development/local-development.md`; architecture → already covered; API notes → `reference/api.md` |
| `metadata-fields.md` (155) | **merge then archive** | Wikidata P-ID mapping → `reference/metadata-fields.md` |
| `known-issues.md` (210) + `known-limitations.md` (219) + `todos/015` (107) | **consolidate into one** | `docs/known-limitations.md`, sections: Performance, Accuracy, Feature gaps, Operations, Platform |
| `ocr-training.md` (139) | **move** | `processing/ocr-training.md` (unique content) |
| `ocr-postdeploy-runbook.md` (238) | **move** | `operations/ocr-postdeploy.md` |
| `wikibase-reference.md` (125) | **merge then archive** | Extensions/gadgets section → `operations/wikibase-operations.md` |
| `wikidata-workflow.md` (256) | **move** | `operations/wikidata-workflow.md` |
| `admin-bulk.md` (413) | **move + retitle** | `operations/bulk-operations.md` |
| `user-guide.md` (361) | **move** | `docs/user-guide.md` |
| `changelog.md` (121) | **move + mark stale** | `CHANGELOG.md` at root |
| `llm-model-evaluation-report.md` (122) | **move** | `testing/results/llm-model-evaluation.md` |
| `ground-truth-field-coverage.md` (146) | **move** | `testing/results/ground-truth-coverage.md` |
| `tech_stack.md` (369) | **archive** | `docs/history/tech-stack-2026-06.md` (names Airavata) |
| `implementation_plan.md` (343) | **archive** | `docs/history/implementation-plan-2026-05.md` |
| `indic_book_metadata_extractor.md` (354) | **archive** | `docs/history/project-overview-original.md` |
| `accuracy-report-day8.md` (199) | **archive** | `docs/history/accuracy-report-day8.md` |
| `llm-extraction-conversation-log.md` (312) | **archive** | `docs/history/` |
| `llm-extraction-zero-fields-investigation.md` (357) | **archive** | `docs/history/` |
| `agent-browser-testing-handoff.md` (427) | **archive** | `docs/history/` |
| `frontend/README.md` (36) | **remove** | Unmodified `create-next-app` boilerplate |

`docs/history/README.md` will state: *archived, describes a past state, not current behaviour, kept for
provenance.*

---

## 5. Dataset and script proposals

### 5.1 What moves to `datasets/`

| From | To | Rationale | Risk |
| --- | --- | --- | --- |
| `backend/tests/fixtures/ground_truth/{hin,tel}` | `datasets/ground-truth/` | 922 MB, consumed by evaluation scripts | `evaluate_extraction.py` default `GT_ROOT` |
| `backend/tests/fixtures/ground_truth/manifest.jsonl` | `datasets/manifest.jsonl` | Index for the above | Same |
| `backend/tests/fixtures/ground_truth/splits` | `datasets/ground-truth/splits/` | Eval splits | prompt harness |
| `backend/tests/fixtures/samples/*` | `datasets/samples/` | Sample PDFs, used by `load_samples.py`, `evaluate_extraction.py` | **pytest coupling unconfirmed — D3 must check** |
| `backend/prompt_eval/{corpus,masks,fewshot}` | `datasets/evaluation/` | Frozen benchmark inputs | `scripts/prompt_eval/common.py` path constants |
| `backend/prompt_eval/manifest*.json` | `datasets/evaluation/` | Corpus manifest | same |

### 5.2 What stays put

| Path | Why it stays |
| --- | --- |
| `backend/tests/fixtures/ground_truth/README.md` | Describes the dataset; a short pointer may remain after the move |
| `backend/prompt_eval/bundles*` (118 MB) | Gitignored generated output; prompt harness writes there. Move or delete is D5, not D4 |
| `backend/reports/` contents | **Move to `benchmarks/`**, but verify no script writes by relative path first |

### 5.3 Scripts

Only the root `scripts/` directory is reorganised:

```text
scripts/deploy/dokploy-deploy.sh     ← from scripts/dokploy-deploy.sh
```

`backend/scripts/` is **left untouched**. Its modules are imported as `scripts.prompt_eval.*` and
invoked as `python -m scripts.<name>` from `backend/`; the `Makefile` and many docs reference those
invocations. Relocating them would touch ~50 entry points for organisational tidiness only.

---

## 6. Path mapping — structured tree

Unchanged unless listed.

| Current | New | Action |
| --- | --- | --- |
| `docs/README.md` | `docs/README.md` | rewrite index |
| `docs/architecture/*.md` (3) | same | none |
| `docs/application/*.md` (4) | same | none |
| `docs/processing/*.md` (6) | same | none |
| `docs/processing/ocr-training.md` | — | **new**, from legacy |
| `docs/development/*.md` (4) | same | `local-development.md` grows |
| `docs/operations/*.md` (5) | same | `monitoring.md`, `runbook.md`, `wikibase-operations.md` grow |
| `docs/operations/bulk-operations.md` | — | **new**, from `admin-bulk.md` |
| `docs/operations/wikidata-workflow.md` | — | **new**, from legacy |
| `docs/operations/ocr-postdeploy.md` | — | **new**, from legacy |
| `docs/testing/*.md` (3) | same | `evaluation.md` links to results |
| `docs/testing/results/*.md` | — | **new**, from two legacy evidence docs |
| `docs/reference/*.md` (3) | same | `api.md` and `metadata-fields.md` grow |
| `docs/user-guide.md` | — | **new**, from legacy |
| `docs/known-limitations.md` | `docs/known-limitations.md` | **rewritten** from three sources |
| `docs/history/*.md` | — | **new**, six archived documents |

Net effect on `docs/`: 54 files → **~40** (25 legacy removed from the flat root: 6 merged-and-archived,
6 archived, 10 moved into the tree, 1 consolidated, 1 removed as boilerplate; plus 4 new destinations).

---

## 7. Trade-offs recorded

| Decision | Cost | Why accepted |
| --- | --- | --- |
| Leave `backend/scripts/` in place | Repository root has two script locations | ~50 `python -m scripts.*` invocations and all Makefile targets stay valid |
| Merge rather than split the API reference | `docs/reference/api.md` becomes ~900 lines | A single reference beats three fragments for lookup |
| Consolidate three "known issues" docs into one | One long document | Three overlapping documents is the current failure mode |
| `docs/history/` rather than deleting | Repository keeps ~1,700 lines of superseded prose | Provenance; deletion is D5 and needs proof |
| Move `reports/` to `benchmarks/` | Scripts that write `reports/...` need a default-path change | Results are not source code |

---

## 8. What D3 must verify before anything moves

1. **Every code reference to a moving path.** `GT_ROOT` in `evaluate_extraction.py`; `load_samples.py`;
   `make_eval_bundle.py`; `scripts/prompt_eval/common.py` path constants; `generate_sample_pdf.py`
   default output.
2. **pytest coupling to `tests/fixtures/samples`** — if any test reads it, that fixture stays.
3. **Whether `backend/reports/` is written by relative path** in any script or default argument.
4. **Makefile targets** referencing `backend/reports`, `tests/fixtures`, `prompt_eval`, or `docs/`.
5. **`.github/workflows/*.yml`** — any path filter or artifact upload tied to moved directories.
6. **`.gitignore` rules** — several are path-anchored (`backend/tests/fixtures/**/*.pdf`,
   `backend/prompt_eval/bundles/`) and must follow the data.
7. **Internal markdown links** — every `[x](path)` in `docs/`, `learnings/`, `plans/`, `todos/` that
   points at a moving file.
8. **Docker build contexts** — `backend/scripts` is copied into the image; confirm nothing references
   `tests/fixtures` at build time.
9. **`CLAUDE.md` / `AGENTS.md` conventions** that name directories.

---

## 9. Open questions for you

1. **`benchmarks/` vs `datasets/benchmarks/`** — results are evidence; inputs are data. Proposal keeps
   them as siblings (`benchmarks/` outputs, `datasets/evaluation/` inputs). Acceptable, or one
   `data/` root?
2. **`docs/history/` contents** — six archived documents (~1,700 lines). Keep all, or keep only those
   with unique evidence (the two LLM investigations) and drop the rest in D5?
3. **`CHANGELOG.md`** — move and mark stale, or regenerate from git history as part of D5?
4. **`docs/testing/results/`** — a new subdirectory for two evidence docs. Preferred over adding a
   fourth top-level area, but it is a new directory. Merge them into `testing/evaluation.md` instead?
5. **`AGENTS.md` conventions** — correct it to match reality (no `probing/`, no `fixtures/`), or adopt
   those conventions as part of this work?

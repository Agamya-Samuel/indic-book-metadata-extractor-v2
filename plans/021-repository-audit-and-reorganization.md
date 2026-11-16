# 021 — Repository Documentation & Asset Audit

- **Date:** 2026-11-17
- **Status:** Deliverable 1 complete — inventory and findings only. **No recommendations, no file changes.**
- **Next:** Deliverable 2 (target structure and path mapping), then D3 impact analysis, D4 execution, D5 cleanup.
- **Method:** every tracked markdown file enumerated via `git ls-files`, line counts from `wc -l`, dates from
  `git log -1 --format=%cs`, sizes from `du`/`git ls-tree -r -l`. Claims about behaviour cross-checked
  against source, not against other prose.

A verdict of `superseded` below means *a newer document covers the same ground*; it does **not** mean the
older file is worthless. Two legacy files are substantially larger than their replacements, which is
recorded as a finding in §3 rather than glossed over.

---

## 1. Scope and method

**Scanned:** all tracked `*.md` under `docs/`, `learnings/`, `plans/`, `todos/`, `poc/`, `infra/`, plus
root `README.md`, `AGENTS.md`, `CLAUDE.md`, `DEPLOY.md`, and `frontend/**/*.md`.

**Excluded:** `node_modules/`, `.next/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `reference/`
(gitignored host notes), and all binary assets. None of these are project documentation.

**Purpose** for each file was derived from its H1/H2 structure and opening paragraph, not from its
filename.

**Totals:** 119 tracked markdown files. Breakdown:

| Area | Files |
| --- | --- |
| `docs/` | 54 (25 legacy flat + 29 structured incl. `README.md`) |
| `learnings/` | 31 (30 numbered + `README.md`) |
| `plans/` | 19 |
| `todos/` | 10 |
| `poc/` | 1 |
| `infra/` | 1 tracked (`gcp-test-nodes.md` is gitignored) |
| Root | 4 (`README`, `AGENTS`, `CLAUDE`, `DEPLOY`) |
| `backend/` | 3 (`reports/prompt-eval/README.md`, `reports/prompt-eval/variants.md`, `scripts/ocr_bench/README.md`, `tests/fixtures/ground_truth/README.md`) |
| `frontend/` | 3 (`README.md` boilerplate, `AGENTS.md`, `CLAUDE.md`) |

---

## 2. Documentation inventory

### 2.1 Root

| Path | Lines | Touched | Purpose | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `README.md` | 206 | 2026-11-15 | Project overview, quickstart, architecture summary, feature list | current, with stale facts | §4 C1, C2 |
| `AGENTS.md` | 68 | 2026-11-10 | Agent workflow rules and folder conventions | current-ish | Documents `probing/` and `fixtures/` folders that do not exist (§5 M7) |
| `CLAUDE.md` | 0 | 2026-11-10 | Pointer file containing only `@AGENTS.md` | pointer | — |
| `DEPLOY.md` | 14 | 2026-11-17 | Three-line pointer to `docs/operations/deployment.md` | pointer | Rewritten this session |

### 2.2 `docs/` structured tree (29)

| Path | Lines | Class | Status |
| --- | --- | --- | --- |
| `docs/README.md` | 132 | index | current |
| `docs/architecture/system-architecture.md` | 407 | architecture | current |
| `docs/architecture/integrations.md` | 237 | architecture | current |
| `docs/architecture/decisions.md` | 148 | index | current |
| `docs/application/frontend.md` | 223 | architecture | current |
| `docs/application/backend.md` | 190 | architecture | current |
| `docs/application/authentication.md` | 249 | architecture | current |
| `docs/application/data-model.md` | 331 | reference | current |
| `docs/processing/pipeline-overview.md` | 172 | architecture | current |
| `docs/processing/pdf-and-pages.md` | 180 | how-to | current |
| `docs/processing/preprocessing.md` | 182 | how-to | current |
| `docs/processing/ocr.md` | 245 | how-to | current |
| `docs/processing/extraction.md` | 258 | how-to | current |
| `docs/processing/jobs-and-queues.md` | 239 | how-to | current |
| `docs/development/local-development.md` | 148 | how-to | current |
| `docs/development/configuration.md` | 198 | reference | current |
| `docs/development/repository-structure.md` | 145 | reference | current |
| `docs/development/contributing.md` | 179 | how-to | current |
| `docs/operations/deployment.md` | 251 | runbook | current |
| `docs/operations/runbook.md` | 227 | runbook | current |
| `docs/operations/monitoring.md` | 144 | how-to | current |
| `docs/operations/backup-and-recovery.md` | 150 | runbook | current |
| `docs/operations/wikibase-operations.md` | 173 | how-to | current |
| `docs/testing/strategy.md` | 154 | reference | current |
| `docs/testing/running-tests.md` | 151 | how-to | current |
| `docs/testing/evaluation.md` | 205 | how-to | current |
| `docs/reference/api.md` | 252 | reference | current |
| `docs/reference/metadata-fields.md` | 195 | reference | current |
| `docs/reference/glossary.md` | 126 | reference | current |

### 2.3 `docs/` legacy flat files (25)

| Path | Lines | Touched | Subject | Status | Note |
| --- | --- | --- | --- | --- | --- |
| `implementation_plan.md` | 343 | 2026-05-22 | 12-week build plan | historical | Predates implementation by 6 months |
| `indic_book_metadata_extractor.md` | 354 | 2026-11-12 | Project overview, architecture, tech stack | overlapping | Duplicates `README` + `architecture/` |
| `tech_stack.md` | 369 | 2026-06-29 | Per-layer technology reference | outdated | Names Airavata as the LLM |
| `api-reference.md` | 1008 | 2026-11-16 | Endpoint-by-endpoint reference | overlapping | **4× larger than `reference/api.md`** |
| `metadata-fields.md` | 155 | 2026-11-13 | Field list, Wikidata mapping | overlapping | Title says 49; body described as 52 elsewhere |
| `local-development-guide.md` | 750 | 2026-11-12 | Dev setup, Docker + native | overlapping | **5× larger than `development/local-development.md`** |
| `developer-guide.md` | 559 | 2026-11-13 | Architecture + dev setup | overlapping | Spans `application/` + `development/` |
| `runbook.md` | 229 | 2026-11-17 | Operations runbook | overlapping | Same size as `operations/runbook.md` |
| `monitoring.md` | 376 | 2026-11-17 | New Relic APM setup | overlapping | **2.6× larger than `operations/monitoring.md`** |
| `ocr-setup.md` | 445 | 2026-11-17 | OCR install, config, pipeline | overlapping | Merges `processing/ocr.md` + `development/configuration.md` |
| `ocr-training.md` | 139 | 2026-11-16 | Fine-tuning the line model | **unique** | No equivalent in the structured tree |
| `ocr-postdeploy-runbook.md` | 238 | 2026-11-16 | Post-deploy OCR tuning steps | **unique** | — |
| `wikibase-reference.md` | 125 | 2026-07-13 | Installed extensions and gadgets | **unique** | — |
| `wikidata-workflow.md` | 256 | 2026-11-12 | QID creation, property mapping | **unique** | Operational detail not in `wikibase-operations.md` |
| `admin-bulk.md` | 413 | 2026-11-12 | OpenRefine/Wikibase bulk workflows | overlapping | — |
| `user-guide.md` | 361 | 2026-11-15 | End-user walkthrough | **unique** | Only end-user documentation in the repo |
| `changelog.md` | 121 | 2026-11-12 | Version history | stale | Last entry `[0.1.0] — 2026-05-29` |
| `known-issues.md` | 210 | 2026-11-17 | Problems and mitigations | overlapping | Overlaps `known-limitations.md` |
| `known-limitations.md` | 219 | 2026-11-15 | Capability limits, risk register | overlapping | Overlaps `known-issues.md` |
| `accuracy-report-day8.md` | 199 | 2026-08-30 | Day-8 accuracy close-out | historical | Airavata-era numbers |
| `llm-model-evaluation-report.md` | 122 | 2026-11-15 | Consolidated model comparison | current | Evidence, not prose |
| `ground-truth-field-coverage.md` | 146 | 2026-11-14 | 49-field conformance and coverage | current | Evidence |
| `agent-browser-testing-handoff.md` | 427 | 2026-11-13 | QA takeover brief | historical | Superseded by `todos/010` pointer |
| `llm-extraction-conversation-log.md` | 312 | 2026-09-01 | Investigation narrative | historical | Root cause since fixed |
| `llm-extraction-zero-fields-investigation.md` | 357 | 2026-09-01 | Zero-fields debugging | historical | Root cause since fixed |

**12 of these 25 are not referenced anywhere in `docs/README.md`:**
`accuracy-report-day8`, `admin-bulk`, `agent-browser-testing-handoff`, `ground-truth-field-coverage`,
`implementation_plan`, `indic_book_metadata_extractor`, `known-limitations`, `llm-extraction-conversation-log`,
`llm-extraction-zero-fields-investigation`, `llm-model-evaluation-report`, `ocr-postdeploy-runbook`,
`wikidata-workflow`.

### 2.4 `learnings/` — grouped

30 numbered records plus a `README.md` describing the convention. Individual titles and outcomes are
already indexed in `docs/architecture/decisions.md`, so the audit records them by group:

| Group | Files | Nature |
| --- | --- | --- |
| Ground truth and evaluation | 001, 002, 003, 005, 006, 009, 010, 013, 019, 022 | Measurements and source surveys |
| OCR | 004, 020, 021, 026, 027, 028, 029, 030 | Benchmarks, strategy reviews, fine-tune results |
| LLM configuration | 017, 018, 025 | Parameter research and validation |
| Platform and reliability | 011, 014, 015, 016, 023, 024 | Exposure, routing, service inventory, hardening |
| Product and UI | 007, 008, 012 | Audits and implementation outcomes |

Status: **historical evidence, intentionally immutable.** Two are known-stale as descriptions of current
behaviour (`015` predates `gemma4:e4b`; `014` describes removed routes).

### 2.5 `plans/` (19)

| Path | Lines | Subject | Recorded status |
| --- | --- | --- | --- |
| `002-ground-truth-poc.md` | 171 | GT dataset PoC | Plan → awaiting approval |
| `003-ocr-engine-evaluation.md` | 175 | OCR engine selection | Decided 2026-11-13 |
| `004-llm-model-evaluation.md` | 181 | LLM selection | In progress |
| `005-auth-rbac.md` | 246 | Auth and RBAC | Implemented |
| `006-ui-ux-workflow-admin.md` | 366 | UI/UX overhaul | Approved |
| `007-moderated-signup-admin-library.md` | 193 | Moderated signup | Implemented |
| `008-ui-ux-composition-redesign.md` | 256 | Composition redesign | Approved |
| `009-metadata-page-selection.md` | 77 | Page-window selection | PoC run |
| `010-notifications.md` | 158 | Notifications | Implementation started |
| `011-ground-truth-source-expansion.md` | 103 | GT expansion | Partially done |
| `011-launch-readiness.md` | 148 | Launch readiness | Code complete |
| `012-llm-service-native-endpoint.md` | 89 | Native `/api/chat` | Implemented |
| `013-production-hardening.md` | 90 | Reliability | Complete |
| `014-api-pagination.md` | 56 | Pagination | **no status line** |
| `015-integrated-ocr-metadata-review.md` | 249 | OCR/metadata review UI | **no status line** |
| `017-telugu-ocr-engine-integration.md` | 98 | Telugu line model | Implemented |
| `018-prompt-optimization.md` | 180 | Prompt engineering | Approved |
| `019-ocr-accuracy-improvement.md` | 126 | OCR accuracy | Proposed |
| `020-ocr-language-and-page-type-routing.md` | 132 | Language routing | Complete |

### 2.6 `todos/` (10)

`008-ui-ux-workflow-admin` (117), `009-auth-rbac-handoff` (363), `010-agent-browser-testing-handoff` (12,
pointer), `011-route-redesign-handoff` (210), `011-ui-ux-composition-redesign` (126),
`012-ocr-engine-integration-handoff` (44), `013-notifications` (26), `014-launch-readiness` (90),
`015-documented-but-unimplemented` (107), `016-prompt-optimization-tracker` (82).

All are execution checklists. `015-documented-but-unimplemented` is the only one whose subject directly
duplicates documentation (`docs/known-limitations.md` has a "What's not yet implemented" section).

### 2.7 Other tracked documentation

| Path | Lines | Subject | Status |
| --- | --- | --- | --- |
| `poc/004-poc-telugu-wikisource-gt.md` | 120 | Wikisource GT proof of concept | historical |
| `infra/monitoring-and-alerting.md` | 96 | Monitoring provider decision | current |
| `backend/reports/prompt-eval/README.md` | 21 | Prompt-eval report format | current |
| `backend/reports/prompt-eval/variants.md` | 610 | Prompt variant catalogue | current |
| `backend/scripts/ocr_bench/README.md` | 46 | OCR benchmark harness | current |
| `backend/tests/fixtures/ground_truth/README.md` | 93 | Ground-truth dataset description | current |
| `frontend/README.md` | 36 | Default `create-next-app` boilerplate | boilerplate |
| `frontend/AGENTS.md` | 5 | Next.js agent rules stub | pointer |
| `frontend/CLAUDE.md` | 1 | Pointer to `AGENTS.md` | pointer |

---

## 3. Overlap and duplication matrix

Classification: **identical** (same content), **subset** (older ⊂ newer), **overlapping** (shared ground,
unique content on both sides), **conflicting** (disagree on facts).

| Subject | Files | Relationship | Evidence |
| --- | --- | --- | --- |
| Operations runbook | `docs/runbook.md` vs `docs/operations/runbook.md` | **overlapping** | Both 227–229 lines, same section order; each has content the other lacks |
| Monitoring | `docs/monitoring.md` (376) vs `docs/operations/monitoring.md` (144) | **subset in reverse** | Legacy is 2.6× larger and carries the New Relic agent setup; new one has the health/metrics model |
| API reference | `docs/api-reference.md` (1008) vs `docs/reference/api.md` (252) | **overlapping** | Legacy enumerates request/response bodies per endpoint; new gives grouped tables |
| Metadata fields | `docs/metadata-fields.md` (155) vs `docs/reference/metadata-fields.md` (195) | **overlapping** | Legacy has Wikidata mapping table; new has batch/page-window detail |
| Local setup | `docs/local-development-guide.md` (750) vs `docs/development/local-development.md` (148) | **subset in reverse** | Legacy covers Windows/WSL, native install, troubleshooting in depth |
| Developer onboarding | `docs/developer-guide.md` (559) vs `docs/development/*` + `docs/application/*` | **overlapping** | Legacy mixes architecture and setup; the new tree splits them |
| Tech stack | `docs/tech_stack.md` (369) vs `docs/architecture/system-architecture.md` | **conflicting** | Legacy names Airavata; current default is `gemma4:e4b` |
| Project overview | `docs/indic_book_metadata_extractor.md` (354) vs `README.md` + `architecture/` | **overlapping** | Third copy of the overview |
| Known issues | `docs/known-issues.md` vs `docs/known-limitations.md` vs `todos/015` | **overlapping ×3** | Same three-way split: issues, limits, unimplemented |
| OCR operational | `docs/ocr-setup.md` (445) + `ocr-training.md` + `ocr-postdeploy-runbook.md` vs `docs/processing/ocr.md` | **overlapping** | New doc covers runtime; legacy covers install, fine-tuning, post-deploy tuning |
| Wikibase | `docs/wikibase-reference.md` + `docs/wikidata-workflow.md` + `docs/admin-bulk.md` vs `docs/operations/wikibase-operations.md` | **overlapping** | New doc states it is optional and lists defects; legacy holds the actual setup procedure |
| Evaluation | `docs/llm-model-evaluation-report.md` + `docs/accuracy-report-day8.md` + `ground-truth-field-coverage.md` vs `docs/testing/evaluation.md` | **overlapping** | New doc describes method; legacy holds the measured numbers |
| Deployment | `DEPLOY.md` (14) vs `docs/operations/deployment.md` (251) | **subset** | Root file is a pointer; verified |
| Changelog | `docs/changelog.md` vs git history | **stale** | Last entry 2026-05-29 |
| Boilerplate | `frontend/README.md` | **n/a** | Unmodified `create-next-app` output |

**Finding:** the "legacy is superseded" premise in `docs/README.md` holds for the pointers
(`DEPLOY.md`) but is **not established** for the 25 legacy files — in four subjects the legacy document is
materially larger than its replacement.

---

## 4. Conflict register

| # | Conflict | Where | Ground truth |
| --- | --- | --- | --- |
| C1 | **Service count** — "8 Docker services" listing `worker-ocr`, `worker-llm` | `README.md:67` | `docker-compose.production.yml` defines **15** services and a **single** `worker` on `-Q ocr,llm,default`. The split exists only in `docker-compose.yml` (dev). |
| C2 | **Field count** — "52 extracted bibliographic fields" | `README.md:96`; also `tech_stack.md`, `accuracy-report-day8.md`, `changelog.md`, `developer-guide.md`, `implementation_plan.md`, `known-issues.md`, `known-limitations.md` | `FullMetadata` has **50** keys: 49 standard + `custom_fields` (`backend/app/schemas/metadata.py`) |
| C3 | **Field count, internal** — title says "49 fields", file is cited among 52-field documents | `docs/metadata-fields.md` | 49 standard fields, 50 keys total |
| C4 | **LLM identity** — Airavata presented as the model | `tech_stack.md`, `implementation_plan.md`, `accuracy-report-day8.md`, `changelog.md`, `developer-guide.md`, `local-development-guide.md`, `llm-extraction-conversation-log.md`, `llm-extraction-zero-fields-investigation.md`, `indic_book_metadata_extractor.md` | `DEFAULT_LLM_MODEL = "gemma4:e4b"`; `phi4-mini` is rollback only |
| C5 | **Removed routes** — `/library`, `/bulk-operations` documented as live | `api-reference.md`, `admin-bulk.md`, `changelog.md`, `implementation_plan.md`, `indic_book_metadata_extractor.md` | No `frontend/src/app/library/` or `bulk-operations/`; bulk is `/admin/bulk`. The three *new* docs that mention them (`application/frontend.md`, `architecture/decisions.md`, `development/repository-structure.md`) do so only to record the removal. |
| C6 | **Worker topology** — split workers described as production | `README.md:67` | Single worker in production compose (see C1) |
| C7 | **Numbering collision** — two `011` plans | `plans/011-ground-truth-source-expansion.md`, `plans/011-launch-readiness.md` | Both exist; distinct subjects |
| C8 | **Numbering collision** — two `011` todos | `todos/011-route-redesign-handoff.md`, `todos/011-ui-ux-composition-redesign.md` | Both exist; distinct subjects |
| C9 | **Heading/file mismatch** — file `013-verified-shortlist-and-ocr.md` is headed `# 012 —` | `learnings/013-…` | Filename and H1 disagree; `012-verified-shortlist` and `012-moderated-signup-outcome` both exist |
| C10 | **Index overstates** — `docs/README.md` calls the 25 flat files "superseded" | `docs/README.md` §Legacy files | Not verified for 4 subjects where legacy is larger (§3) |

---

## 5. Misplacement findings

Each entry states the observation and why the location is a poor fit — not where it belongs.

| # | Observation | Why the location is a poor fit |
| --- | --- | --- |
| M1 | 25 legacy documents sit flat in `docs/` beside a 7-directory structured tree | Two competing organisations in one directory; 12 legacy files are unreachable from the index |
| M2 | Host-specific operations material lives outside `docs/`: `infra/monitoring-and-alerting.md`, `learnings/011`, `learnings/024`, `plans/011-launch-readiness.md` | Operational procedure is discoverable only by reading the process log |
| M3 | **1.1 GB / 274 files** of ground-truth data under `backend/tests/fixtures/`, of which **183 are tracked** and 91 are untracked PDFs | A production dataset lives inside the application's test package; `pytest` roots there, so dataset growth affects test tooling |
| M4 | `backend/prompt_eval/` holds **131 MB / 206 files**, including two 59 MB bundle directories that are gitignored | Generated artefacts sit inside the backend package |
| M5 | `backend/reports/` holds **46 tracked benchmark outputs (2.1 MB)** | Evidence artefacts live inside the backend source tree |
| M6 | Scripts are split: root `scripts/` has 1 file (`dokploy-deploy.sh`), `backend/scripts/` has ~50 | No single location for repository tooling |
| M7 | `AGENTS.md` documents `probing/` and `fixtures/` conventions; **neither directory exists** | The stated convention does not match the repository |
| M8 | `frontend/README.md` is unmodified `create-next-app` boilerplate | Describes nothing about this project |
| M9 | `docs/implementation_plan.md` (2026-05-22) and `docs/tech_stack.md` (2026-06-29) predate the implementation | Dated plans presented as current documentation |
| M10 | `project-update.html` at root (gitignored) | Untracked artefact in the source root |
| M11 | `.next/`, `.pytest_cache/`, `.ruff_cache/` present in the working tree | Generated; correctly gitignored, but visible in the tree |
| M12 | `CLAUDE.md` (0 lines), `frontend/CLAUDE.md` (1 line), `frontend/AGENTS.md` (5 lines) | Pointer stubs in three locations for one rule file |

---

## 6. Coverage gaps

Checked against routes, services and modules — not against other prose.

| Area | State | Evidence |
| --- | --- | --- |
| Notifications | **No current doc** | `plans/010` + `todos/013` only; `notifications.py`, `notification_service.py`, bell UI undocumented |
| SSE event contract | Partial | Event types appear in `reference/api.md`; no dedicated contract/versioning doc |
| Maintenance mode | Partial | Covered in `operations/runbook.md`; middleware behaviour not in `application/backend.md` |
| Pagination | Partial | Envelope documented; `plans/014` has no status line |
| Admin queue management / bulk cancel | **No current doc** | `api/admin.py` exposes `/jobs/cancel`, `/jobs/summary`; only endpoint rows exist |
| OCR fine-tuning | **No current doc** | Only legacy `docs/ocr-training.md` |
| Wikibase extensions/gadgets | **No current doc** | Only legacy `docs/wikibase-reference.md` |
| End-user guide | **No current doc** | Only legacy `docs/user-guide.md` |
| Changelog / release notes | **No current doc** | Legacy `docs/changelog.md` is stale |
| Ground-truth corpus construction | Partial | `tests/fixtures/ground_truth/README.md` + `backend/scripts/*`; not in `docs/testing/` |

---

## 7. Data and asset inventory

`.git` is **5.0 MB**. The working tree carries ~1.2 GB of data, almost all gitignored. That distinction
matters: repository weight is a git problem, not a disk problem.

| Path | Kind | Tracked | Size | Regeneration | Consumers |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/fixtures/ground_truth/hin` | Ground truth | 70 of 105 | 564 MB | `fetch_from_wikisource.py`, `enrich_ground_truth.py`, `verify_ground_truth.py` | `eval_ocr.py`, `evaluate_extraction.py`, prompt harness |
| `backend/tests/fixtures/ground_truth/tel` | Ground truth | 102 of 138 | 358 MB | Same | Same |
| `backend/tests/fixtures/ground_truth/splits` | Fixture manifest | 1 of 1 | 4 KB | `make_eval_bundle.py` | prompt harness |
| `backend/tests/fixtures/ground_truth/manifest.jsonl` | Index | yes | 72 KB | Regenerated with corpus | prompt harness |
| `backend/tests/fixtures/samples/eng` | Sample PDFs | 1 of 3 | 36 KB | `generate_sample_pdf.py` | pytest, e2e |
| `backend/tests/fixtures/samples/hin` | Sample PDFs | 3 of 12 | 29 MB | `generate_sample_pdf.py` | pytest, e2e |
| `backend/tests/fixtures/samples/tel` | Sample PDFs | 2 of 11 | 102 MB | `generate_sample_pdf.py` | pytest, e2e |
| `backend/tests/fixtures/samples/bilingual` | Sample PDF | 1 of 1 | 512 B | `generate_sample_pdf.py` | pytest |
| `backend/prompt_eval/corpus` | Frozen OCR inputs | yes | 14 MB | `build_corpus.py` | prompt harness (`prompt-eval`) |
| `backend/prompt_eval/masks` | Evaluation masks | yes | 160 KB | `build_mask.py` | prompt harness |
| `backend/prompt_eval/fewshot` | Held-out exemplars | yes | 68 KB | `build_fewshot.py` | prompt harness (`V11`) |
| `backend/prompt_eval/bundles` | **Generated** | no (gitignored) | 59 MB | `build_bundles.py` | prompt harness only |
| `backend/prompt_eval/bundles-psm11-20261115` | **Generated** | no (gitignored) | 59 MB | `build_bundles.py` | prompt harness only |
| `backend/reports/*.json` | Benchmark outputs | yes | 2.1 MB | produced by eval scripts | `docs/testing/evaluation.md`, `learnings/` |
| `backend/reports/prompt-eval/variants.md` | Benchmark report | yes | 610 lines | `prompt-report` | prompt work |
| `backend/scripts/ocr_bench/` | Benchmark harness | yes | small | n/a | OCR evaluation |
| `storage/models/telugu-ocr-ft` | Model weights | no (volume) | 310 MB | `train_tesseract_lstm.sh` + fine-tune | worker OCR |

**Classification of the boundary cases:**

- **Test fixtures:** `samples/*` — small inputs the suite reads at a pinned path.
- **Datasets:** `ground_truth/{hin,tel}` — used by evaluation scripts far more than by `pytest`, and 1.1 GB.
- **Benchmark inputs:** `prompt_eval/corpus`, `masks`, `fewshot` — frozen on purpose (byte-identical inputs).
- **Benchmark outputs:** `backend/reports/*`, `prompt_eval/` variants report — evidence to preserve, not inputs.
- **Generated:** `prompt_eval/bundles*` — rebuildable in one command, already gitignored.
- **Model weights:** not in the repository at all; live on the storage volume.

---

## 8. Scale summary

| Area | Files | Tracked | On disk | In git |
| --- | --- | --- | --- | --- |
| `docs/` | 54 | 54 | 688 KB | yes |
| `learnings/` | 31 | 31 | 384 KB | yes |
| `plans/` | 19 | 19 | 260 KB | yes |
| `todos/` | 10 | 10 | 104 KB | yes |
| `backend/tests/fixtures/` | 274 | 183 | **1.1 GB** | JSON only |
| `backend/prompt_eval/` | 206 | 179 | **131 MB** | corpus/masks/fewshot |
| `backend/reports/` | 46 | 46 | 2.1 MB | yes |
| `poc/`, `infra/`, `scripts/` | 5 | 3 | 36 KB | partial |
| **Total `.git`** | — | — | — | **5.0 MB** |

---

## 9. Explicit non-goals

This deliverable does **not**:

1. Propose a directory structure, or state where any file should live.
2. Provide a path mapping, rename list, or keep/merge/delete verdict.
3. Assess impact on imports, scripts, CI, or links — that is Deliverable 3.
4. Change, move, or delete any file.
5. Judge whether a legacy document's extra depth is still accurate — only that it exists and is larger.

Where a fact could not be established (for example whether `shadcn/ui` is still used, referenced at
`README.md:75`), it is left out rather than guessed.

---

## 10. Questions carried into Deliverable 2

1. Are the four legacy documents that are materially larger than their replacements
   (`api-reference`, `local-development-guide`, `monitoring`, `ocr-setup`) sources to merge from, or
   frozen archives?
2. Is the `ground_truth/` corpus an application test fixture or a repository-level dataset? Its consumer
   list (eval scripts ≫ pytest) points one way; its current path points the other.
3. Should `backend/reports/` continue to accumulate outputs in the source tree, and should
   `prompt_eval/bundles*` remain inside the backend package when already gitignored?
4. Are the three pointer stubs (`CLAUDE.md`, `frontend/CLAUDE.md`, `frontend/AGENTS.md`) meant to be
   maintained, or are they tool-generated?
5. Do the numbering collisions (C7, C8, C9) get renumbered, or left as historical fact?

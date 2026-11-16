# Testing Strategy

What is tested, at which level, and what is deliberately left to evaluation rather than unit tests.

The pipeline has two very different kinds of correctness:

1. **Software correctness** — does the code do what it claims? Unit and integration tests.
2. **Quality** — is the OCR text good, is the metadata right? Benchmarks against ground truth, not
   assertions.

Trying to unit-test (2) produces brittle tests that assert yesterday's accuracy. So the split is
deliberate.

---

## 1. Layers

| Layer | Location | Tool | Answers |
| --- | --- | --- | --- |
| Backend unit | `backend/tests/unit/` | pytest | Pure functions, mocked I/O |
| Backend integration | `backend/tests/integration/` | pytest | Database, tasks, transactions |
| Frontend unit | `frontend/tests/` | Vitest | Components, hooks, lib, stores |
| End-to-end | `backend/scripts/e2e_*.py`, Playwright | script + `make test-e2e` | A real stack processes a real book |
| Quality evaluation | `backend/scripts/*`, `prompt_eval/` | harness scripts | OCR CER, extraction accuracy |

---

## 2. What is unit-tested and why

The backend keeps logic in pure functions specifically so it can be tested without a database:

| Module | Why it is testable |
| --- | --- |
| `preprocessing.py` | Pure OpenCV transforms on arrays |
| `page_selection.py` | Pure text heuristics |
| `batch_routing.py` | Pure slicing and truncation |
| `ocr_postprocess.py` | Pure string normalisation |
| `extraction_validator.py` | Pure scoring |
| `ocr_tasks.ocr_outcome` | Pure decision function |
| `stage_manager` transitions | Testable with a session fixture |
| `security.py` | Pure token/crypto helpers |

The LLM is injectable into the hybrid orchestrator (`llm_fill_remaining`), so tiering is tested without
Ollama.

### High-value unit targets

| Target | Risk it protects |
| --- | --- |
| `ocr_outcome(total, errors)` | Partial OCR failing the whole book |
| `_resolve_slice` / `select_pages_for_batch` | Batches starving on short books |
| `assemble_ocr_text` truncation | Silently cutting a page mid-word |
| `verify_media_token` | Scope/resource confusion in signed URLs |
| `_user_from_token` checks | Accepting a revoked or unverified session |
| `deriveWorkflowState` (frontend) | Stepper disagreeing with the server |
| Token-bucket / rate-limit edge cases | Auth endpoints not throttled |

---

## 3. What is integration-tested

| Area | Why it needs a database |
| --- | --- |
| Stage transitions and sequential gating | Row locks, `attempt` increments, derived book status |
| Supersede semantics | Requires two job rows with ordered `created_at` |
| Job reaper | Time manipulation over real rows |
| Metadata persistence + evidence reconciliation | `FOR UPDATE`, delete-and-reinsert |
| Migration correctness | Schema must build from empty |
| Notification idempotency | Unique constraint on `(user_id, event_key)` |

These use the real SQLAlchemy models against a test database, not mocks — the failure modes being
tested (locking, constraints, deadlocks) only exist in a real database.

---

## 4. Frontend testing

Vitest, organised by concern:

| Directory | Covers |
| --- | --- |
| `frontend/tests/lib/` | `workflow-state.ts`, pagination, error handling |
| `frontend/tests/hooks/` | SSE, job polling, unsaved-changes |
| `frontend/tests/components/` | Shared, auth, OCR, metadata, admin, notifications |
| `frontend/tests/pages/` | Route-level rendering |
| `frontend/tests/stores/` | Zustand store |

`deriveWorkflowState` is the highest-risk pure function in the frontend: seven steps derived from six
stages, plus staleness. It deserves direct tests, not just component assertions.

---

## 5. End-to-end

| Script | Purpose |
| --- | --- |
| `backend/scripts/e2e_smoke.py` | Fast path: upload → pages → OCR → extract on a small fixture |
| `backend/scripts/e2e_prod.py` | Full run against a deployed environment |
| `make test-e2e` | Wrapper |

E2E is the only place that proves the *wiring* — that a job is created, dispatched, picked up by a
worker, and that SSE and the database agree. Unit tests cannot catch a task that is never enqueued.

---

## 6. Quality evaluation is not testing

OCR and extraction quality are measured, not asserted:

- **OCR**: character error rate against Wikisource-derived ground truth.
- **Extraction**: per-field presence and value accuracy against a verified corpus, with masks for
  unroutable and un-in-scan fields.

Numbers fluctuate with model and preprocessing changes; a regression test would encode one measurement
as truth. Instead, results are recorded in `learnings/` and `benchmarks/reports/`. See
[evaluation](evaluation.md).

---

## 7. Test data

| Location | Contents |
| --- | --- |
| `datasets/samples/` | Small generated PDFs |
| `datasets/ground-truth/` | Expected metadata for fixtures |
| `backend/scripts/generate_sample_pdf.py` | Regenerates synthetic samples |
| `benchmarks/reports/` | Benchmark output, not inputs |

Fixtures are small and synthetic on purpose: real books are large and licensing-sensitive. Real
quality work uses the external ground-truth corpus, not fixtures.

---

## 8. What is not tested

Honest gaps:

1. **No browser E2E in CI** for the full workflow; Playwright exists but is not a gate.
2. **No load or soak testing.**
3. **No chaos testing** of worker death mid-task, despite the elaborate recovery paths.
4. **No migration downgrade tests** — downgrades exist but are not exercised.
5. **No property-based tests** for the Unicode normalisation rules.
6. **No contract tests** between the typed frontend client and the backend schemas; the hand-written
   interfaces in `api.ts` can drift silently.

---

## 9. Policy

- A bug fix gets a regression test that fails before the fix.
- A pipeline decision (partial OCR, staleness, supersede) gets a test at the level where the decision
  lives.
- A model or prompt change gets an evaluation run, not a test.
- Do not assert accuracy numbers in tests.

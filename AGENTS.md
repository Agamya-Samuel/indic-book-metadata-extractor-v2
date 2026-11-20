# Open Book Map — Agent Instructions

## Current Phase: Documented and Stable

The platform is implemented, deployed (staging + production via Dokploy) and fully documented. The
pipeline runs PDF upload → page selection → preprocessing → OCR review → LLM extraction → metadata
review, with an admin panel, bulk operations (OpenRefine → Wikibase/QuickStatements), and
email-verified, admin-approved accounts.

- **OCR:** Tesseract (LSTM only) for Hindi and English; an optional fine-tuned Telugu line model with
  per-page Tesseract fallback; script-aware routing; Unicode normalisation. Binarization and denoising
  are off by default because they erode the Indic headstroke.
- **Extraction:** hybrid regex → dictionary → LLM across 49 fields in 8 batches. Default model is
  `gemma4:e4b` via Ollama's native `/api/chat`; `phi4-mini` is the rollback.
- **Auth:** cookie sessions, CSRF double-submit, email verification, moderated signup, `user`/`admin`
  roles, owner-scoped access.
- **Layout:** current documentation in `docs/`, evaluation inputs in `datasets/`, measured outputs in
  `benchmarks/`, archived material in `docs/history/`.

Open gaps: CPU-only inference (tens of minutes per book), Telugu/Hindi only, one book processed at a
time, no semantic search (the pgvector schema was removed as dead code — see
`learnings/036-pgvector-removal.md`), and Compose-profile gating for the optional services still
unshipped.

---

## Agent Workflow Rules

### 1. Validate Before Implement
- Every feature/component must go through: feasibility study → PoC → documentation → implementation
- No implementation without a successful PoC documented in `learnings/`
- Use `plans/XXX-*.md` to track each study's scope and success criteria

### 2. Folder Structure Conventions
| Folder | Purpose | Naming |
|--------|---------|--------|
| `plans/` | Project plans, ADRs, study designs | `XXX-plan-description.md` |
| `poc/` | Proofs of concept (validated approaches) | `XXX-poc-description.md` |
| `learnings/` | Documented findings, conclusions | `XXX-finding-name.md` |
| `todos/` | Project task tracking, long-running agent tasks | `XXX-todo-description.md` |
| `infra/` | Cloud infrastructure inventory, live resource/task trackers | `descriptive-name.md` |
| `docs/` | Current technical documentation — architecture, API, operations | `kebab-case.md` inside a category |
| `datasets/` | Evaluation data: ground truth, samples, frozen corpus | fixed layout, see `datasets/README.md` |
| `benchmarks/` | Measured outputs and reports | producer-defined |

**Numbering:** three-digit sequential (`001-`, `002-`, …) for `plans/`, `poc/`, `learnings/` and `todos/`. `docs/`, `datasets/` and `benchmarks/` are organised by category instead.

### 3. Incremental Development (When Implementation Starts)
- One small increment at a time
- Test, lint, typecheck after each logical change
- Manual verification at each milestone
- No big-bang implementation

### 4. Documentation Standards
- Current behaviour → `docs/` (index: `docs/README.md`). Update the affected document in the same change
- Archived documents → `docs/history/`; never edit them to match current behaviour
- All findings → `learnings/XXX-*.md` (template in `learnings/README.md`)
- Technical decisions → `plans/` (ADRs) or `learnings/`
- No host-specific detail (IPs, node names, panel ports, credentials) in tracked files; use the gitignored `infra/local/`
- Keep relative documentation links resolvable

### 5. Commit Guidelines
- Do not make one giant commit.
- Commit code in logical order, break changes into smaller commits
- Commit message must have a heading and descriptive body
- Do not add co-author trailing lines

---

## Agent Coordination

- Check `learnings/README.md` for completed studies before starting new work
- Before creating or using any GCP/compute resource, read `infra/gcp-test-nodes.md` and claim a node in its live tracker
- Post new findings to `learnings/` after each experiment or PoC
- Update relevant `plans/XXX-*.md` with results
- No parallel work on dependent studies (see plan dependencies)

---

## Escalation

If a feasibility study reveals a blocker (e.g., OCR accuracy too low on Indic scripts, LLM extraction unreliable):
1. Document in `learnings/XXX-blocker-name.md`
2. Update the relevant `plans/XXX-*.md` with alternative approaches
3. Notify user for product-level decision (scope change, pivot, etc.)
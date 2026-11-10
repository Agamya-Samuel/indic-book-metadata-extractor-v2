# Indic Book Metadata Extractor — Agent Instructions

## Current Phase: Pipeline Hardening & Metadata Quality

The core platform is implemented and deployed (staging + production via Dokploy): PDF upload → page selection → preprocessing → OCR review → LLM extraction → metadata review → library, plus an admin panel and bulk operations (OpenRefine → Wikibase/QuickStatements). Current work focuses on extraction reliability and metadata quality:

- Hardened extraction pipeline: DB constraints, concurrency-safe OCR corrections, audit trails, per-stage lifecycle tracking (`book_stage_status`)
- Multi-tier Indic OCR: stock Tesseract models, Sauvola binarization, dictionary-based post-processing
- Hybrid extraction with per-field provenance; default LLM is Qwen2.5 7B via Ollama (replaced Airavata)
- Open gaps: CPU-only inference (~10–20 min/book), Telugu/Hindi only, no authentication, pgvector semantic search not yet implemented

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
| `probing/` | Feasibility experiments, investigations | `XXX-probing-description.md` |
| `poc/` | Proofs of concept (validated approaches) | `XXX-poc-description.md` |
| `fixtures/` | Test data, sample inputs, ground truth | `XXX-fixtures-description.md` |
| `learnings/` | Documented findings, conclusions | `XXX-finding-name.md` |
| `todos/` | Project task tracking, long-running agent tasks | `XXX-todo-description.md` |
| `infra/` | Cloud infrastructure inventory, live resource/task trackers | `descriptive-name.md` |

**Numbering:** Three-digit sequential (`001-`, `002-`, etc.) across all folders.

### 3. Incremental Development (When Implementation Starts)
- One small increment at a time
- Test, lint, typecheck after each logical change
- Manual verification at each milestone
- No big-bang implementation

### 4. Documentation Standards
- All findings → `learnings/XXX-*.md`
- Use the template in `learnings/README.md`
- Update PRODUCT.md only for product-level changes
- Technical decisions → `plans/` (ADRs) or `learnings/`

### 5. Commit Guidelines
- Do not make one giant commit.
- Commit code in logical order, break changes into smaller commits
- Commit message must have a heading and descriptive body
- Do not add co-author trailing lines

---

## Agent Coordination

- Check `learnings/README.md` for completed studies before starting new work
- Before creating or using any GCP/compute resource, read `infra/gcp-test-nodes.md` and claim a node in its live tracker
- Post new findings to `learnings/` after each probing/PoC
- Update relevant `plans/XXX-*.md` with results
- No parallel work on dependent studies (see plan dependencies)

---

## Escalation

If a feasibility study reveals a blocker (e.g., OCR accuracy too low on Indic scripts, LLM extraction unreliable):
1. Document in `learnings/XXX-blocker-name.md`
2. Update `plans/001-project-architecture.md` with alternative approaches
3. Notify user for product-level decision (scope change, pivot, etc.)
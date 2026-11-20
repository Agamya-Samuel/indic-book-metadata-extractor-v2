# Decisions and Findings Index

The project keeps two working records outside `docs/`, by convention set in `AGENTS.md`:

- **`plans/`** — intent. A proposal written *before* work starts: scope, success criteria, approach.
- **`learnings/`** — evidence. A record written *after* work finishes: measurements, outcomes, and what
  the numbers mean.

Neither is "current truth". These are append-only history. Where a plan and a learning disagree, the
learning wins; where either disagrees with the code, **the code wins**. `docs/` describes the present.

This page indexes both so they are navigable without rearranging them.

---

## How to read these

| Question | Look in |
| --- | --- |
| "Why is OCR this way?" | The relevant `learnings/02x-ocr-*` record, then `processing/ocr.md` |
| "What were we planning to do?" | `plans/*` |
| "Did it work?" | Matching `learnings/*-outcome.md` or benchmark record |
| "What does the system do *now*?" | `docs/` |

A plan's **status line** is the fastest signal: `Implemented`, `Approved`, `In progress`, `proposed`,
or `complete`.

---

## Plans

| # | Title | Status |
| --- | --- | --- |
| 002 | [Ground-Truth Dataset from Wikimedia Commons](../../plans/002-ground-truth-poc.md) | Plan → awaiting approval |
| 003 | [OCR Engine Selection for Open Book Map](../../plans/003-ocr-engine-evaluation.md) | Decided 2026-11-13 — engines locked |
| 004 | [LLM Selection for Indic Metadata Extraction (49 fields)](../../plans/004-llm-model-evaluation.md) | In progress — accuracy arm partial |
| 005 | [Authentication and Role-Based Access Control](../../plans/005-auth-rbac.md) | Implemented |
| 006 | [UI/UX Overhaul: Book Workflow + Admin Operations](../../plans/006-ui-ux-workflow-admin.md) | Approved |
| 007 | [Moderated Signup, Admin-Only Library, Owner-Only Access](../../plans/007-moderated-signup-admin-library.md) | Implemented 2026-11-12 |
| 008 | [UI/UX Redesign: Unify the Composition Layer](../../plans/008-ui-ux-composition-redesign.md) | Approved |
| 009 | [Metadata-Page Selection (front/back window)](../../plans/009-metadata-page-selection.md) | POC run — labelling flawed |
| 010 | [In-app notifications and email alerts](../../plans/010-notifications.md) | Implementation started |
| 011 | [Ground-Truth Source Expansion](../../plans/011-ground-truth-source-expansion.md) | Phases 1 & 3 done; Phase 2 pending |
| 011 | [Launch readiness](../../plans/011-launch-readiness.md) | Code complete, deployed |
| 012 | [Route `LLMService` through Ollama's native endpoint](../../plans/012-llm-service-native-endpoint.md) | Implemented 2026-11-15 |
| 013 | [Production Hardening: End-to-End Reliability](../../plans/013-production-hardening.md) | Complete 2026-11-14 |
| 014 | [API + UI Pagination](../../plans/014-api-pagination.md) | — |
| 015 | [Integrated OCR Reference and Metadata Review](../../plans/015-integrated-ocr-metadata-review.md) | — |
| 017 | [Telugu OCR Engine Integration](../../plans/017-telugu-ocr-engine-integration.md) | Implemented 2026-11-15 |
| 018 | [Prompt Engineering for 49-Field Extraction](../../plans/018-prompt-optimization.md) | Approved; harness built |
| 019 | [OCR Accuracy Improvement (Hindi + Telugu)](../../plans/019-ocr-accuracy-improvement.md) | Proposed |
| 020 | [OCR Language Integrity and Page-Type Routing](../../plans/020-ocr-language-and-page-type-routing.md) | Complete, production-verified |

> Two files share the number 011, and `plans/` has no 001 or 016. Numbers were allocated
> sequentially by date, not by index, so gaps and duplicates exist. Treat the filename as the
> identifier, not the number.

---

## Learnings

### Ground truth and evaluation

| # | Title | Outcome |
| --- | --- | --- |
| 001 | [Ground-Truth Dataset: Feasibility & Source Survey](../../learnings/001-ground-truth-dataset-feasibility.md) | Complete → PoC recommended |
| 002 | [Enriching GT from Wikisource + Internet Archive](../../learnings/002-gt-enrichment-sources.md) | — |
| 003 | [Harness Wiring + Scaling GT from Wikisource](../../learnings/003-harness-and-wikisource-scaling.md) | — |
| 005 | [LLM Model Evaluation](../../learnings/005-llm-model-evaluation.md) | Resource/speed arm measured |
| 006 | [First Real End-to-End Accuracy](../../learnings/006-first-real-accuracy.md) | — |
| 009 | [Decision & Classification Models vs Generative LLMs](../../learnings/009-decision-classification-models.md) | — |
| 010 | [LLM Shortlist Benchmark + Ollama RAM footprint](../../learnings/010-llm-shortlist-benchmark.md) | — |
| 013 | [Verified-GT Shortlist, OCR Model Variant, Recall Diagnosis](../../learnings/013-verified-shortlist-and-ocr.md) | — |
| 019 | [GT Corpus Enrichment (Hindi, catalogue depth)](../../learnings/019-gt-corpus-enrichment.md) | Phases A & B done |
| 022 | [GT Source Expansion: scale, catalogue depth, script fix](../../learnings/022-gt-source-expansion.md) | Phase 1 done |

### OCR

| # | Title | Outcome |
| --- | --- | --- |
| 004 | [OCR-Stage Error (Tesseract Telugu) vs Wikisource](../../learnings/004-ocr-stage-cer.md) | — |
| 020 | [OCR Engine Benchmark on Real Indic Scans](../../learnings/020-ocr-engine-benchmark.md) | — |
| 021 | [OCR Engine Operational Requirements](../../learnings/021-ocr-engine-operational-requirements.md) | — |
| 026 | [Review of the Hindi/Telugu OCR Improvement Strategy](../../learnings/026-ocr-accuracy-strategy-review.md) | — |
| 027 | [Default Preprocessing Is a 1.5× Upscale, and It Costs Accuracy](../../learnings/027-default-preprocessing-upscale-benchmark.md) | — |
| 028 | [The Telugu Line Model Does Not Want the Upscale Either](../../learnings/028-line-model-preprocessing-benchmark.md) | — |
| 029 | [Language Routing, the `+eng` Model, and Typeface Limits](../../learnings/029-ocr-language-routing-and-font-benchmarks.md) | — |
| 030 | [Telugu Line-Model Fine-Tune (and Hindi Negative Results)](../../learnings/030-telugu-line-finetune-results.md) | — |

### LLM configuration and prompting

| # | Title | Outcome |
| --- | --- | --- |
| 012 | [Route `LLMService` through the native endpoint](../../plans/012-llm-service-native-endpoint.md) | Implemented, verified |
| 017 | [Self-Hosted LLM Configuration: Parameter Reference](../../learnings/017-llm-configuration-research.md) | Provisional |
| 018 | [LLM Configuration Validation on Verified Telugu Books](../../learnings/018-llm-config-validation.md) | Complete (32/32 calls) |
| 025 | [Prompt Engineering for 49-Field Extraction](../../learnings/025-prompt-optimization.md) | Harness built |

### Platform, operations and reliability

| # | Title | Outcome |
| --- | --- | --- |
| 011 | [Deployment Exposure Audit & Single-Origin Fix](../../learnings/011-deployment-exposure-and-single-origin.md) | — |
| 014 | [Frontend + Backend Route Redesign Outcome](../../learnings/014-routing-redesign-outcome.md) | Shipped |
| 015 | [Service Inventory, Memory Profile and Gating](../../learnings/015-service-inventory-and-gating.md) | Measured; gating **not implemented** |
| 016 | [The Pipeline Could Not Process a Book at HEAD](../../learnings/016-pipeline-non-functional-at-head.md) | All three fixed |
| 023 | [Production Hardening: End-to-End Outcome](../../learnings/023-production-hardening-outcome.md) | Complete |
| 024 | [Host Network Recovery and gemma4 Resource Reality](../../learnings/024-host-network-and-gemma-resource-reality.md) | — |
| 036 | [pgvector Semantic Search: Cost Analysis and Removal](../../learnings/036-pgvector-removal.md) | Removed as dead code |
| 037 | [PostgreSQL 18 Upgrade (Fresh Volume)](../../learnings/037-postgres-18-upgrade.md) | Applied |

### Product and UI

| # | Title | Outcome |
| --- | --- | --- |
| 007 | [UI/UX Audit: Book Workflow + Admin Dashboard](../../learnings/007-ui-ux-workflow-admin-audit.md) | — |
| 008 | [Auth/RBAC Implementation Outcome](../../learnings/008-auth-rbac-outcome.md) | — |
| 012 | [Moderated Signup, Admin-Only Library, Owner-Only Access](../../learnings/012-moderated-signup-outcome.md) | Implemented |

*(Numbering collides across topics — `012` exists three times in `learnings/`. Use the full filename.)*

---

## Records that are known stale

These are not wrong history; they were accurate when written. But they no longer describe the code,
so do not use them as a reference for current behaviour.

| Record | What changed since |
| --- | --- |
| [learnings/015](../../learnings/015-service-inventory-and-gating.md) | Says a 6 GB cap and `phi4-mini` preloaded. Compose now uses `mem_limit: 9g` and `gemma4:e4b`. Memory measurements remain valid. |
| [learnings/014](../../learnings/014-routing-redesign-outcome.md) | Refers to `/library` and `/bulk-operations`. Both routes are gone — `/library` was removed and bulk moved to `/admin/bulk`. |
| [plans/014](../../plans/014-api-pagination.md), [plans/015](../../plans/015-integrated-ocr-metadata-review.md) | No status line recorded, so "is this done?" cannot be answered from the file. |

### Missing numbers

`plans/` has no `001` or `016`; `learnings/` has no gap but reuses `011`, `012`, `013` and `015`
across different topics. This is historical, and renumbering would break cross-references, so it is
left alone.

---

## Adding a new record

1. Take the next three-digit number for the folder. Do not reuse a number.
2. `plans/XXX-*.md` before starting work; `learnings/XXX-*.md` after finishing.
3. Put a `**Status:**` line near the top — this index depends on it.
4. Link the plan from its learning, and the learning from its plan.
5. If the work changes the system's behaviour, update the relevant `docs/` file too. The record is
   history; `docs/` is the present.

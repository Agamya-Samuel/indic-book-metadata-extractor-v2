# Learnings Folder

This folder contains documented findings from feasibility studies, proofs of concept, and probing experiments.

## Naming Convention
`XXX-finding-descriptive-name.md` — three-digit sequential numbering shared across `plans/`, `probing/`, `poc/`, `fixtures/`, `learnings/`.

## Template
Each learning document should include:
1. **Date** — when the study concluded
2. **Study Context** — what was being evaluated and why
3. **Summary** — one-line conclusion
4. **Key Findings** — detailed evidence, organized by topic
5. **Recommendation** — go/no-go with rationale
6. **Next Steps** — concrete actions (new probing, PoC, plan updates)
7. **References** — links to sources, PRs, docs, code

## Current Learnings

- [001 — Ground-Truth Dataset Feasibility & Source Survey](001-ground-truth-dataset-feasibility.md) — Schema is 49 fields (not 52); no drop-in Indic PDF+metadata dataset; build from Wikidata/Commons/Wikisource + s1.md seed + manual verification (CC/PD-only). Metrics, split, and phased PoC proposed.
- [005 — LLM Model Evaluation for Metadata Extraction](005-llm-model-evaluation.md) — Resource/speed arm measured on the 4 vCPU/16 GB node: `qwen3:4b-instruct-2507` is the safest drop-in (valid JSON, ~½ RAM, ~1.6× the 7B baseline); `qwen3.5:4b` fastest only with `think:false` (default returns empty). Accuracy arm pending GT verification.
- [002 — GT Enrichment from Wikisource + Internet Archive](002-gt-enrichment-sources.md) — Grew GT to 14 books (9 tel/5 hin), 4–11/49 fields each; te.wikisource Index header + IA metadata are the productive sources; hi.wikisource has no proofreading; remaining fields are genuinely absent.
- [003 — Harness Wiring + Scaling GT from Wikisource Index Pages](003-harness-and-wikisource-scaling.md) — 19 books (14 tel/5 hin), 14 with page-level OCR GT; harness `--ground-truth` mode scores the corpus (stub-validated; real run needs Ollama+Postgres).
- [004 — OCR-Stage Error vs Wikisource GT](004-ocr-stage-cer.md) — Measured Tesseract Telugu CER ≈ 0.45 median (range 0.20–0.62); OCR is the dominant error source. Also: `PDFService.render_pages` (used by the harness) does not exist.
- [007 — UI/UX Audit: Book Workflow + Admin Dashboard](007-ui-ux-workflow-admin-audit.md) — Full audit with verified file:line defects: five P0 data-integrity bugs (LLM-config trap, OCR editor state bleed, fake stepper, re-run OCR dead end, preprocessing config misuse), per-stage gaps, admin duplication; phased plan approved (see `plans/006`, `todos/008`).
- [008 — Auth/RBAC Implementation Outcome](008-auth-rbac-outcome.md) — Shipped cookie+CSRF sessions, rotating single-use refresh, owner-scoped enforcement, metadata-only public catalog, and admin user management on the existing stack (no pipeline changes); residual gaps: no per-user quotas, auth-only rate limits, SMTP dependency.

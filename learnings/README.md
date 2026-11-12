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
- [006 — First Real End-to-End Accuracy](006-first-real-accuracy.md) — Harness run on GCP `test-node-3` (8 books, `qwen2.5:3b`): micro-F1 **0.308**; structured fields work, name/text fields precise but low-recall; `description_work` fails.
- [010 — LLM Shortlist Benchmark + Ollama RAM](010-llm-shortlist-benchmark.md) — 49-field sweep on 1 book: **phi4-mini F1 0.50** > qwen2.5:3b 0.31 > qwen3-4b-instruct-2507 / qwen2.5:7b 0.20; measured RAM 4B=3.38 GB, 7B=4.83 GiB. Fixed harness hardcoded-`tel` language bug.
- [007 — UI/UX Audit: Book Workflow + Admin Dashboard](007-ui-ux-workflow-admin-audit.md) — Full audit with verified file:line defects: five P0 data-integrity bugs (LLM-config trap, OCR editor state bleed, fake stepper, re-run OCR dead end, preprocessing config misuse), per-stage gaps, admin duplication; phased plan approved (see `plans/006`, `todos/008`).
- [008 — Auth/RBAC Implementation Outcome](008-auth-rbac-outcome.md) — Shipped cookie+CSRF sessions, rotating single-use refresh, owner-scoped enforcement, metadata-only public catalog, and admin user management on the existing stack (no pipeline changes); residual gaps: no per-user quotas, auth-only rate limits, SMTP dependency.
- [009 — Specialized Decision & Classification Models vs Generative LLMs](009-decision-classification-models.md) — Desk study + live probes of OpenRouter's Decisions/Extractions categories ($0.0006 spent). Decisions return typed judgments, not values — the alpha API 400s on any value-typed field; `choice`/`noul` classify Hindi/Telugu well (language survives p=0.45 corruption). Paid probe: clairic/ScaleDown extract Indic values from *text* (5/5, 4/5) but **neither reads a Telugu scan** — the OCR bypass is closed. Recommendation: keep the generative LLM as extractor; decision models only as a calibrated *validator* behind a measured gate.
- [011 — Deployment Exposure Audit & Single-Origin Fix](011-deployment-exposure-and-single-origin.md) — Prod was undeployable since the auth commit (two `:?` env vars missing from Dokploy → 404), and once up every mutation 403'd because the API sat on its own subdomain (host-only CSRF cookie unreadable by the frontend). Fixed by making the frontend host the single public entry point with the API at `/api`; audited and closed the rest of the exposure (backend, flower, Dokploy :3000, Traefik :8080).

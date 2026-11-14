# 015 — Documented but NOT implemented

- **Date:** 2026-11-14
- **Purpose:** Everything the markdown corpus describes as existing, planned, or required that is **absent from the code at HEAD**. Each item was checked by reading the doc claim and then searching the code. The inverse (docs that are stale because the code *does* have the feature) is in §6 — do not rebuild those.
- **Method:** doc claim → `Grep`/`Read` against `backend/app`, `frontend/src`, `docker/`, `.github/`. "Verified absent" means a targeted search returned nothing.
- **Status snapshot:** checked on branch `feat/ui-composition-redesign`.

---

## 1. LLM extraction

| # | Documented (where) | Code reality | Impact | Owner |
|---|---|---|---|---|
| 1 | Route `LLMService` through Ollama's **native `/api/chat`** with `think:false` — [plans/012](012-llm-service-native-endpoint.md) | `llm_service.py:99` still calls the **OpenAI-compatible** `/v1`; no `LLM_NATIVE_ENDPOINT` anywhere in `backend/app` | **Production cannot use `gemma4:e4b`** — the `/v1` path drops `think`, so thinking models return empty `content` (every batch empty). The measured best Telugu model is unusable. Needs a Dokploy deploy | Dev (+ user to deploy) |
| 2 | **Repetition/loop guard** before shipping `phi4-mini` — [learnings/018](018-llm-config-validation.md) finding 5, [plans/012](012-llm-service-native-endpoint.md) risks | No repeated-n-gram detection in `llm_service.py` | `phi4-mini` looped to the token cap and returned **invalid JSON despite schema-constrained decoding** (measured, 018) | Dev |
| 3 | `num_ctx` **4096** and one `max_tokens` value — [learnings/017](017-llm-configuration-research.md) §1, [018](018-llm-config-validation.md) | `docker/Modelfile.phi4-mini` says `num_ctx 8192` while the container env sets `CONTEXT_LENGTH=4096`; app default `max_tokens=256` vs `ExtractionRequest` default `512` | The documented decision is not reflected consistently; effective context is ambiguous | Dev |
| 4 | **NER extractor** (`spaCy xx_ent_wiki_sm`) for person names, with `target_fields` plumbing ready — [known-limitations](../docs/known-limitations.md) §"What's not yet implemented" item 2 | No `spacy` / `ner_extractor` anywhere in `backend/` | `author`, `translator`, `editor` stay LLM-only → low recall (the #1 open accuracy gap) | Dev |
| 5 | **Per-language prompt templates** (Telugu/Hindi/English variants) — known-limitations §LLM | One `SYSTEM_PROMPT_TEMPLATE` + one `EXTRACTION_PROMPT_TEMPLATE`; only the few-shot examples vary by language (`prompts.py`) | Partial: per-language examples exist, per-language *templates* do not | Dev |

> Note: §1 item 5 and the "few-shot" claim in the same doc conflict with each other — the few-shot is implemented, the per-language templates are not (see §6).

---

## 2. OCR

| # | Documented (where) | Code reality | Impact | Owner |
|---|---|---|---|---|
| 6 | **Telugu line-model engine** (`harsha-desaraju/telugu-ocr-model`, CER 0.16 vs 0.40) is the **chosen** engine — [learnings/020](020-ocr-engine-benchmark.md), [021](021-ocr-engine-operational-requirements.md), [todos/012](012-ocr-engine-integration-handoff.md), [known-issues](../docs/known-issues.md) | Exists only in `backend/scripts/ocr_bench/`; **not** wired into `app/services/ocr_service.py` | The single largest accuracy lever (halves Telugu CER) is unshipped; all LLM accuracy stays OCR-bound | Dev |
| 7 | **`GET /api/admin/ocr-corrections`** endpoint to measure raw→corrected edit rate — [plans/003](003-ocr-engine-evaluation.md) §risks, [learnings/021](021-ocr-engine-operational-requirements.md) | No such route in `backend/app/api` | Cannot measure reviewer-effort (the chosen PoC gate) | Dev |
| 8 | **Page-rotation detection** (OSD `--psm 1` on page 1) — known-limitations §OCR "Mitigations NOT yet implemented" | No `rotate`/`osd` handling in `ocr_service.py` | Rotated title/colophon pages OCR as garbage | Dev |
| 9 | **Script-aware preprocessing** (different denoise params per script) — same known-limitations list | Preprocessing exists but is not script-aware (no per-script branch found) | Low-confidence absence — re-verify before acting | Dev |

---

## 3. Search & ML

| # | Documented (where) | Code reality | Impact | Owner |
|---|---|---|---|---|
| 10 | **pgvector semantic search** — schema exists, search "not yet implemented" — [README](../README.md#L199), [known-issues](../docs/known-issues.md), [changelog](../docs/changelog.md), [AGENTS.md](../AGENTS.md) | Only `backend/app/models/embedding.py` + the model import exist; **no service populates or queries** it (grep for `embedding` in `backend/app` returns only the model) | The 768-dim `embeddings` table is dead schema | Dev |

---

## 4. Limits, policy & CI

| # | Documented (where) | Code reality | Impact | Owner |
|---|---|---|---|---|
| 11 | **Per-user quotas** ("any approved user can upload/run unlimited jobs") — README, known-limitations | No `quota` code in `backend/app` | A single user can saturate the 4-core box | Dev |
| 12 | **CI gating on the accuracy harness** (`test-accuracy` job failing below an F1 threshold) — known-limitations item 5 | `.github/workflows/` has `ci.yml` + `security.yml`; **no** `test-accuracy` reference | Accuracy regressions are not caught in CI | Dev |
| 13 | **Indic transliteration in the accuracy harness** so cross-script values aren't scored 0.0 — known-limitations item 4 | Harness records `script_match` but does not transliterate | Roman-vs-Telugu values depress F1 (affects `author` on every Telugu book) | Dev |
| 14 | **`probing/` and `fixtures/` folders** mandated by the workflow — [AGENTS.md](../AGENTS.md) §Folder Structure | Both directories are **MISSING** (plans, poc, learnings, todos, infra exist) | The documented study workflow cannot be followed as written | Dev |

---

## 5. Operator actions (documented, blocked on access — not code)

From [todos/014](014-launch-readiness.md) §"Remaining operator actions" (need the Cloudflare account):

- Restrict origin ingress to Cloudflare ranges (or Cloudflare Tunnel).
- Edge WAF + rate rule for `/api/auth/*`.
- Offsite backup destination + credentials.
- Uptime/alerting monitor against `/api/health`.

Owner: **user** (credentials). Also documented in [known-issues](../docs/known-issues.md) §Deployment.

---

## 6. The inverse: docs that are STALE (code already has it)

Do **not** build these — the documentation is out of date, the feature exists. Listed so they are not mistaken for gaps.

| Doc claim | Code reality |
|---|---|
| known-issues: "Page extraction is still synchronous … planned but not implemented" | Now Celery-backed: `books.py:314` `render_pages_for_book.delay(...)`, plus `apply_preprocessing_bulk.delay` and `preprocess_pages_for_book.delay` |
| known-limitations §LLM: "Few-shot examples … current prompt has zero examples" | `prompts.py` ships `FEW_SHOT_EXAMPLES` for `tel`/`hin`/`eng` |
| known-limitations §LLM: "The current model is `ai4bharat/Airavata-GGUF`" | Production preloads **`phi4-mini`** (`docker-compose.production.yml` `OLLAMA_PRELOAD_MODEL`) |
| learnings/021: "`ocr_results.corrections` is never written" | Now written — `ocr_tasks.py:80` sets `existing.corrections` (via `ocr_postprocess`) |
| AGENTS.md: "no authentication" | Auth/RBAC shipped (learnings 008/013, `plans/005`) |
| AGENTS.md / changelog: "pgvector semantic search not yet implemented" | Still true — not stale (see §3 item 10) |
| `docs/agent-browser-testing-handoff.md` ⬜ Phase-2 list (SaveBar, evidence nav, field revert) | `frontend/src/components/shared/save-bar.tsx` and metadata-review wiring now exist → treat that ⬜ block as **unreliable** |
| learnings/017 & 018: "Ollama 6 GiB cap" | Raised to **7 GB** on 2026-11-13 (known-issues §Ollama memory cap; `docker-compose.production.yml` `mem_limit: "7g"`) — my own docs are stale here |

## 7. In progress (not a docs-only gap)

[plans/013-production-hardening](013-production-hardening.md) — status "in progress (started 2026-11-14)": workflow-breaking defects, cancellation/retries, data isolation, mail path. Track it there rather than here.

## 8. Low confidence — re-verify before acting

- **Rate limiting scope.** README says limits exist "only on the auth endpoints", but `backend/app/main.py:70` defines a global `RateLimitMiddleware`. Read the middleware before changing anything.
- **Publisher whitelist size** ("~30") — not counted reliably; the list may already be larger.
- **`docs/monitoring.md`** New Relic claims vs `NEW_RELIC_ENABLED=false` default — a deployment-config question, not code.
- **plans/009 metadata page-selection** — the doc itself says the runner is "not wired into production"; not independently verified.

## 9. Summary

| Bucket | Count |
|---|---|
| Verified documented-but-absent (code change needed) | **13** (§1–§4) |
| Documented, blocked on operator access | 4 (§5) |
| Stale docs (feature exists — do not rebuild) | 7 (§6) |
| In progress elsewhere | 1 (§7) |

**Top 3 by impact, in order:**

1. **Native-endpoint fix (§1.1)** — without it the measured-best Telugu model cannot run in production at all. Needs a Dokploy deploy (user-triggered).
2. **Telugu OCR engine integration (§2.6)** — halves Telugu CER; the documented root cause of the whole recall ceiling.
3. **Loop guard (§1.2)** — the only thing standing between `phi4-mini` and silently invalid JSON in production.


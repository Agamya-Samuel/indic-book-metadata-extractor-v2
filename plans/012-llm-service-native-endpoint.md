# 012 — Route `LLMService` through Ollama's native endpoint (enable gemma4 in production)

- **Date:** 2026-11-14
- **Status:** **Implemented and verified on `oki` (2026-11-15)** — gemma4 pulled, native call returns valid JSON, and the default model is switched. The Dokploy deploy is the remaining step.
- **Why:** the best-measured model is `gemma4:e4b` (`think:false`) — Telugu 0.523, Hindi 0.640 vs `phi4-mini` 0.400 — but it **cannot run on the current production call path**.

## Problem

`LLMService.extract_batch` calls Ollama through the **OpenAI-compatible** client
(`instructor.from_openai(OpenAI(base_url="{ollama}/v1"), Mode.MD_JSON)`) and passes
`extra_body={"think": False}`. That endpoint **drops the flag**, so a thinking model
(`gemma4`) spends its whole output budget on the reasoning channel and returns
**empty `content`** — every batch comes back empty. Proven in [learnings/019](../learnings/019-gt-corpus-enrichment.md)
and [022](../learnings/022-gt-source-expansion.md); the harness `--native` path
([`scripts/native_extract.py`](../backend/scripts/native_extract.py)) already works around it.

## Change (single chokepoint)

`extract_batch` is the **only** place the app calls an LLM. Add an **opt-in native path**:

- When enabled (env `LLM_NATIVE_ENDPOINT=true`, default off), POST to `{ollama}/api/chat`
  with `"think": false` and `options={num_predict, temperature}`, reading `message.content`.
- **Keep the schema instruction** — `render_extraction_prompt` already lists the exact
  fields, and `instructor`'s MD_JSON contribution was a schema hint + parsing. Replicate the
  hint in the prompt and parse the reply with a **tolerant JSON extractor** (grab the outer
  `{...}`), with **one retry** and the existing empty-batch fallback.
- Preserve everything else: circuit breaker, `usage_stats` statuses, `_strip_schema_echoes`,
  raw-response capture, per-batch timeout.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Loss of schema-constrained decoding → invalid JSON | tolerant parse + retry + fallback (phi4-mini already needs a loop guard — [learnings/017](017-llm-configuration-research.md)) |
| Production regression | flag defaults **off**; switch on only after a staging/verification run; revert = unset env |
| Two code paths to maintain | keep the OpenAI path for non-thinking models; native path only when the flag is set (or when the model is in the thinking set) |
| Silent empty output (the current bug!) | native path checks for empty `content` and records `empty_response`, as today |

## PoC → test → rollout

1. **PoC (on a node):** implement the native branch behind the env flag; run the **real pipeline**
   (upload → page select → OCR → extraction) on one book with `gemma4:e4b` and confirm
   `awaiting_review` with non-empty `llm_runs`. (The harness `--native` already proves the
   extraction call; this proves the *service* path.)
2. **Unit tests:** tolerant parser, flag gating, empty-response detection.
3. **Verification:** re-run the harness with and without the flag on a couple of books — F1 must
   match the `--native` numbers.
4. **Rollout:** set `LLM_NATIVE_ENDPOINT=true`, `docker/Modelfile` + `OLLAMA_PRELOAD_MODEL=gemma4:e4b`,
   commit, deploy via Dokploy (user-triggered), verify on the deployed host.

## Success criteria

- Production extracts with `gemma4:e4b` end-to-end, valid JSON per batch, no empty-response batches.
- Measured F1 on the deployed host ≥ the harness numbers (Telugu ≈ 0.52, Hindi ≈ 0.64).
- Flag off + `phi4-mini` ⇒ behaviour identical to today (no regression). Thinking
  models force the native path regardless of the flag.

## Implementation (2026-11-15)

- `Settings.llm_native_endpoint` (env `LLM_NATIVE_ENDPOINT`, default `false`), wired into
  `docker-compose.production.yml` and `docker-compose.staging.yml` for **both** the backend
  and the worker, plus `.env.example` / `.env.{production,staging}.example`.
- `LLMService.extract_batch` branches to `_extract_batch_native`: POST `{ollama}/api/chat`
  with `think:false` (thinking families only — sending it to `phi4-mini` errors),
  `options={num_predict, temperature}`, and `stream:false`; reads `message.content`.
- The schema hint instructor used to inject is replaced by `_json_schema_hint` appended to the
  prompt (so the stored audit prompt matches exactly what was sent). Replies go through
  `_parse_json_object` (tolerant of prose/fences), with **one retry**, then the existing
  `fallback` / `empty_response` statuses and empty-batch fallback.
- Circuit breaker, raw-response capture, `_strip_schema_echoes`, the 1200 s per-batch timeout,
  and the whole OpenAI path are unchanged. Flag off ⇒ byte-for-byte the old behaviour.
- Tests: `backend/tests/unit/test_llm_service.py` covers the parser, schema hint, flag gating,
  success/`done_reason`, retry recovery, empty content, unparseable content, and transport
  failure. `pytest tests/unit -q` → **281 passed**; `ruff` clean.
- **Production state (2026-11-15):** `gemma4:e4b` is pulled on `oki` (6.6 GB, 7.5B, Q4_K_M,
  thinking default true). A native `/api/chat` call with `think:false` returned valid JSON;
  residency is **6.71 GiB idle / 7.9 GiB during a real extraction**, so the Ollama cap moved
  7 GB → **9 GB**. The compose preload, `LLM_NATIVE_ENDPOINT=true`, and the `gemma4:e4b`
  default are deployed; one Telugu book completed end to end with 8/8 non-empty runs.
- **The model is pinned:** `ExtractionRequest` rejects anything except `gemma4:e4b`, the LLM
  configuration page shows the model read-only, and the Ollama entrypoint warms gemma at boot
  (keep-alive 30m). Only one model is ever resident (`OLLAMA_MAX_LOADED_MODELS=1`), with a 9 GB
  cap. `phi4-mini` remains the code-level rollback, not a user choice.
- **Egress is no longer a blocker** (PyPI ~32 MB/s, HF ~1.1 MB/s — [learnings/024](../learnings/024-host-network-and-gemma-resource-reality.md)).

## Open questions

- Keep the OpenAI path at all, or move fully to native (simpler, one path) once proven?
- `think:false` for gemma4 only, or also send it for `qwen3*` families (same trap)?

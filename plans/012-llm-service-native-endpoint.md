# 012 — Route `LLMService` through Ollama's native endpoint (enable gemma4 in production)

- **Date:** 2026-11-14
- **Status:** Plan — implement after the model×language matrix ([plans/011](011-ground-truth-source-expansion.md) task 2). **Needs a production deploy (Dokploy).**
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
- Flag off ⇒ behaviour identical to today (`phi4-mini`, no regression).

## Open questions

- Keep the OpenAI path at all, or move fully to native (simpler, one path) once proven?
- `think:false` for gemma4 only, or also send it for `qwen3*` families (same trap)?

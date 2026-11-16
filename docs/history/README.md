# Archived Documentation

Everything in this directory describes a **past state of the project**. It is kept for provenance —
so a decision can be traced, or an old measurement checked — and is not a reference for current
behaviour.

Current documentation lives one level up in [`docs/`](../README.md). Where an archived document and
the current tree disagree, the current tree wins.

---

## What is here, and why

| File | Superseded by | Why it was kept |
| --- | --- | --- |
| `api-reference-2026-11.md` | [reference/api.md](../reference/api.md) | Per-endpoint bodies were merged forward; the original is the raw record |
| `local-development-guide-2026-11.md` | [development/local-development.md](../development/local-development.md) | Native setup merged forward |
| `monitoring-2026-11.md` | [operations/monitoring.md](../operations/monitoring.md) | New Relic setup merged forward |
| `ocr-setup-2026-11.md` | [processing/ocr.md](../processing/ocr.md), [development/local-development.md](../development/local-development.md) | Install content merged forward |
| `runbook-2026-11.md` | [operations/runbook.md](../operations/runbook.md) | Restore drill merged into [backup-and-recovery](../operations/backup-and-recovery.md) |
| `developer-guide-2026-11.md` | `application/` + `development/` | Split across the structured tree |
| `metadata-fields-2026-11.md` | [reference/metadata-fields.md](../reference/metadata-fields.md) | Wikidata mapping merged forward |
| `wikibase-reference-2026-07.md` | [operations/wikibase-operations.md](../operations/wikibase-operations.md) | Extension list merged forward |
| `known-issues-2026-11.md` | [known-limitations.md](../known-limitations.md) | Consolidated with the limitations document |
| `implementation-plan-2026-05.md` | — | The original 12-week plan; predates implementation |
| `tech-stack-2026-06.md` | [architecture/system-architecture.md](../architecture/system-architecture.md) | Records the stack **before** the move to `gemma4:e4b`; names Airavata |
| `project-overview-original.md` | [README.md](../../README.md) | Third copy of the overview |
| `accuracy-report-day8.md` | [testing/evaluation.md](../testing/evaluation.md) | Airavata-era numbers, kept as evidence |
| `llm-extraction-conversation-log.md` | [processing/extraction.md](../processing/extraction.md) | Investigation narrative; root cause since fixed |
| `llm-extraction-zero-fields-investigation.md` | [processing/extraction.md](../processing/extraction.md) | Same investigation, deep-dive form |
| `agent-browser-testing-handoff.md` | [testing/strategy.md](../testing/strategy.md) | QA takeover brief for one sprint |

---

## Rules for this directory

1. Do not update these files to match current behaviour. If something here becomes relevant again,
   move it back into the tree and rewrite it.
2. Do not link to them from current documentation as if they were authoritative.
3. Adding an archive requires the replacement to exist first. Archive what has been merged, not what
   someone suspects is obsolete.

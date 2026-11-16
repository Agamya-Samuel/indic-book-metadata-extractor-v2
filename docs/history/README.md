# Archived Documentation

Documents that describe a **past state of the project**. They are kept as primary evidence — the
original plan, the measurements taken at the time, an investigation narrative — not as a reference for
current behaviour.

Current documentation lives one level up in [`docs/`](../README.md). Where an archived document and the
current tree disagree, the current tree wins.

---

## What is here, and why

| File | Nature | Why it was kept |
| --- | --- | --- |
| `implementation-plan-2026-05.md` | Original 12-week plan | Records the scope the project was actually built against |
| `tech-stack-2026-06.md` | Stack snapshot | Documents the stack **before** the move to `gemma4:e4b`; names Airavata |
| `accuracy-report-day8.md` | Measurement | Airavata-era accuracy numbers, kept as evidence rather than rewritten |
| `llm-extraction-conversation-log.md` | Investigation narrative | The reasoning trail behind a defect that was later fixed |
| `llm-extraction-zero-fields-investigation.md` | Deep-dive investigation | Same defect, full root-cause analysis |
| `agent-browser-testing-handoff.md` | Sprint handoff | QA takeover brief for one specific period |

These are not duplicated anywhere. Each is the only record of its particular moment.

---

## What was removed

Ten archived documents were deleted after verifying their content had been merged into the current
tree, not merely superseded:

`api-reference`, `local-development-guide`, `monitoring`, `ocr-setup`, `runbook`, `developer-guide`,
`metadata-fields`, `wikibase-reference`, `known-issues`, and the duplicate project overview.

Each was restated in its replacement before deletion — request/response bodies into
[reference/api.md](../reference/api.md), native setup into
[development/local-development.md](../development/local-development.md), agent topology into
[operations/monitoring.md](../operations/monitoring.md), the restore drill into
[backup-and-recovery.md](../operations/backup-and-recovery.md), the Wikidata mapping into
[reference/metadata-fields.md](../reference/metadata-fields.md), and so on. Git history still holds
the originals.

---

## Rules for this directory

1. Do not update these files to match current behaviour. If something here becomes relevant again, move
   it back into the tree and rewrite it.
2. Do not link to them from current documentation as if they were authoritative.
3. Archive what has been merged or is genuine primary evidence — not what merely looks old.
4. Deleting an archive requires proving its unique content survives elsewhere.

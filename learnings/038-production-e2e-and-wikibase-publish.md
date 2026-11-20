# 038 — Production End-to-End Run and Wikibase Publish Paths

**Date:** 2026-11-20

## Study Context

After the PostgreSQL 18 fresh-volume migration, the Telugu line-model restore, and the
pre-launch data cleanup, the production stack needed a real (not theoretical) end-to-end run:
upload → page selection → preprocessing → OCR → LLM extraction → metadata review → export →
Wikibase publish. Both the direct bot publish and the QuickStatements bot path were to be
exercised against the live host.

## Summary

The full pipeline passed end to end on production. OCR used the restored Telugu fine-tuned line
model, the LLM produced 50 fields, and both publish paths created real Wikibase items:
**Q161** via `POST /api/wikibase/publish` (21 claims) and **Q166** via QuickStatements
`run_single_command` (9 claims). QuickStatements **batch** mode remains blocked by a missing
Toolforge batch DB; single-command mode works.

## Key Findings

### Pipeline (real run)

- Book: `19380101_Savitri_Natakamu_Telugu_PDF.pdf` (134 pages), pages 1–8 selected.
- Render ~20 s; preprocessing completed; OCR ~17–19 s.
- Worker log: `Loading Telugu line OCR model '/app/storage/models/telugu-ocr-ft'` — the
  fine-tuned model was used, not the fallback.
- LLM `gemma4:e4b`: 119–333 s depending on page count, 50 metadata fields, status
  `awaiting_review`.
- Review: ground-truth corrections merged, book reached `complete`.

### Export and publish

- `GET /api/books/{id}/export?format=csv` → 1,965 B.
- `POST /api/bulk/export-wikibase?language=tel` → 681 B QuickStatements v1 TSV.
- `POST /api/wikibase/publish` (direct `OpenBookMapBot`) → **Q161**, 21 claims, labels
  `te`/`en`, `P2=Q147` (book), `P15=Q136` (Telugu), `P18=1938`, `P29=134`.
- QuickStatements v1: OAuth login as `Admin`, `api.php?action=import&format=v1` parsed 1
  `CREATE` command; `api.php?action=run_single_command` created **Q166** (9 claims).
- `api.php?action=run_batch` returns `Could not complete the request.`: QS v1's batch path
  needs the Toolforge DBs `quickstatements_p` / `quickstatements_auth`, which this self-hosted
  compose does not provision (`ToolforgeCommon.php` → `tools.db.svc.wikimedia.cloud`).

### Defects found and fixed during the run

1. **Stale property mapping.** `property-mapping.json` still mapped `Q571→Q1`, `Q809→Q2`,
   `Q1568→Q3`, `Q1860→Q4`, but the item cleanup had deleted those items.
   `create-properties.sh` trusts the mapping and skipped them, so publish failed with
   `[[Item:Q2|Q2]] not found`. Removing the four `Q*` entries and re-running the init created
   `Q147` book, `Q136` Telugu, `Q148` Hindi, `Q149` English.
2. **QuickStatements OAuth consumer missing `basic`.** Login succeeded but every
   `wbeditentity` returned *"You do not have the permissions needed to carry out this action."*
   Adding `basic` (plus `editpage`, `highvolume`) to `oauth_registered_consumer.oarc_grants`
   fixed it; no re-registration needed.
3. **Metadata update rejects nulls.** The LLM returns explicit `null` for absent fields; the
   update schema only accepts strings/dicts, so strip `None` before `PUT /metadata`.
4. **Telugu fine-tune restored.** The model was lost when `storage_data` was recreated;
   restored from `/home/agamya/.cache/telugu-ocr-ft/model-ft-ctc` (epoch-4, 311 MB) with
   `model.safetensors` SHA-256 `fbcf8f1441e3ac92101ac6856dbf46110da7e9652303ffe3c73ffb2c9762a1e5`.
   It is now published at [`agamyasamuel/telugu-ocr-ft`](https://huggingface.co/agamyasamuel/telugu-ocr-ft)
   (tag `v1.0.0`, SHA `69d2ddb4ac458ee43f04d27096209fdad7727490`, MIT) and baked into the
   worker image by `docker/Dockerfile.backend`; the local cache is no longer a deploy dependency.

### Cleanup after the run

Deleted the E2E book, all Wikibase items except the four shared stubs
(`Q136`/`Q147`/`Q148`/`Q149`), the six generated notifications, and all active sessions.
Final app DB: **0 books, 3 admins, 0 jobs, 0 notifications, 0 active sessions**; Alembic 022;
Wikibase 4 items; QS logged out. Final backup `indic_books_20261120_102916.dump`.

## Recommendation

- Keep both publish paths: direct `POST /api/wikibase/publish` is the supported scripted path;
  QuickStatements `run_single_command` works for interactive/single-command use.
- If QuickStatements **batch** mode is required, provision `quickstatements_p` /
  `quickstatements_auth` and point `ToolforgeCommon.php` at the local MySQL (or replace the
  wrapper). Until then, do not rely on `run_batch`.
- The QS consumer must always include `basic`; document it in the setup runbook.

## Next Steps

- Decide whether to provision the QS batch DB or keep the current single-command/direct
  publish workflow.
- If a public sample book is wanted, re-run the pipeline with `E2E_KEEP=1`; otherwise the
  library stays empty for launch.
- Rotate the three admin passwords before public release (accounts were created during
  testing).

## References

- `docs/operations/export-pipeline.md` (QuickStatements section)
- `docs/operations/quickstatements-setup.md` (grant + batch-mode notes)
- `learnings/030-telugu-line-finetune-results.md` (fine-tuned model)
- `learnings/031-wikibase-export-pipeline.md`, `032-wikibase-bot-passwords.md`,
  `033-wikibase-oauth-quickstatements.md`
- `backend/app/services/wikibase_publish.py`, `backend/app/api/bulk.py`
- E2E runner: `/tmp/oki_full_e2e.py` (temporary; not committed)
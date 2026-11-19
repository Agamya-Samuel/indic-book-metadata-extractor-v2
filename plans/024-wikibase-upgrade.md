# 024 — Wikibase/MediaWiki upgrade plan

**Status:** proposed
**Author:** platform
**Created:** 2026-11-19

## Problem

The Wikibase stack runs **Wikibase Suite image 7** (`wikibase/wikibase:7`, MediaWiki **1.45.4**).
MediaWiki 1.45 is a legacy branch that reaches end-of-life on **31 December 2026**. It is already
behind the 1.45.5/1.45.6 security fixes, and `wbeditentity` in REL1_45 hardcodes `bot=false`, so
bot-flagged edits are not marked.

## Options

| Option | Version | Support | Notes |
| --- | --- | --- | --- |
| A. Stay on 7 | 1.45.4 | EOL 2026-12-31 | no work, but no security fixes after Dec |
| B. WBS 4.1 (LTS legacy) | 1.43.9 | 2027-12-31 | older, but long support |
| C. WBS 8.2 (stable) | 1.46.2 | 2027-07-31 | current; replaces Elasticsearch with OpenSearch |
| D. WBS 9 (next LTS) | 1.47 | 2029 | due end Nov 2026; **recommended** |

**Recommendation:** target **D (1.47 LTS)** when the image is published; use **C** only if a
sooner migration is required.

## Scope

* `wikibase` and `wikibase-jobrunner` images
* search backend: `wikibase/elasticsearch:1` → `wikibase/opensearch:1` (required by WBS 8+)
* `docker/wikibase/config/90-extensions.php` (extension names/IDs are stable, but verify)
* CirrusSearch statement index (`searchIndexProperties`) and a full reindex
* OAuth consumer used by QuickStatements (re-register or verify)
* `create-properties.sh` (property IDs are stable; no re-creation needed)
* QuickStatements (`wikibase/quickstatements:1`) and OpenRefine (`3.10`) compatibility

## Pre-requisites

1. Full backup: MySQL dump + `wikibase_data`, `elasticsearch_data`, `quickstatements_data`.
2. A staging copy of the stack (same compose, different project name/volumes).
3. Record current versions: `Special:Version`, property/item counts, `property-mapping.json`.

## Steps

1. **Staging PoC**
   * restore the latest backup into a staging compose project;
   * switch to the target image, run `php maintenance/run.php update.php --quick`;
   * recreate the search index and reindex;
   * verify `Special:Version`, `wbsearchentities`, `haswbstatement:P2=Q1`, and the export pipeline.
2. **Extensions**
   * confirm the target image bundles REL1_47-compatible CirrusSearch, WikibaseCirrusSearch,
     WikibaseManifest, OAuth, ULS, WikibaseQualityConstraints;
   * re-apply `$wgWBRepoSettings['searchIndexProperties']` and the statement types.
3. **OAuth**
   * re-register the QuickStatements consumer against the new instance (callback
     `https://<qs-host>/api.php`), update `oauth.ini` / `QS_OAUTH_CONSUMER_*`.
4. **Production cutover**
   * maintenance window, `docker compose down` (no `-v`), restore/upgrade, `update.php`,
     reindex, smoke tests.
5. **Verification**
   * `GET /w/api.php?action=query&meta=siteinfo` → 200
   * `Special:Version` shows 1.47.x
   * `haswbstatement:P2=Q1` returns the published books
   * `POST /api/wikibase/publish` (dry run) → 200
   * OpenRefine reconciliation + one test edit
   * QuickStatements login + one test batch (if used)

## Risks

| Risk | Mitigation |
| --- | --- |
| Elasticsearch → OpenSearch migration | staging PoC; keep the old data volume until verified |
| Extension incompatibility | pin the image, test each extension in staging |
| OAuth consumer invalidated | re-register and update env |
| Reindex time | small dataset (<100 entities); minutes |
| Downtime | schedule; the app can run read-only during the switch |

## Acceptance criteria

* `Special:Version` reports the target branch and no EOL warning.
* All 49-field exports still validate; `haswbstatement:P2=Q1` returns every published book.
* QuickStatements and OpenRefine can still authenticate and edit.
* No loss of properties, items, or `property-mapping.json`.
# 031 — Wikibase Export Pipeline: What Was Broken and How It Was Fixed

**Date:** 2026-11-19
**Study context:** The application had a documented "Wikibase/OpenRefine bulk operations" feature, but
nothing had ever been published. This study audited the existing code against a live stack and
implemented the end-to-end path.

## Summary

The pipeline was not partially broken — it had never run. The Wikibase had **0 properties and 0
items**, and the code had several defects that would have produced invalid edits even after the
catalogue was initialised. The full chain (app → OpenRefine CSV → OpenRefine → Wikibase) is now
implemented and verified on the live OKI host.

## Key findings

### The Wikibase was empty

`wikibase-init` had never succeeded:

```
[create-properties] ERROR: API not available after 5 minutes. Exiting.
```

The readiness probe used `MW_WG_SERVER/w/api.php` (`https://wikibase/...`) from inside the compose
network. TLS/DNS do not exist there, so the loop always timed out. Fixed by probing
`http://wikibase/w/api.php` (`MW_API_INTERNAL`).

### Login always failed, then every edit was denied

`create-properties.sh` fetched a login token and sent it with `curl -d`. The token ends in `+`,
which form-decoding turns into a space → `WrongToken` → anonymous session. Every subsequent
`wbeditentity` then failed with *"You do not have the permissions needed to carry out this action."*
Fixed by sending every token with `--data-urlencode` and failing loudly when `login.result != Success`.

### The exporter emitted invalid claims

`export_service._wikibase_item` emitted **string literals for `wikibase-item` properties** (e.g.
`P50 = "రచయిత"`), skipped every field without a Wikidata property (15 of 49), and hardcoded
`labels.en`. Labels/descriptions are now in the book language (`hi`/`te`), datatypes follow the
contract, unresolved entity values are reported under `unresolved` instead of being emitted, and
duplicate statements are collapsed.

### Reconciliation and publishing

OpenRefine needs a manifest and a reconciliation service for a custom Wikibase. No SPARQL endpoint
exists in the stack, so both are served by the backend:

* `GET /api/reconcile/manifest.json` — manifest v2 with the local `instance_of` property;
* `GET /api/reconcile/{lang}/api` — Reconciliation Service 1.0 over `wbsearchentities`;
* `POST /api/wikibase/publish` — idempotent create/update via `wbeditentity`.

### Idempotency

`books.wikibase_item_id` (migration `020`) records the item. Entity values are matched by label and
created once as stubs. Values > 400 chars are truncated and reported; labels > 250 chars are skipped.

## Recommendation

**Done.** The pipeline is implemented, documented in `docs/operations/export-pipeline.md`, and
verified with real Hindi/Telugu books (Q87, Q100; later Q112, Q115, Q121, Q129).

## Next steps

* Deploy the backend image that contains the reconciliation and publish endpoints.
* Re-run `alembic upgrade head` before the first deploy of the new ORM column.
* Re-verify after the 1.47 upgrade ([plans/024](../plans/024-wikibase-upgrade.md)).

## References

* `docker/wikibase/create-properties.sh`
* `backend/app/services/export_service.py`
* `backend/app/api/reconcile.py`
* `backend/app/services/wikibase_publish.py`
* `docs/operations/export-pipeline.md`
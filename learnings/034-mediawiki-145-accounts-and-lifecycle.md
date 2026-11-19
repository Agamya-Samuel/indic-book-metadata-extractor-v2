# 034 — MediaWiki 1.45 Account Creation and the 1.45/1.47 Lifecycle

**Date:** 2026-11-19
**Study context:** Creating the QuickStatements and OpenRefine accounts through the API failed in
several non-obvious ways. This study records the working call and the version-support position.

## Summary

MediaWiki 1.45's `action=createaccount` requires `createtoken`, `createreturnurl` and `retype`; the
old `token` parameter is rejected. The instance runs **1.45.4**, a legacy branch that is EOL on
**31 December 2026**; the next LTS (1.47) is due at the end of November 2026.

## Key findings

### createaccount parameters (1.45)

```
token=...            → Unrecognized parameter: "token"
createtoken=...      → createtoken parameter must be set
+ createreturnurl=...→ createreturnurl parameter must be set
+ retype=...         → authmanager-create-no-primary (password rejected)
```

Working call:

```bash
CT=$(curl -s "$API?action=query&meta=tokens&type=createaccount&format=json" | jq -r .query.tokens.createaccounttoken)
curl -s --data-urlencode action=createaccount \
     --data-urlencode username="$U" \
     --data-urlencode password="$P" \
     --data-urlencode retype="$P" \
     --data-urlencode createtoken="$CT" \
     --data-urlencode createreturnurl="https://<host>/wiki/Main_Page" \
     --data-urlencode reason="..." \
     --data-urlencode format=json "$API"
```

Every token-bearing request must use `--data-urlencode`; tokens end in `+`.

### Version support

| Branch | Latest | End of support |
| --- | --- | --- |
| 1.46 (stable) | 1.46.2 | 2027-07-31 |
| **1.45 (ours)** | 1.45.6 | **2026-12-31** |
| 1.43 (LTS) | 1.43.11 | 2027-12-31 |
| 1.47 (next LTS) | — | due Nov 2026 |

Wikibase images: `wikibase/wikibase:7` = MW 1.45.4; `:8` = MW 1.46.2; `:4.1` = MW 1.43.9.

### Upgrade implications

* WBS 8+ replaces Elasticsearch with **OpenSearch** (`wikibase/opensearch:1`).
* `wbeditentity` hardcodes `bot=false` in REL1_45 (see [032](032-wikibase-bot-passwords.md)).
* A major upgrade needs `update.php`, a full reindex, extension re-checks, and OAuth
  re-registration. Plan: [plans/024](../plans/024-wikibase-upgrade.md).

## Recommendation

**Track 1.47 LTS.** Do not attempt the upgrade as part of feature work; run it as a staged change
with a backup and a staging PoC. Until then, 1.45.4 works but needs the December security release
if the image publishes one.

## Next steps

* Watch for the 1.47 LTS image.
* Add a quarterly dependency check to the operations calendar.

## References

* [Version lifecycle](https://www.mediawiki.org/wiki/Version_lifecycle)
* [Manual:Bot passwords](https://www.mediawiki.org/wiki/Manual:Bot_passwords)
* `plans/024-wikibase-upgrade.md`
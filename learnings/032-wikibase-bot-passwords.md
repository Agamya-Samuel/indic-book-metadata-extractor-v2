# 032 — Wikibase Bot Passwords, Grants, and the bot Flag

**Date:** 2026-11-19
**Study context:** The automated publisher originally reused the admin password. Replacing it with a
proper bot password exposed how MediaWiki grants interact with Wikibase rights.

## Summary

A bot password **can** edit Wikibase items, but only when it carries `basic` + `editpage` +
`createeditmovepage`. The first attempt failed because `editpage` was missing. In REL1_45,
`wbeditentity` hardcodes `bot=false`, so entity edits are never marked as bot edits.

## Key findings

### Grants are not rights

Per [Wikibase/Permissions](https://www.mediawiki.org/wiki/Wikibase/Permissions):

| Right | Grant |
| --- | --- |
| `read` | `basic` |
| `edit` (entities) | `editpage` |
| `item-term` (labels/descriptions/aliases) | `editpage` |
| `createpage` (items) | `createeditmovepage` |
| `property-create` | `createeditmovepage` |

A bot password only carries a right if the user has it **and** the grant is selected. Selecting
`createeditmovepage` alone gives `createpage` but **not** `item-term`, so creating an item with a
label fails with `permissiondenied` / `badaccess-groups`.

`basic` is mandatory; without it every API call returns `readapidenied`.

### The bot flag is hardcoded in REL1_45

`ModifyEntity.php` sets `'bot' => false` unconditionally. Even with the account in the `bot` group,
the bot password carrying `highvolume` (the `bot` right), and `bot=1` in the request, the revision
is stored with `bot=false`. The code still sends `bot=1` so it starts working after an upgrade.

### Bot passwords vs OAuth

[wikibase-edit](https://github.com/maxlath/wikibase-edit) and the MediaWiki manual recommend an
**owner-only OAuth consumer** for interactive/single-user tools and bot passwords for unattended
scripts. Our split:

* backend publish → dedicated account + bot password;
* QuickStatements → normal OAuth consumer (see [033](033-wikibase-oauth-quickstatements.md));
* OpenRefine → dedicated `OpenRefineEditor` account (manual UI login).

## Recommendation

**Adopted.** `OpenBookMapBot@publish` with `basic`, `editpage`, `createeditmovepage`, `highvolume`.
Document the grants in `docs/operations/export-pipeline.md` §4.

## Next steps

* Re-check the bot flag after the 1.47 upgrade.
* Rotate the bot token if it is ever exposed.

## References

* [Wikibase/Permissions](https://www.mediawiki.org/wiki/Wikibase/Permissions)
* [Manual:Bot passwords](https://www.mediawiki.org/wiki/Manual:Bot_passwords)
* `backend/app/services/wikibase_publish.py`
# Export pipeline: application → OpenRefine → Wikibase

How reviewed book metadata leaves the application, gets cleaned in OpenRefine, and is
published to the project's Wikibase. Every stage below was executed against the live
OKI deployment on 2026-11-18.

```
Application ──► OpenRefine CSV ──► OpenRefine ──► Wikibase ──► Verification
                    │                  │              ▲
                    └── Wikibase JSON   └─ reconcile ──┘
                                       (this backend)
```

## 1. Prerequisites

| Requirement | Value / where |
| --- | --- |
| Wikibase catalogue | `docker/wikibase/properties.json` → 48 properties (34 Wikidata P-IDs + 14 `LOCAL-*`) and 4 seed items |
| Property mapping | `storage/property-mapping.json`, written by `wikibase-init` (52 entries on the live host) |
| Field contract | `backend/app/schemas/metadata_contract.json` (49 fields) |
| Bot account | `<wikibase>/wiki/Special:BotPasswords`, grants *Create, edit, and move pages* + *Edit existing pages* |
| Backend config | `WIKIBASE_API_URL`, `WIKIBASE_PUBLIC_URL`, `WIKIBASE_BOT_USERNAME`, `WIKIBASE_BOT_PASSWORD` |
| DNS | `obm-wikibase.oki-india.org` must resolve; OpenRefine runs in the browser and calls it directly |

Verify the catalogue before a run:

```bash
curl -s "https://obm-wikibase.oki-india.org/w/api.php?action=query&list=allpages&apnamespace=122&format=json"
curl -s "https://openbookmap.oki-india.org/api/reconcile/manifest.json"
```

A manifest with `version: 2.0` and a `reconciliation_endpoint` means OpenRefine can edit.

## 2. Application → OpenRefine

Use **Export metadata → OpenRefine CSV** (single book) or **Admin → bulk export** (many).
The file is UTF-8 without a BOM, has 53 columns (`book_id`, `book_title`, `book_language`,
`source_filename`, then all 49 contract fields), and leaves empty fields empty.

* Hindi and Telugu are written as-is; no transliteration or escaping.
* Spreadsheet formula escaping is deliberately **not** applied to this format (it is applied
  to CSV/XLSX), so a value beginning with `-` or `+` survives intact.
* `book_id` lets you map OpenRefine rows back to application books after editing.

Import into OpenRefine with **Create project → This Computer**, or:

```bash
TOKEN=$(curl -s https://obm-openrefine.oki-india.org/command/core/get-csrf-token | jq -r .token)
curl -s -X POST "https://obm-openrefine.oki-india.org/command/core/create-project-from-upload" \
  -H "X-CSRF-Token: $TOKEN" -F "project-file=@hindi_openrefine.csv"
```

## 3. Reconcile and clean in OpenRefine

1. **Add the Wikibase instance**: *Wikibase → Manage Wikibase instances → Add Wikibase instance*,
   manifest URL `https://openbookmap.oki-india.org/api/reconcile/manifest.json`.
2. **Log in**: *Wikibase → Log in to Wikibase…* with the dedicated editor account
   `OpenRefineEditor` (credentials in `.env.production`), not the admin account.
3. **Reconcile entity columns** (author, publisher, genre, subject, language, …):
   *Reconcile → Start reconciling → IndicBooks Wikibase reconciliation*. Values that already
   exist link to their QID; missing values can be created as new items.
4. **Edit the schema**: *Wikibase → Edit Wikibase schema*. Add one statement per column using
   the datatypes in `metadata_contract.json`:
   * `wikibase-item` → reconciled item column
   * `monolingualtext` → `title`, `subtitle`, `description_work`, … with the book language tag
     (`te` for Telugu, `hi` for Hindi)
   * `time` → `publication_date`, `inception` (year precision is accepted)
   * `quantity` → `pages`
   * `external-id` → `isbn` (ISBN-10 and ISBN-13 use different properties)
5. **Upload edits**: *Wikibase → Upload edits to Wikibase*. Use a clear edit summary and a
   dedicated tag (the manifest suggests `openrefine-<version>`).

Reconciliation can also be driven from the API:

```bash
curl -s "https://openbookmap.oki-india.org/api/reconcile/en/api?query=book"
# {"result":[{"id":"Q1","name":"book",...}]}
```

## 4. Automated publishing (no OpenRefine)

For scripted runs and regression checks, the backend can publish directly:

```bash
curl -s -X POST https://openbookmap.oki-india.org/api/wikibase/publish \
  -H "Content-Type: application/json" \
  -d '{"book_ids":["<uuid>"],"dry_run":true}'
```

* `book_ids` omitted → every book with status `complete`.
* `dry_run: true` validates the contract and reports warnings without writing.
* Publishing is idempotent: `books.wikibase_item_id` stores the item id, so later runs update
  that item instead of creating duplicates.
* Entity-valued fields are matched by label and created once as stubs.
* Values longer than 400 characters are truncated (Wikibase's string limit) and reported;
  entity names longer than 250 characters are skipped with a warning.

### Publish account

The backend logs in with a **dedicated, non-admin account using a bot password**:
`WIKIBASE_BOT_USERNAME` is `OpenBookMapBot@publish` and `WIKIBASE_BOT_PASSWORD` is the
bot token from *Special:BotPasswords*.

Create the bot password with these **grants** (MediaWiki grants, not user rights):

* `basic` — required; without it every API call fails with `readapidenied`
* `editpage` — carries `edit` and `item-term` (labels, descriptions, aliases)
* `createeditmovepage` — carries `createpage`

Without `editpage`, a bot password authenticates but `wbeditentity` fails with
`permissiondenied` / `badaccess-groups`, because the entity edit check needs `item-term`
for the label. The account must be a normal user, not a sysop.

### Bot etiquette

Writes follow MediaWiki's bot conventions:

* `maxlag=5`; when Wikibase replies `maxlag`, the request is retried after `Retry-After`.
* `summary="Published from Open Book Map"` on every edit.
* For interactive tools (OpenRefine, QuickStatements) OAuth is preferred; bot passwords
  are for unattended scripts.
* `OpenBookMapBot` is in the `bot` group and the publisher sends `bot=1`, but
  `wbeditentity` in Wikibase REL1_45 hardcodes `bot=false` (`ModifyEntity.php`), so entity
  edits still appear as normal user edits. Re-check after the 1.47 upgrade.

## 5. Verification

```bash
# Item created for the book
curl -s "https://obm-wikibase.oki-india.org/w/api.php?action=wbgetentities&ids=Q87&props=labels|claims&format=json"
```

Confirmed on the live host (2026-11-18):

| Book | Item | Label language | Claims | Notes |
| --- | --- | --- | --- | --- |
| अगस्त क्रान्ति का इतिहास (Hindi) | Q87 | `hi` | 25 | author, publisher, ISBN-free, pages 8 |
| భరత న్తంతరయ సంగరమం (Telugu) | Q100 | `te` | 26 | pages 248, ISBN-13 |

The OpenRefine projects imported from the Hindi and Telugu exports each showed 53 columns and the
original script in `title`, `author`, `publisher`, `pages` and `scribes`
(`अगस्त क्रान्ति का इतिहास` / `భరత న్తంతరయ సంగరమం`).

## 6. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `wikibase-init` times out, Wikibase has 0 properties | probe used the public origin from inside the compose network | `MW_API_INTERNAL=http://wikibase/w/api.php` (fixed in `docker/wikibase/create-properties.sh`) |
| `You do not have the permissions needed…` on every edit | login token contained `+` and was sent unencoded → `WrongToken` → anonymous session | use `--data-urlencode` for `lgtoken` (fixed) |
| `Label and description … can not have the same value` | `description_work` equals the title | identical descriptions are dropped (fixed) |
| `Must be no more than 400 characters long` | long prose in a string/monolingual field | values are truncated to 400 and reported |
| `not-recognized-language: hin` | ISO 639-2 code sent where a BCP-47 tag is required | `tel→te`, `hin→hi`, `eng→en` |
| Edits append instead of replace | this Wikibase uses `clear`, not `clearclaims` | `edit_item` sends `clear` |
| OpenRefine cannot reach Wikibase | DNS missing or `WIKIBASE_PUBLIC_URL` wrong | add the DNS record and set the public origin |

## 7. QuickStatements (optional)

QuickStatements is publicly routed at
`https://obm-quickstatements.oki-india.org`; its `config.json` and
`oauth.ini` are rendered from the environment at startup. It needs a Wikibase bot account and a
**normal, not owner-only** OAuth consumer.

The full, reproducible procedure — bot account, email confirmation, `oauthbot` group, consumer
registration, environment variables and verification — is in
[`quickstatements-setup.md`](quickstatements-setup.md).

QuickStatements stays optional: OpenRefine's Wikibase extension and
`POST /api/wikibase/publish` publish without it.

## 8. Deployment order

The publish endpoint records the item id in `books.wikibase_item_id` (migration `020`). The
column must exist **before** the new backend image starts, otherwise every query that selects a
book fails:

```bash
docker compose exec backend alembic upgrade head   # adds books.wikibase_item_id
# then rebuild/redeploy the backend image
```

## 9. Contract maintenance

* `backend/app/schemas/metadata.py` loads `metadata_contract.json` at import time and fails
  fast if the field set drifts from `FullMetadata`.
* `docker/wikibase/properties.json` is the bootstrap catalogue. Add a `LOCAL-*` entry there
  when a field needs a new property, then re-run `wikibase-init`; it is idempotent and matches
  existing entities by label.
* `tests/unit/test_export_service.py` and `tests/unit/test_wikibase_publish.py` cover the
  contract, datatypes, Unicode, and idempotency.
## See also

* [031 — What was broken and how it was fixed](../../learnings/031-wikibase-export-pipeline.md)
* [032 — Bot-password grants and the bot flag](../../learnings/032-wikibase-bot-passwords.md)
* [033 — QuickStatements OAuth](../../learnings/033-wikibase-oauth-quickstatements.md)
* [034 — MediaWiki 1.45 accounts and lifecycle](../../learnings/034-mediawiki-145-accounts-and-lifecycle.md)

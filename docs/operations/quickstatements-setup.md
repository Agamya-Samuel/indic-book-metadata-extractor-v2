# QuickStatements setup and re-creation

How QuickStatements is wired to the Wikibase, and every step needed to recreate it on a fresh
instance, after a domain change, or if the OAuth consumer is lost.

QuickStatements is **optional**: OpenRefine's Wikibase extension and
`POST /api/wikibase/publish` publish without it. It is a browser batch editor for bulk edits.

## What is already in the repository

| Piece | Where |
| --- | --- |
| QS service, env plumbing | `docker-compose.production.yml` (`quickstatements`) |
| `oauthbot` group + `mwoauthproposeconsumer` | `docker/wikibase/config/90-extensions.php` |
| Wikibase sitename, logo, canonical origin, statement index | same file |
| QS credentials | Dokploy environment and `.env.production` (gitignored) |
| Consumer + bot account | live in the Wikibase database — **not** in git |

A fresh Wikibase therefore needs steps 1–4 below re-run.

## 1. Create the bot account

MediaWiki 1.45 needs `createtoken`, `createreturnurl` and `retype` (not `token`):

```bash
API="https://<wikibase-host>/w/api.php"
BOT_USER="QuickStatementsBot"
BOT_PASS='<generate a 24+ char password>'

# 1. login as an admin
LT=$(curl -s -c /tmp/c -b /tmp/c "$API?action=query&meta=tokens&type=login&format=json" | jq -r .query.tokens.logintoken)
curl -s -c /tmp/c -b /tmp/c \
  --data-urlencode action=login --data-urlencode lgname=<admin> \
  --data-urlencode lgpassword='<admin-password>' --data-urlencode lgtoken="$LT" \
  --data-urlencode format=json "$API" | jq -c .login

# 2. create the account
CT=$(curl -s -c /tmp/c -b /tmp/c \
  "$API?action=query&meta=tokens&type=createaccount&format=json" | jq -r .query.tokens.createaccounttoken)
curl -s -c /tmp/c -b /tmp/c \
  --data-urlencode action=createaccount \
  --data-urlencode username="$BOT_USER" \
  --data-urlencode password="$BOT_PASS" \
  --data-urlencode retype="$BOT_PASS" \
  --data-urlencode createtoken="$CT" \
  --data-urlencode createreturnurl="https://<wikibase-host>/wiki/Main_Page" \
  --data-urlencode reason="QuickStatements publishing bot" \
  --data-urlencode format=json "$API" | jq .
```

Success looks like `{"createaccount":{"status":"PASS","username":"QuickStatementsBot"}}`.

Every token-bearing request must use `--data-urlencode`; sending the token with `-d` turns the
trailing `+` into a space and produces `WrongToken`.

## 2. Confirm the bot's email address

OAuth registration refuses accounts without a confirmed email
(*"You must confirm your email address"*). The bot has no mailbox, so mark it confirmed directly:

```sql
UPDATE user
   SET user_email = 'quickstatements-bot@<domain>',
       user_email_authenticated = '20261119090000',   -- binary(14), YYYYMMDDHHMMSS
       user_email_token = NULL
 WHERE user_name = 'QuickStatementsBot';
```

## 3. Grant the right to register a consumer

The bot needs `mwoauthproposeconsumer`. A dedicated group keeps this off ordinary users; the
group is already defined in `docker/wikibase/config/90-extensions.php`:

```php
$wgGroupPermissions['oauthbot']['mwoauthproposeconsumer'] = true;
```

Add the bot to it (note the `userrights` token type):

```bash
UT=$(curl -s -c /tmp/c -b /tmp/c \
  "$API?action=query&meta=tokens&type=userrights&format=json" | jq -r .query.tokens.userrightstoken)
curl -s -c /tmp/c -b /tmp/c \
  --data-urlencode action=userrights --data-urlencode user=QuickStatementsBot \
  --data-urlencode add=oauthbot --data-urlencode token="$UT" \
  --data-urlencode format=json "$API" | jq -c .
```

If the config file is bind-mounted, a container recreate may be needed before the group exists
(PHP caches the file per worker; `apache2ctl graceful` is not always enough).

## 4. Register the OAuth consumer

Sign in as `QuickStatementsBot` and open:

```
https://<wikibase-host>/wiki/Special:OAuthConsumerRegistration/propose/oauth1a
```

| Field | Value |
| --- | --- |
| Name | `QuickStatements` |
| Description | `QuickStatements batch editor for Open Book Map` |
| Callback URL | `https://<qs-host>/api.php` |
| Callback is prefix | **checked** |
| Owner-only | **unchecked** |
| Grant | **Basic** (`grant-basic`) + **Create, edit, and move pages** (`grant-createeditmovepage`) + **Edit pages** (`grant-editpage`) + **High volume** (`grant-highvolume`) |
| Agreement | checked |

**Do not use an owner-only consumer.** QuickStatements fetches an access token from a different
site, and the handshake fails with `mwoauthserver-consumer-owner-only`.

**`grant-basic` is mandatory.** A consumer with only `createeditmovepage` logs in fine but every
`wbeditentity` fails with *"You do not have the permissions needed to carry out this action."*
Adding the grant does not require re-registration:

```sql
UPDATE oauth_registered_consumer
   SET oarc_grants = '["useoauth","basic","createeditmovepage","editpage","highvolume"]'
 WHERE oarc_consumer_key = '<consumer-key>';
```

On success the page prints the consumer token/secret and an access token/secret. Copy the
**consumer** pair into the environment (step 5); the access token is obtained by the OAuth flow.

If the callback came out as `/wiki/Special:OAuth/verified` (the form default), fix it:

```sql
UPDATE oauth_registered_consumer
   SET oarc_callback_url = 'https://<qs-host>/api.php',
       oarc_callback_is_prefix = 1
 WHERE oarc_id = <id>;
```

## 5. Configure the environment

Set these in **Dokploy → Compose → Environment** and `.env.production`:

```
QUICKSTATEMENTS_PUBLIC_URL=https://<qs-host>
WIKIBASE_PUBLIC_URL=https://<wikibase-host>
QS_OAUTH_CONSUMER_KEY=<consumer token>
QS_OAUTH_CONSUMER_SECRET=<consumer secret>
WIKIBASE_QS_BOT_USERNAME=QuickStatementsBot
WIKIBASE_QS_BOT_PASSWORD=<the bot's password>
```

The QS image renders `/var/www/html/quickstatements/public_html/config.json` and
`/quickstatements/data/oauth.ini` from the environment at startup, so no config file or helper
script is needed. Redeploy the `quickstatements` service after changing any of these.

## 6. Verify

```bash
# 1. the tool is up
curl -I https://<qs-host>/

# 2. the consumer credentials reached the container
docker exec <qs-container> grep -o "^consumerKey = .\{0,8\}" /quickstatements/data/oauth.ini

# 3. log in through the browser (Log in → Wikibase login → Allow) and then:
curl -s -b <cookies> "https://<qs-host>/api.php?action=is_logged_in"
# {"status":"OK",...,"is_logged_in":true}
```

A logged-in response names `QuickStatementsBot` and lists its rights. Batches can then be pasted
from `POST /api/bulk/export-wikibase` or imported with the URL form
`https://<qs-host>/#/v1=<url-encoded batch>`.

### Batch vs single-command mode

`POST /api/bulk/export-wikibase` returns a QuickStatements v1 TSV. The UI/API parses it with
`api.php?action=import&format=v1` and executes it with `api.php?action=run_single_command`
(one command per call, `last_item` threaded between calls). The batch path
(`api.php?action=run_batch`) is also supported: the compose provisions
`wikibase__quickstatements_p` / `wikibase__quickstatements_auth` on first boot
(`docker/mysql/02-init-quickstatements.sql`), and the custom QS image
(`docker/quickstatements/Dockerfile`) adds the `mysqli` extension and repoints the
Toolforge DB wrapper at the local `mysql` service. Both modes work; the app's direct
`POST /api/wikibase/publish` remains the simplest scripted path.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `WrongToken` on login | token sent with `-d`; `+` decoded as space | use `--data-urlencode` for every token |
| `createtoken parameter must be set` | 1.45 renamed the parameter | use `createtoken`, plus `createreturnurl` and `retype` |
| `authmanager-create-no-primary` | password rejected / missing `retype` | resend with `retype` and a 12+ char password |
| `You must confirm your email address` | bot email not confirmed | step 2 |
| `You do not have permission to propose…` | missing `mwoauthproposeconsumer` | step 3 |
| `mwoauthserver-consumer-owner-only` | owner-only consumer | register a normal consumer (step 4) |
| `permissiondenied` on every QS edit | consumer missing `basic` | add `grant-basic` (step 4) |
| `run_batch` returns `Could not complete the request.` | QS image missing the local-DB fix, or `wikibase__quickstatements_*` not provisioned | rebuild the QS image (`docker/quickstatements/Dockerfile`) and check the schemas |
| `Could not complete the request.` from `oauth_redirect` | bad callback / owner-only / bad credentials | check `oauth.ini`, consumer callback, and QS logs |
| QS cannot reach Wikibase | wrong `WIKIBASE_PUBLIC_URL` | use the public HTTPS origin in the QS env; internal `http://wikibase` is also reachable |
| Config reverts after redeploy | Dokploy rewrites the compose env | update Dokploy, not just the file |
## See also

* [033 — QuickStatements OAuth on a self-hosted Wikibase](../../learnings/033-wikibase-oauth-quickstatements.md)
* [034 — MediaWiki 1.45 account creation](../../learnings/034-mediawiki-145-accounts-and-lifecycle.md)

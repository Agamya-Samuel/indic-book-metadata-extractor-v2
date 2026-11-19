# 033 — QuickStatements OAuth on a Self-Hosted Wikibase

**Date:** 2026-11-19
**Study context:** QuickStatements was deployed but unusable: no public URL and an OAuth consumer
pointing at `https://localhost/api.php`. This study wired it end to end.

## Summary

QuickStatements works against a self-hosted Wikibase with a **normal, not owner-only** OAuth
consumer, a prefix callback at `https://<qs-host>/api.php`, and a bot account that can register the
consumer. The remaining requirements are operational (DNS, env), not code.

## Key findings

### Owner-only consumers cannot be used by a separate tool

The first attempt registered an owner-only consumer. The QS handshake failed:

```
mwoauthserver-consumer-owner-only
```

An owner-only consumer cannot fetch an access token from another site. The consumer must be a
normal (not owner-only) consumer, registered by the bot account, with the callback and grant.

### The bot needs `mwoauthproposeconsumer`

Registering a consumer at `Special:OAuthConsumerRegistration` requires the
`mwoauthproposeconsumer` right. A dedicated `oauthbot` group carries it, and the bot is a member.
Without it the page shows *"You do not have permission to propose new OAuth consumers."*

### The bot needs a confirmed email

OAuth registration refuses accounts without a confirmed address. The bot has no mailbox, so
`user.user_email` and `user.user_email_authenticated` are set directly (binary(14),
`YYYYMMDDHHMMSS`).

### The callback must be a prefix

The form's default callback is `/wiki/Special:OAuth/verified`. QS calls
`https://<qs-host>/api.php`, so the consumer needs **callback is prefix** checked and the URL
`https://<qs-host>/api.php`. A mismatch produces `Could not complete the request.` on
`api.php?action=oauth_redirect`.

### QS is configured entirely from env

The image renders `config.json` and `oauth.ini` from `QUICKSTATEMENTS_PUBLIC_URL`,
`WIKIBASE_PUBLIC_URL`, `OAUTH_CONSUMER_KEY` and `OAUTH_CONSUMER_SECRET` at startup. No bind mount
or helper script is needed.

## Recommendation

**Adopted.** QuickStatements is routed, env-configured, and authenticated as `QuickStatementsBot`
(`is_logged_in: true`). It stays optional — OpenRefine's Wikibase extension and the backend publish
endpoint do not need it.

## Next steps

* After a domain change: update `QUICKSTATEMENTS_PUBLIC_URL`, re-register the consumer, update
  `QS_OAUTH_CONSUMER_*`, redeploy.
* Full procedure: `docs/operations/quickstatements-setup.md`.

## References

* `docs/operations/quickstatements-setup.md`
* `docker/wikibase/config/90-extensions.php` (`oauthbot` group)
* `docker-compose.production.yml` (`quickstatements`)
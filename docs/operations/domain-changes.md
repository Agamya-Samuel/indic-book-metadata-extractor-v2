# Changing the public hostnames

Every hostname in this project is **temporary**. Nothing in the application hardcodes one; the
values are injected at build or deploy time. To move to a new domain, change the environment and
recreate the affected services.

## Where each host is configured

| Host | Service:port | Configuration |
| --- | --- | --- |
| App (frontend + API) | `frontend:3000` via `proxy:80` | `NEXT_PUBLIC_SITE_URL`, `FRONTEND_URL`, `APP_BASE_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL` |
| OpenRefine | `openrefine:3333` | `NEXT_PUBLIC_OPENREFINE_URL` (build-time, baked into the client bundle) |
| Wikibase | `wikibase:80` | `WIKIBASE_HOST`, `WIKIBASE_SCHEME`, `WIKIBASE_PUBLIC_URL`, `MW_WG_SERVER` |
| QuickStatements | `quickstatements:80` | `QUICKSTATEMENTS_PUBLIC_URL` (the image renders `config.json` and `oauth.ini` from it at startup) |

The backend's reconciliation endpoints (`/api/reconcile/...`) stay on the **app** origin; they are
not a separate host.

## Procedure

1. **DNS** — create the records (Cloudflare proxy is fine; the two working hosts are A records).
2. **Dokploy** — set each domain on the right service and port, HTTPS + Let's Encrypt.
3. **Environment** — update the variables above in Dokploy → Compose → Environment and in
   `.env.production` (gitignored).
4. **Rebuild the frontend** — `NEXT_PUBLIC_*` values are inlined at build time, so the frontend
   image must be rebuilt for the new OpenRefine/Wikibase links to appear.
5. **Recreate Wikibase** — `$wgServer` is baked into `LocalSettings.php` at install time, but
   `docker/wikibase/config/90-extensions.php` overrides it from `MW_WG_SERVER` on every request,
   so a recreate (or a graceful Apache reload) is enough.
6. **QuickStatements** — after a host change, re-register the OAuth consumer on the Wikibase with
   callback `https://<qs-host>/api.php` and update `QS_OAUTH_CONSUMER_KEY` /
   `QS_OAUTH_CONSUMER_SECRET`. The container entrypoint writes `oauth.ini` from them.
7. **Verify** — `curl -I https://<host>/` for each, then the checks in
   [`export-pipeline.md`](export-pipeline.md) §5.

## What is deliberately not hardcoded

* The app's canonical URL comes from `NEXT_PUBLIC_SITE_URL`.
* Wikibase canonical URLs come from `MW_WG_SERVER` (set from `WIKIBASE_HOST`/`WIKIBASE_SCHEME`).
* QuickStatements' own links and OAuth endpoints are rendered from
   `QUICKSTATEMENTS_PUBLIC_URL` / `WIKIBASE_PUBLIC_URL`.
* The Main Page is seeded from `docker/wikibase/Main_Page.wikitext`, which contains no absolute
   URLs.
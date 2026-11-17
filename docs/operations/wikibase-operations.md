# Wikibase and QuickStatements Operations

> **Status: optional and not enabled by default in practice.** These services currently start with the
> compose stack, but nothing in the core pipeline depends on them. Stopping them loses no processing
> capability — only the ability to push reviewed metadata to a Wikibase instance.
>
> Compose-profile gating is **recommended but not implemented**. See
> [integrations](../architecture/integrations.md).

---

## 1. What the stack contains

| Service | Role | Required by |
| --- | --- | --- |
| `wikibase` | MediaWiki + Wikibase entity store | QuickStatements, manual browsing |
| `wikibase-jobrunner` | MediaWiki job queue worker | Wikibase entity writes |
| `wikibase-init` | One-shot property creation | First run only |
| `quickstatements` | Batch statement import UI | Publishing TSV |
| `mysql` (MariaDB 10.11) | Wikibase's own database | Wikibase |
| `elasticsearch` | Wikibase search backend | Wikibase search |
| `openrefine` | Bulk data cleaning GUI | Optional reconciliation workflow |

Idle cost is significant: roughly 2.5 GiB, with OpenRefine (~1.08 GiB) and Elasticsearch (~900 MiB)
dominating.

---

## 2. What the application actually integrates with

**Very little, by design.**

| Capability | Behaviour |
| --- | --- |
| QuickStatements export | `POST /api/bulk/export-wikibase` generates a TSV **locally** and never contacts Wikibase |
| Property mapping | Read from `property-mapping.json`, written by `wikibase-init` (see §5.1) |
| OpenRefine | A link-out only; `openrefine_service.py` is dead code |
| Health checks | `/health` does not check any Wikibase service |

So "Wikibase integration" today means: produce a file in the right format, and let a human paste it
into QuickStatements.

---

## 3. Starting and stopping

```bash
make wikibase-shell      # shell into the wikibase container
make wikibase-logs       # follow logs
make wikibase-init       # re-run property creation
make wikibase-update     # update the image
make install-gadgets     # install the in-wiki editing gadgets
```

To stop the optional stack without deleting data, stop the services — do **not** remove volumes.

```bash
docker compose stop wikibase wikibase-jobrunner quickstatements mysql elasticsearch openrefine flower
```

`wikibase-init` is a one-shot (`restart: "no"`) and re-creates properties on the next start if they are
missing. Because it is idempotent, restarting after a deliberate stop is safe.

---

## 4. Volumes

| Volume | Contents |
| --- | --- |
| `mysql_data` | Wikibase relational data |
| `elasticsearch_data` | Search index |
| `wikibase_config` | LocalSettings overrides, generated property mapping |
| `wikibase_data` | Uploaded media |
| `quickstatements_data` | QuickStatements state |
| `openrefine_data` | OpenRefine projects |

**Never `down -v`.** Volume names differ between environments (`mysql_data` in development vs
`mysql_data_v3` in production), so enumerate before deleting anything, and confirm per volume.

---

## 5. Known defects

Items 5.2 and 5.3 remain open; 5.1 records a defect that has been fixed.

### 5.1 Property mapping (fixed)

`create-properties.sh` is incremental: it loads any existing mapping, creates only the entities that
are missing, and merges the result. `wikibase-init` mounts the backend's storage volume at
`/app/storage` (`./backend/storage` in development, `storage_data` in production), so the script writes
the mapping to both `/config/property-mapping.json` and `/app/storage/property-mapping.json`.

`load_property_mapping()` therefore finds `PROPERTY_MAPPING_PATH`. It is called on every export
request, so no backend restart is needed after `make wikibase-init`.

### 5.2 `openrefine_service.py` is dead code

Nothing imports it. Verified: no importers in `backend/app`. The OpenRefine integration is a URL in the
frontend bundle, not a backend capability.

### 5.3 The UI cannot be feature-flagged

`NEXT_PUBLIC_OPENREFINE_URL` and `NEXT_PUBLIC_WIKIBASE_URL` are inlined at **build** time. Hiding the
links requires a rebuild; a runtime environment variable will not do it.

---

## 6. Publishing workflow (as it actually works)

```text
metadata reviewed and complete
        │
        ▼
POST /api/bulk/export-wikibase  →  QuickStatements TSV (generated locally)
        │
        ▼
open QuickStatements UI  →  paste TSV  →  run batch
        │
        ▼
Wikibase entities created/updated
```

Prerequisites: `wikibase` and `quickstatements` healthy, and the property IDs in the TSV valid for the
target instance.

---

## 7. Gating (recommended, not implemented)

The intended mechanism is Compose profiles:

```yaml
wikibase:
  profiles: [wikibase]
openrefine:
  profiles: [openrefine]
```

with `COMPOSE_PROFILES=` empty by default and `COMPOSE_PROFILES=wikibase,openrefine` when needed.

`COMPOSE_PROFILES` was verified end to end in
[`learnings/015`](../../learnings/015-service-inventory-and-gating.md): with the variable empty, only
core services start; with it set, the named profile's services join. What is missing is the `profiles:`
keys themselves in `docker-compose.production.yml`.

Expected saving: ~2.5 GiB per environment with no restructuring.

---

## 8. Security

- Give Wikibase and OpenRefine public hostnames only if they must be reachable. Both are
  administrative surfaces with their own auth, unrelated to this application's accounts.
- QuickStatements is `expose: 80` so Traefik can route it; do not bind it to a host port, which would
  also prevent a second environment from starting.
- Wikibase admin credentials (`WIKIBASE_ADMIN_PASS`) are separate from application users. Generate them
  fresh per environment.
- The Traefik API is unauthenticated by default and was observed exposing every router/service. Restrict
  it at the host firewall (`DOCKER-USER`, not `ufw`).

---

## 9. Extensions and gadgets

The local Wikibase image bundles the extensions the workflow needs. Verify the live list at
`/wiki/Special:Version`.

**Wikibase:** WikibaseRepository, WikibaseClient, WikibaseCirrusSearch, WikibaseManifest,
WikibaseLocalMedia, EntitySchema, WikibaseEdtf, WikibaseLexeme, WikibaseLexemeCirrusSearch,
WikibaseQualityConstraints, PropertySuggester.

**MediaWiki:** CirrusSearch, Elastica, Echo, OAuth (for QuickStatements), UniversalLanguageSelector,
Babel, CLDR, VisualEditor, Scribunto, ParserFunctions, Cite, CodeMirror, DiscussionTools, ConfirmEdit,
Nuke, SyntaxHighlight, AbuseFilter, AdvancedSearch, Gadgets.

**Gadgets** (`make install-gadgets`), eight curated from wikidata.org: Merge, labelLister,
KeyShortcuts, DuplicateReferences, compact items, NarrowUI, Descriptions, AuthorityControl. Enable
per user at `/wiki/Special:Preferences#mw-prefsection-gadgets`.

Extensions deliberately **not** installed are the ones that require Wikimedia-wide infrastructure
(CentralAuth and similar); they are not feasible self-hosted.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `wikibase` unhealthy | MySQL or Elasticsearch not ready | Check those logs; `start_period` is 120 s |
| Properties missing | `wikibase-init` never ran or failed | `make wikibase-init` |
| QuickStatements rejects the TSV | Property IDs do not exist | Verify property mapping on the instance |
| Export contains Wikidata P-IDs | Mapping file missing or unreadable | Run `make wikibase-init`, then restart the backend |
| OpenRefine link 404s | `NEXT_PUBLIC_OPENREFINE_URL` unset at build | Rebuild the frontend |
| Everything slow after starting the stack | ~2.5 GiB extra plus CPU | Stop the optional services |

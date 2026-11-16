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
| Property mapping | Read from a JSON file; **currently broken** (see §5) |
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

These are real and documented rather than worked around:

### 5.1 Property mapping never loads

- `docker/wikibase/create-properties.sh` writes `MAPPING_FILE="/config/property-mapping.json"` into the
  `wikibase_config` volume.
- The backend reads `PROPERTY_MAPPING_PATH`, default `/app/storage/property-mapping.json`, from
  `storage_data`.

Different volumes, so the file is never found and `_load_property_mapping()` always falls back to
hardcoded Wikidata P-IDs. Until the paths agree, local property IDs must match Wikidata's by
construction.

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

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `wikibase` unhealthy | MySQL or Elasticsearch not ready | Check those logs; `start_period` is 120 s |
| Properties missing | `wikibase-init` never ran or failed | `make wikibase-init` |
| QuickStatements rejects the TSV | Property IDs do not exist | Verify property mapping on the instance |
| Export contains Wikidata P-IDs | The broken mapping fallback | Expected — see §5.1 |
| OpenRefine link 404s | `NEXT_PUBLIC_OPENREFINE_URL` unset at build | Rebuild the frontend |
| Everything slow after starting the stack | ~2.5 GiB extra plus CPU | Stop the optional services |

# Plan: Wikibase Extensions, QuickStatements, Gadgets, and QID Workflow

## Context

The `dev` branch has a Wikibase instance (`wikibase/wikibase:7`, MW 1.45.4) alongside the Indic Book Metadata Extractor. It's a **minimal deployment** — `LocalSettings.Extensions.php` is an empty stub, no additional extensions installed, no QuickStatements, no jobrunner.

### Critical Bug Found

The current setup bind-mounts an empty stub at `/LocalSettings.Extensions.php`, **replacing** the image's own file containing `glob('/var/www/html/LocalSettings.d/*.php')`. This breaks loading of all bundled extension configs (Wikibase, CirrusSearch, EntitySchema, OAuth, Echo, etc.). Task 3 fixes this.

### Entrypoint Behavior

1. **First boot**: `install.php` → generates `/config/LocalSettings.php` (with `require_once` for MediaWiki.php and Extensions.php) → runs `default-extra-install.sh` (ES indexing, OAuth auto-gen) → starts Apache
2. **Every boot**: Runs `php maintenance/update.php --quick` (auto-migrates DB)
3. **OAuth auto-gen**: `default-extra-install.sh` creates OAuth consumer if `QUICKSTATEMENTS_PUBLIC_URL` set, writes `oauth.ini` to shared volume

### Branch Verification

All REL1_45 branches confirmed to exist (HTTP 200): PropertySuggester, WikibaseLexeme, WikibaseLexemeCirrusSearch, WikibaseQualityConstraints, AdvancedSearch.

---

## Scope

| Decision | Choice |
|----------|--------|
| WDQS (SPARQL) | **Skip** |
| Extension install | **Custom Dockerfile** |
| QID creation | **QuickStatements only** |
| WikibaseEdtf | **Enable** |
| AbuseFilter | **Include** |
| PropertySuggester init | **Manual** documented step |
| OAuth | **Auto-gen** via shared volume |
| Existing data | **Fresh start** |
| LocalSettings pattern | **Switch** to `LocalSettings.d/90-extensions.php` |
| Gadgets | **8 curated** from wikidata.org |
| Docs | **Repo `docs/`** |
| Property auto-creation | **Init container** (one-shot, runs after wikibase healthy) |
| Property ID mapping | **Dynamic JSON** — copy to backend after creation |
| Gadget source files | **Fetch at Docker build time** |

---

## Tasks

### Task 1: Create Custom Wikibase Dockerfile

**Create:** `docker/wikibase/Dockerfile`

```dockerfile
FROM wikibase/wikibase:7

# Install extensions (REL1_45 = MW 1.45.x)
RUN cd /var/www/html/extensions && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/PropertySuggester && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseLexeme && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseLexemeCirrusSearch && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikibaseQualityConstraints && \
    git clone -b REL1_45 --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/AdvancedSearch

# Copy property creation script and definitions
COPY create-properties.sh /create-properties.sh
COPY properties.json /properties.json
RUN chmod +x /create-properties.sh

# Fetch gadget source files from wikidata.org at build time
COPY fetch-gadgets.sh /fetch-gadgets.sh
RUN chmod +x /fetch-gadgets.sh && /fetch-gadgets.sh

# Copy gadget installer
COPY install-gadgets.sh /install-gadgets.sh
RUN chmod +x /install-gadgets.sh
```

---

### Task 2: Create Extension Config File

**Create:** `docker/wikibase/config/90-extensions.php`

```php
<?php
wfLoadExtension('PropertySuggester');
wfLoadExtension('WikibaseLexeme');
wfLoadExtension('WikibaseLexemeCirrusSearch');
wfLoadExtension('WikibaseQualityConstraints');
wfLoadExtension('AdvancedSearch');
wfLoadExtension('AbuseFilter');
wfLoadExtension('WikibaseEdtf');
wfLoadExtension('Gadgets');

$wgPropertySuggesterMinProbability = 0.05;
$wgLexemeEnableCirrusSearch = true;
$wgWBQualityConstraints['constraintCheckOnEntitySave'] = true;
$wgWBQualityConstraints['constraintCheckOnSpecialPage'] = true;
```

---

### Task 3: Fix LocalSettings Mount Pattern

**Delete:** `docker/wikibase/config/LocalSettings.Extensions.php` (empty stub)
**Delete:** `docker/wikibase/config/LocalSettings.MediaWiki.php` (empty stub)

**Modify** wikibase + jobrunner volumes:
- **Remove**: `/LocalSettings.Extensions.php` and `/LocalSettings.MediaWiki.php` bind mounts
- **Add**: `./docker/wikibase/config/90-extensions.php:/var/www/html/LocalSettings.d/90-extensions.php`

---

### Task 4: Update Wikibase Service

In `docker-compose.yml`:
1. `image: wikibase/wikibase:7` → `build: ./docker/wikibase`
2. Add `QUICKSTATEMENTS_PUBLIC_URL: "http://localhost:9191"`
3. Add `quickstatements_data:/quickstatements/data` volume
4. Remove `MW_SECRET_KEY`, `MW_UPGRADE_KEY`, `WIKIBASE_PUBLIC_SCHEME` env vars

---

### Task 5: Add QuickStatements Service

```yaml
quickstatements:
  image: wikibase/quickstatements:1
  restart: unless-stopped
  ports:
    - "9191:80"
  environment:
    QUICKSTATEMENTS_PUBLIC_URL: "http://localhost:9191"
    WIKIBASE_PUBLIC_URL: "http://localhost:8181"
  volumes:
    - quickstatements_data:/quickstatements/data
  depends_on:
    wikibase:
      condition: service_healthy
```

---

### Task 6: Add Jobrunner Service

```yaml
wikibase-jobrunner:
  build:
    context: ./docker/wikibase
    dockerfile: Dockerfile
  command: /jobrunner-entrypoint.sh
  restart: unless-stopped
  depends_on:
    wikibase:
      condition: service_healthy
  volumes:
    - wikibase_config:/config
    - ./docker/wikibase/config/90-extensions.php:/var/www/html/LocalSettings.d/90-extensions.php
    - wikibase_data:/var/www/html/images
    - quickstatements_data:/quickstatements/data
```

---

### Task 7: Add Wikibase Init Container (Property + QID Creation)

**Create:** `docker/wikibase/properties.json`
JSON with 22 properties + P31 + Q571 (book). Each entry: `wikidata_id`, `label`, `datatype`, `description`.

**Create:** `docker/wikibase/create-properties.sh`
Shell script that:
1. Polls Wikibase API until healthy
2. Logs in as admin via API
3. Creates each property from `properties.json` via `action=wbeditentity&new=property`
4. Creates Q571 (book) item
5. Writes mapping (Wikidata P-ID → local P-ID) to `/config/property-mapping.json`

**Add to `docker-compose.yml`:**
```yaml
wikibase-init:
  build:
    context: ./docker/wikibase
    dockerfile: Dockerfile
  command: /create-properties.sh
  restart: "no"
  environment:
    MW_ADMIN_NAME: admin
    MW_ADMIN_PASS: ${WIKIBASE_ADMIN_PASS}
  volumes:
    - wikibase_config:/config
  depends_on:
    wikibase:
      condition: service_healthy
```

**Post-deploy manual step:** After first successful init, copy mapping to backend:
```bash
docker compose cp wikibase-init:/config/property-mapping.json ./backend/property-mapping.json
docker compose restart backend
```

---

### Task 8: Create Gadget Fetch + Install System

**Create:** `docker/wikibase/fetch-gadgets.sh`
Script that runs at Docker build time. Fetches JS/CSS from wikidata.org API for 8 gadgets:
- Merge, labelLister, KeyShortcuts, DuplicateReferences, compact_items, NarrowUI, Descriptions, AuthorityControl
- Saves to `/gadgets/` directory in the image
- Uses `curl` to fetch from `https://www.wikidata.org/w/api.php?action=query&titles=MediaWiki:Gadget-*.js&prop=revisions&rvprop=content&format=json`

**Create:** `docker/wikibase/install-gadgets.sh`
Runtime script that:
1. Logs into Wikibase API as admin
2. Creates `MediaWiki:Gadgets-definition` page with definitions for all 8 gadgets
3. Creates each `MediaWiki:Gadget-*.js` and `MediaWiki:Gadget-*.css` page from `/gadgets/` files
4. Idempotent

---

### Task 9: Update Backend QuickStatements Export

**Modify:** `backend/app/api/bulk.py` — `bulk_export_wikibase` endpoint

- Read `property-mapping.json` to map Wikidata P-IDs to local P-IDs
- Fall back to hardcoded Wikidata P-IDs if mapping not found (backward compatible)
- Use local Q571 for "instance of = book"

**Modify:** `backend/app/core/config.py` — add `PROPERTY_MAPPING_PATH` setting

---

### Task 10: Add Volumes + Update `.env.example`

Add to `volumes:` section: `quickstatements_data:`
Remove dead vars (`MW_SECRET_KEY`, `MW_UPGRADE_KEY`). Add QS documentation comments.

---

### Task 11: Mirror to `docker-compose.dokploy.yml`

Same changes as Tasks 4-7, 10 with:
- `expose` instead of `ports`
- Image names: `app-jb5tjz-wikibase`, etc.
- Fresh volumes with `_v2` suffix

---

### Task 12: Write QID Workflow Documentation

**Create:** `docs/wikidata-workflow.md`

1. Overview (Wikibase, QID/PID)
2. Prerequisites (services running, properties auto-created on first boot)
3. Creating Properties (auto-created + manual via Special:NewProperty)
4. Creating Items (Q-IDs) manually
5. Batch creation via QuickStatements (TSV syntax)
6. App's Wikibase Export (Bulk Operations → QS → Wikibase)
7. End-to-end pipeline (Book → OCR → LLM → Review → Export → OpenRefine → QS → Wikibase)
8. Property mapping system
9. Post-upload tasks (PropertySuggester data, constraint checking, gadgets)
10. Troubleshooting

---

### Task 13: Create Wikibase Extension/Tooling Reference

**Create:** `docs/wikibase-reference.md`
Installed extensions table, missing extensions + reasons, installed gadgets, future additions.

---

### Task 14: Update `docs/bulk-operations.md`

Add: QS upload workflow, OAuth troubleshooting, links to new docs.

---

### Task 15: Update Makefile

Add targets: `wikibase-shell`, `wikibase-logs`, `wikibase-update`, `install-gadgets`, `wikibase-init`

---

## Files Summary

| File | Action | Task |
|------|--------|------|
| `docker/wikibase/Dockerfile` | **CREATE** | 1 |
| `docker/wikibase/config/90-extensions.php` | **CREATE** | 2 |
| `docker/wikibase/create-properties.sh` | **CREATE** | 7 |
| `docker/wikibase/properties.json` | **CREATE** | 7 |
| `docker/wikibase/fetch-gadgets.sh` | **CREATE** | 8 |
| `docker/wikibase/install-gadgets.sh` | **CREATE** | 8 |
| `docker/wikibase/config/LocalSettings.Extensions.php` | **DELETE** | 3 |
| `docker/wikibase/config/LocalSettings.MediaWiki.php` | **DELETE** | 3 |
| `docker-compose.yml` | **MODIFY** | 3-7, 10 |
| `docker-compose.dokploy.yml` | **MODIFY** | 11 |
| `.env.example` | **MODIFY** | 10 |
| `backend/app/api/bulk.py` | **MODIFY** | 9 |
| `backend/app/core/config.py` | **MODIFY** | 9 |
| `Makefile` | **MODIFY** | 15 |
| `docs/wikidata-workflow.md` | **CREATE** | 12 |
| `docs/wikibase-reference.md` | **CREATE** | 13 |
| `docs/bulk-operations.md` | **MODIFY** | 14 |

---

## Validation

1. `docker compose build wikibase` — custom Dockerfile builds (includes gadget fetch)
2. `docker compose up -d mysql elasticsearch wikibase` — starts, update.php runs
3. `docker compose up -d wikibase-init` — creates properties + Q571, writes mapping
4. `http://localhost:8181/wiki/Special:Version` — all 8 extensions + Gadgets listed
5. `http://localhost:8181/wiki/Special:Properties` — properties exist
6. `docker compose up -d quickstatements` — QS loads at :9191, OAuth works
7. Upload sample QS TSV → items created with correct properties
8. `docker compose up -d wikibase-jobrunner` — processes background jobs
9. Copy mapping to backend, restart backend → QS export uses local P-IDs
10. Run `install-gadgets.sh` → gadgets in Special:Preferences

**Post-deploy manual steps:**
```bash
# 1. Load PropertySuggester data (one-time)
docker compose exec wikibase php extensions/PropertySuggester/maintenance/updateSuggesterData.php

# 2. Copy property mapping to backend (one-time)
docker compose cp wikibase-init:/config/property-mapping.json ./backend/property-mapping.json
docker compose restart backend

# 3. Install gadgets (one-time)
docker compose exec wikibase bash /install-gadgets.sh
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| REL1_45 branch missing | All 5 verified |
| OAuth auto-gen fails | Manual OAuth registration docs |
| Property init timing | Init container polls API until healthy |
| Gadget fetch at build time fails (network) | Dockerfile build fails visibly; retry build |
| Gadget JS incompatible with MW 1.45 | Test on first install; remove broken gadgets |
| Property mapping not copied | Backend falls back to hardcoded Wikidata P-IDs |

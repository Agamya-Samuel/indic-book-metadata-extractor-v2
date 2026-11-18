# Wikidata Workflow — QID Creation and Linked Data Pipeline

> **Superseded (2026-11-18).** This describes the original manual workflow. The supported
> procedure is [`export-pipeline.md`](export-pipeline.md); operational details are in
> [`wikibase-operations.md`](wikibase-operations.md). Prefer OpenRefine's Wikibase extension or
> `POST /api/wikibase/publish` over creating items by hand and pasting QuickStatements batches.
> Ports below are local-development values; production uses the public hostnames.

## Overview

This document describes the complete workflow for creating Wikibase items (QIDs) and properties (PIDs) from the Indic Book Metadata Extractor, and the end-to-end pipeline from scanned book PDF to structured linked data.

### Key Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **QID** | Wikibase item identifier | Q571 = book |
| **PID** | Wikibase property identifier | P50 = author |
| **Statement** | A property-value pair on an item | Q12345 → P50 → "విశ్వనాథ సత్యనారాయణ" |
| **QuickStatements** | Batch editing tool for Wikibase | Uploads TSV to create/edit items |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Indic Book Metadata Extractor                              │
│                                                             │
│  Pipeline (per book):                                       │
│    Upload → Pages → Preprocess → OCR → LLM → Review → Lib  │
│                                                             │
│  Wikidata workflow (periodic):                              │
│    Library → Export CSV → OpenRefine → Clean → Import       │
│    Library → Export QS TSV → QuickStatements → Wikibase     │
└──────────────────────┬──────────────────────────────────────┘
                       │
    ┌──────────────────▼──────────────────┐
    │         Wikibase (:8181)            │
    │  Items (Q-IDs), Properties (P-IDs)  │
    │  Statements, Labels, Descriptions   │
    └──────────────────┬──────────────────┘
                       │
    ┌──────────────────▼──────────────────┐
    │    QuickStatements (:9191)          │
    │  Batch item creation from TSV       │
    └─────────────────────────────────────┘
```

---

## Prerequisites

1. All Docker services running:
   ```bash
   docker compose up -d
   ```

2. Wikibase initialized and healthy:
   ```bash
   docker compose ps wikibase mysql elasticsearch
   ```

3. Properties auto-created by `wikibase-init` container (runs once on first boot):
   ```bash
   docker compose logs wikibase-init
   ```

4. QuickStatements accessible at http://localhost:9191

---

## Step 1: Property Auto-Creation (First Boot)

On first boot, the `wikibase-init` container automatically:

1. Waits for Wikibase API to become healthy
2. Logs in as admin
3. Creates the 34 properties in `docker/wikibase/properties.json` that have a Wikidata equivalent:

| Wikidata ID | Label | Datatype | Local ID (example) |
|-------------|-------|----------|---------------------|
| P31 | instance of | wikibase-item | P1 |
| P50 | author | wikibase-item | P2 |
| P98 | editor | wikibase-item | P3 |
| P110 | illustrator | wikibase-item | P4 |
| P123 | publisher | wikibase-item | P5 |
| P136 | genre | wikibase-item | P6 |
| P144 | based on | wikibase-item | P7 |
| P166 | award received | wikibase-item | P8 |
| P179 | part of the series | wikibase-item | P9 |
| P212 | ISBN-13 | external-id | P10 |
| P291 | place of publication | wikibase-item | P11 |
| P361 | part of | wikibase-item | P12 |
| P393 | edition number | string | P13 |
| P407 | language of work or name | wikibase-item | P14 |
| P478 | volume | string | P15 |
| P571 | inception | time | P16 |
| P577 | publication date | time | P17 |
| P629 | edition or translation of | wikibase-item | P18 |
| P655 | translator | wikibase-item | P19 |
| P736 | cover art by | wikibase-item | P20 |
| P750 | distributed by | wikibase-item | P21 |
| P825 | dedicated to | wikibase-item | P22 |
| P859 | sponsor | wikibase-item | P23 |
| P872 | printed by | wikibase-item | P24 |
| P921 | main subject | wikibase-item | P25 |
| P941 | inspired by | wikibase-item | P26 |
| P957 | ISBN-10 | external-id | P27 |
| P1104 | number of pages | quantity | P28 |
| P1433 | published in | wikibase-item | P29 |
| P1476 | title | monolingualtext | P30 |
| P1545 | series ordinal | string | P31 |
| P1680 | subtitle | monolingualtext | P32 |
| P2679 | author of foreword | wikibase-item | P33 |
| P7937 | form of creative work | wikibase-item | P34 |

4. Creates the items in `docker/wikibase/items.json`: Q571 (book), Q809 (Telugu), Q1568 (Hindi),
   Q1860 (English)
5. Writes `property-mapping.json` to `/config/` and, because the backend storage volume is mounted,
   to `/app/storage/`

**Verify:** Visit http://localhost:8181/wiki/Special:Properties — all properties should be listed.

The script is incremental: it skips entities already present in the mapping, so adding a property to
`properties.json` and re-running creates only the new one.

**Re-run if needed:**
```bash
docker compose run --rm wikibase-init
```

---

## Step 2: Verify the Mapping

`wikibase-init` writes the mapping to the backend storage volume directly, so no copy or restart is
needed. The backend reads it on every export request:

```bash
docker compose logs wikibase-init | tail -5
```

**Verify:** the log ends with `Done. N entity mappings available`, and the first export logs
"Loaded property mapping from /app/storage/property-mapping.json".

---

## Step 3: Install PropertySuggester Data (One-Time)

Load initial property suggestion data so Wikibase suggests relevant properties when editing:

```bash
docker compose exec wikibase php extensions/PropertySuggester/maintenance/updateSuggesterData.php
```

**Verify:** Edit any item on Wikibase — PropertySuggester should suggest relevant properties.

---

## Step 4: Install Gadgets (One-Time)

Install curated Wikidata gadgets for enhanced editing:

```bash
docker compose exec wikibase bash /install-gadgets.sh
```

This installs 8 gadgets:
- **Merge** — Merge duplicate items
- **labelLister** — Show/edit labels across languages
- **KeyShortcuts** — Keyboard shortcuts (L=label, D=desc, S=statements)
- **DuplicateReferences** — Copy references across statements
- **compact items** — More compact statement UI
- **NarrowUI** — Responsive design for narrow screens
- **Descriptions** — Hover to see item descriptions
- **AuthorityControl** — Links to authority control values

**Enable gadgets:** Visit http://localhost:8181/wiki/Special:Preferences#mw-prefsection-gadgets

---

## Step 5: Create Items (QIDs) Manually

### Via Wikibase UI

1. Go to http://localhost:8181/wiki/Special:NewItem
2. Set label (e.g., "విశ్వనాథ సత్యనారాయణ రచనలు")
3. Set description (e.g., "Telugu literary works collection")
4. Add statements using the property suggester
5. Save — the item gets a QID (e.g., Q10)

### Via QuickStatements (Batch)

1. Prepare a TSV file (see Step 6 for format)
2. Go to http://localhost:9191
3. Log in with Wikibase credentials
4. Paste TSV content or upload file
5. Run — items are created in bulk

---

## Step 6: Batch Create via QuickStatements

### TSV Format

```
CREATE
LAST	Len	"My Book Title"
LAST	P2	"Author Name"
LAST	P4	"Publisher Name"
LAST	P1	Q571
```

Where:
- `CREATE` — creates a new item
- `LAST` — refers to the most recently created item
- `Len` — sets the English label
- `P2` — local property ID for "author" (check your property mapping)
- `Q571` — "book" item

### Using the App's Export

1. Go to http://localhost:3000/admin/bulk
2. Filter by language/status if needed
3. Click **Download QuickStatements**
4. Open http://localhost:9191
5. Paste the TSV content
6. Click **Run**

The export automatically uses local property IDs from the mapping file.

---

## Step 7: End-to-End Pipeline

```
1. UPLOAD         Upload scanned PDF of Telugu/Hindi book
2. SELECT PAGES   Choose front/back pages for processing
3. PREPROCESS     Tune image settings (grayscale, contrast, deskew)
4. OCR REVIEW     Side-by-side view, correct OCR errors
5. LLM EXTRACT    Run LLM extraction (52 metadata fields)
6. METADATA REVIEW  Review and edit extracted fields
7. LIBRARY        Book saved with complete metadata

8. EXPORT CSV     Download metadata as CSV
9. OPENREFINE     Clean/standardize in OpenRefine (clustering, faceted browsing)
10. IMPORT CSV    Upload cleaned CSV back to app

11. EXPORT TSV    Generate QuickStatements file
12. QUICKSTATEMENTS  Upload TSV to create Wikibase items
13. WIKIBASE      Items created with properties, labels, descriptions
```

---

## Troubleshooting

### QuickStatements says "Property not found"
- The property mapping may be missing or stale. Run `make wikibase-init`, then restart the backend.
- Check that properties exist: http://localhost:8181/wiki/Special:Properties

### OAuth login fails on QuickStatements
- OAuth credentials may not have been auto-generated. Register manually:
  1. Go to http://localhost:8181/wiki/Special:OAuthConsumerRegistration/propose
  2. Set callback URL to `http://localhost:9191/api.php`
  3. Grant: `createeditmovepage`, `editpage`, `highvolume`
  4. Approve the consumer
  5. Set `OAUTH_CONSUMER_KEY` and `OAUTH_CONSUMER_SECRET` in QS environment

### PropertySuggester shows no suggestions
- Run the data loading command (Step 3)
- Suggestions improve as more items are created

### Wikibase is slow or unresponsive
- Check MySQL and Elasticsearch health: `docker compose ps mysql elasticsearch`
- Check logs: `docker compose logs wikibase`
- First boot takes ~60 seconds for initialization

### Gadget installation fails
- Check if Wikibase API is accessible: `curl http://localhost:8181/w/api.php?action=query&format=json`
- Run manually: `docker compose exec wikibase bash /install-gadgets.sh`

---

## References

- [QuickStatements Documentation](https://www.wikidata.org/wiki/Help:QuickStatements)
- [Wikibase API Documentation](https://www.mediawiki.org/wiki/Wikibase/API)
- [Wikidata Properties List](https://www.wikidata.org/wiki/Wikidata:List_of_properties)
- [OpenRefine Documentation](https://docs.openrefine.org/)
- [Wikibase Extension Documentation](https://www.mediawiki.org/wiki/Wikibase)

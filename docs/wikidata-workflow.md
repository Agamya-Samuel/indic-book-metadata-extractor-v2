# Wikidata Workflow — QID Creation and Linked Data Pipeline

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
3. Creates 22 properties matching Wikidata definitions:

| Wikidata ID | Label | Datatype | Local ID (example) |
|-------------|-------|----------|---------------------|
| P31 | instance of | wikibase-item | P1 |
| P50 | author | wikibase-item | P2 |
| P98 | editor | wikibase-item | P3 |
| P123 | publisher | wikibase-item | P4 |
| P136 | genre | wikibase-item | P5 |
| P291 | place of publication | wikibase-item | P6 |
| P407 | language | wikibase-item | P7 |
| P571 | inception | time | P8 |
| P577 | publication date | time | P9 |
| ... | ... | ... | ... |

4. Creates Q571 (book) item
5. Writes `property-mapping.json` to `/config/`

**Verify:** Visit http://localhost:8181/wiki/Special:Properties — all properties should be listed.

**Re-run if needed:**
```bash
docker compose run --rm wikibase-init
```

---

## Step 2: Copy Property Mapping to Backend

After the init container completes, copy the mapping file so the backend can use it for QuickStatements exports:

```bash
docker compose cp wikibase-init:/config/property-mapping.json ./backend/storage/property-mapping.json
docker compose restart backend
```

**Verify:** Check backend logs for "Loaded property mapping from /app/storage/property-mapping.json"

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

1. Go to http://localhost:3000/bulk-operations
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
- The property mapping may not be copied to the backend. Run Step 2 again.
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

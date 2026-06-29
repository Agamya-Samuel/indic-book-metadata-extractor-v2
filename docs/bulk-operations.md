# Bulk Operations — OpenRefine & Wikibase Integration

## Overview

After processing thousands of books through the extraction pipeline, librarians need to:

1. **Standardize metadata** across the collection — fix inconsistent publisher names, author spellings, place names with OCR artifacts
2. **Export to Wikibase** — push cleaned, structured metadata as linked data

**OpenRefine** is the industry-standard open-source tool for bulk data cleaning, widely used by libraries (Europeana, DPLA, Library of Congress). It provides clustering algorithms, faceted browsing, and a visual GUI suitable for non-technical users.

**Wikibase** is a structured data store (the software behind Wikidata) that holds bibliographic metadata as linked entities with properties.

This document explains how to use the Bulk Operations page to clean metadata in OpenRefine and export it to Wikibase.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Indic Book Metadata Extractor                                      │
│                                                                     │
│  Pipeline (per book):                                               │
│    Upload → Pages → Preprocess → OCR → LLM → Review → Library       │
│                                                                     │
│  Bulk operations (periodic):                                        │
│    Library ──export──→ CSV ──→ OpenRefine ──clean──→ CSV            │
│                              (:3333)                                │
│                                  │                                  │
│                                  ├──→ Wikibase (:8181)              │
│                                  │    (via QuickStatements)         │
│                                  │                                  │
│    Library ←──import── CSV ←─────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| OpenRefine | 3333 | Bulk data cleaning GUI |
| Wikibase | 8181 | Structured data store |
| MySQL | (internal) | Wikibase database |
| Elasticsearch | (internal) | Wikibase search index |

---

## Prerequisites

- Docker Compose running with all services (including Wikibase + OpenRefine)
- At least one book processed through the full pipeline (status: `complete`)

Start all services:

```bash
docker compose up -d
```

Verify OpenRefine and Wikibase are running:

```bash
docker compose ps openrefine wikibase
```

Access:
- **OpenRefine**: http://localhost:3333
- **Wikibase**: http://localhost:8181

---

## Workflow: Bulk Metadata Cleaning

### Step 1: Export Metadata from the System

1. Open the application at **http://localhost:3000**
2. Navigate to **Bulk Operations** (link in the top navbar)
3. In the **Export to CSV** card:
   - Optionally filter by **Language** (e.g., Telugu only)
   - Optionally filter by **Status** (e.g., only `complete` books)
   - Click **Download CSV**
4. A CSV file is downloaded with:
   - One row per book
   - First column: `book_id` (UUID — used for re-import matching)
   - Remaining columns: all 52 metadata fields + `title`, `language`, `filename`

**CSV columns** (in order):
```
book_id, title, language, filename, label, author, description_work, 
description_edition, translator, editor, compiler, inception, 
form_of_creative_work, genre, subject, original_language, 
edition_or_translation_of, based_on, inspired_by, volume, 
edition_number, publication_date, publisher, place_of_publication, 
printer, place_of_printing, language, cover_artist, cover_page_designer, 
typesetting_by, typing_by, book_designer, distributors, pages, 
dedication, dedication_verbatim, part_of_series, serial_number_in_series, 
part_of_the_set, illustrators, isbn, title, subtitle, awards, context, 
publisher_telugu, sponsor, first_published_in, forewords, abbreviations, 
authors_in_compilation, opinions_messages, scribes
```

---

### Step 2: Open in OpenRefine

1. Open **http://localhost:3333** in your browser
2. Click **Open** (top left) → **Import Project** or drag the CSV onto the page
3. Alternatively: click **Create Project** → **This Computer** → select the exported CSV
4. Configure import settings:
   - Ensure **Parse cell values into numbers, dates, ...** is **unchecked** (keep everything as text)
   - Set **Encoding** to **UTF-8** if not already selected
5. Click **Create Project**

You'll see a table with all your books as rows and metadata fields as columns.

---

### Step 3: Clean & Standardize Data in OpenRefine

#### 3a: Cluster Similar Values

The most powerful feature for fixing OCR artifacts and inconsistencies.

1. Click the dropdown arrow on a column header (e.g., `publisher`)
2. Select **Facet** → **Text facet**
3. A facet panel appears on the left showing all unique values and their counts
4. Click the **Cluster** button in the facet panel
5. OpenRefine shows groups of similar values:
   - "విశాలాంధ్ర" and "విశాలాంధ్ర పబ్లిషర్స్" — merge these
   - "ప్రచురణక్ర్త" and "ప్రచురణకర్త" — fix the typo
6. Review each cluster, check/uncheck as needed
7. Click **Merge Selected** to apply corrections

**Clustering methods** (try different ones for better results):
| Method | Best for |
|--------|----------|
| keyCollision (fingerprint) | Exact duplicates after normalization |
| keyCollision (metaphone3) | Phonetic similarities |
| nearestNeighbor (levenshtein) | Typos and OCR errors |
| nearestNeighbor (ppm) | Complex character-level similarities |

#### 3b: Find & Replace

For systematic corrections:

1. Click column dropdown → **Edit cells** → **Transform...**
2. Use GREL (Google Refine Expression Language):
   ```
   value.toLowercase()                    # normalize to lowercase
   value.replace("ప్రచురణక్ర్త", "ప్రచురణకర్త")  # fix specific typo
   value.trim()                           # remove leading/trailing spaces
   ```

#### 3c: Faceted Browsing

Explore data distributions:

1. Click column dropdown → **Facet** → **Text facet**
2. See all unique values and their counts in the left panel
3. Click any value to filter the table to only those rows
4. Use **Edit** in the facet to rename values in bulk

#### 3d: Useful Columns to Cluster

These fields benefit most from clustering (due to OCR artifacts or inconsistent naming):

| Column | Why |
|--------|-----|
| `publisher` | Publisher names vary in spelling, abbreviations |
| `place_of_publication` | City names in Telugu/Hindi script have variants |
| `author` | Author names may have honorifics, initials |
| `printer` | Similar to publisher — often confused |
| `translator` | Names may include "అనువాదం" or not |
| `genre` | Genre labels may use different terms |

---

### Step 4: Export Cleaned Data from OpenRefine

1. In OpenRefine, click **Export** (top right) → **Custom tabular exporter...**
2. Configure:
   - **Format**: Comma-separated values (CSV)
   - **Lines**: All rows
   - **Columns**: Select all (ensure `book_id` is included!)
3. Click **Export** → save the file

**Important**: The exported CSV **must** contain the `book_id` column — this is how the system matches rows back to books.

---

### Step 5: Import Cleaned Data Back

1. Return to the application at **http://localhost:3000/bulk-operations**
2. In the **Import from CSV** card:
   - Choose **Import Mode**:
     - **Merge** (default) — only update fields that have values in the CSV; existing fields not in the CSV are preserved
     - **Overwrite** — replace all metadata fields with the CSV values; fields missing from CSV become empty
   - Click **Upload CSV**
   - Select the cleaned CSV file from OpenRefine
3. A summary appears showing:
   - Total rows processed
   - Books updated
   - Fields changed
   - Books not found (if any `book_id`s don't match)
   - Errors (if any rows had invalid data)

The metadata in the library is now updated with the cleaned values.

---

## Workflow: Wikibase Export

### Step 1: Generate QuickStatements

1. Go to **http://localhost:3000/bulk-operations**
2. In the **Wikibase Export** card:
   - Optionally filter by **Language**
   - Click **Download QuickStatements**
3. A `.tsv` file is downloaded in QuickStatements format

The file contains one `CREATE` block per book, with:
- `Len` — English label (from the book's title)
- `P31` — instance of = book (Q571)
- `P407` — language (Telugu = Q809, Hindi = Q1568)
- All fields mapped to their Wikidata properties (P50 for author, P123 for publisher, etc.)

### Step 2: Upload to Wikibase

**Option A: Via QuickStatements Tool (recommended)**

1. Open https://quickstatements.toolforge.org/
2. Log in with your Wikibase credentials
3. Paste the TSV content or upload the file
4. Review the preview — verify items look correct
5. Click **Run** to create the items

**Option B: Directly via Wikibase API**

1. Open your Wikibase at http://localhost:8181
2. Use the API to batch-create items programmatically
3. See the [Wikibase API documentation](https://www.mediawiki.org/wiki/Wikibase/API)

### Wikibase Properties Used

The export maps fields to these Wikidata-compatible properties:

| Field | Property | Label |
|-------|----------|-------|
| author | P50 | author |
| translator | P655 | translator |
| editor | P98 | editor |
| genre | P136 | genre |
| subject | P921 | subject |
| publication_date | P577 | publication date |
| publisher | P123 | publisher |
| place_of_publication | P291 | place of publication |
| language | P407 | language |
| inception | P571 | inception |
| form_of_creative_work | P7937 | form of creative work |
| edition_or_translation_of | P629 | edition of |
| based_on | P144 | based on |
| inspired_by | P941 | inspired by |
| volume | P478 | volume |
| edition_number | P393 | edition number |
| printer | P872 | printer |
| place_of_printing | P2919 | place of printing |
| cover_artist | P736 | cover artist |
| pages | P1104 | pages |
| sponsor | P859 | sponsor |

Fields without Wikidata mappings (e.g., `title`, `isbn`, `dedication`, custom roles) are included as labels or skipped.

---

## API Reference

All endpoints are under `/api/bulk`.

### `GET /api/bulk/stats`

Returns library statistics.

**Response**:
```json
{
  "total_books": 1234,
  "books_with_metadata": 1100,
  "languages": {"tel": 800, "hin": 434},
  "statuses": {"complete": 1100, "ocr_complete": 134}
}
```

---

### `POST /api/bulk/export`

Export all book metadata as CSV.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `language` | string | Filter by language code (e.g., `tel`, `hin`) |
| `status` | string | Filter by book status (e.g., `complete`) |

**Response**: CSV file download (`text/csv`)

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/export?language=tel&status=complete" \
  -o metadata_export.csv
```

---

### `POST /api/bulk/import`

Import cleaned metadata from CSV.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `merge` | `merge` or `overwrite` |

**Body**: Multipart form data with a `file` field containing the CSV.

**Response**:
```json
{
  "total_rows": 500,
  "books_updated": 498,
  "books_not_found": 2,
  "fields_changed": 1523,
  "errors": ["Row 45: invalid book_id 'not-a-uuid'"]
}
```

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/import?mode=merge" \
  -F "file=@cleaned_metadata.csv"
```

---

### `POST /api/bulk/export-wikibase`

Generate QuickStatements TSV for Wikibase upload.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `language` | string | Filter by language code |

**Response**: TSV file download (`text/tab-separated-values`)

**Example**:
```bash
curl -X POST "http://localhost:8000/api/bulk/export-wikibase" \
  -o quickstatements.tsv
```

---

## Troubleshooting

### OpenRefine not accessible
- Check if the container is running: `docker compose ps openrefine`
- Check logs: `docker compose logs openrefine`
- Ensure port 3333 is not in use by another application

### Wikibase not accessible
- Check if MySQL and Elasticsearch are healthy: `docker compose ps mysql elasticsearch`
- Wikibase takes ~60 seconds to initialize on first start
- Check logs: `docker compose logs wikibase`

### Import shows "books not found"
- The CSV's `book_id` column must contain valid UUIDs that match existing books
- Re-export from the system to get the correct `book_id` values
- Don't modify the `book_id` column in OpenRefine

### QuickStatements upload fails
- Ensure the TSV file is properly formatted (tab-separated)
- Check that the Wikibase instance is accessible from QuickStatements
- Verify OAuth credentials are configured if using a remote Wikibase

### OpenRefine project is slow
- For very large datasets (5000+ books), OpenRefine may be slow
- Use the export filters (language, status) to reduce the dataset size
- Increase OpenRefine's memory: add `JAVA_OPTIONS=-Xmx4g` to the Docker environment

---

## References

- [OpenRefine Documentation](https://docs.openrefine.org/)
- [OpenRefine Wiki](https://github.com/OpenRefine/OpenRefine/wiki)
- [Wikibase Documentation](https://www.mediawiki.org/wiki/Wikibase)
- [QuickStatements](https://quickstatements.toolforge.org/)
- [Wikidata Properties](https://www.wikidata.org/wiki/Wikidata:List_of_properties)

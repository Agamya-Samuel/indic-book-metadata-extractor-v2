# User Guide — Indic Book Metadata Extractor

## Introduction

Indic Book Metadata Extractor is a web application that helps you extract structured bibliographic metadata from scanned PDFs of books in Telugu and Hindi. The application uses Tesseract OCR to read text from scanned pages, then uses a locally-hosted AI model (Airavata 7B) to extract 52 metadata fields.

**Browser requirements**: Any modern browser (Chrome, Firefox, Edge, Safari).

---

## Getting Started

1. Ensure the application is running (see the [README](../README.md) for setup instructions)
2. Open **http://localhost:3000** in your browser
3. You'll see the home page with two options: **Upload a Book** and **Browse Library**

---

## Step 1: Upload a PDF

1. Click **Upload a Book** on the home page
2. Drag and drop a PDF file onto the upload area, or click to browse
3. Select the **Language** (Telugu or Hindi)
4. Optionally enter a **Title** for the book
5. Click **Upload**

The system will analyze the PDF, count its pages, and redirect you to the Page Selection step.

**Supported formats**: PDF files only, up to 200 MB.

---

## Step 2: Page Selection

1. After upload, you'll see a grid of thumbnail previews for all pages in the PDF
2. Choose which pages to process:
   - **Front Pages**: Enter the number of pages from the beginning (e.g., first 5 pages)
   - **Back Pages**: Enter the number of pages from the end (e.g., last 3 pages)
   - **Select All**: Process all pages
3. Metadata is typically found on the title page, copyright page, and back cover, so selecting 5 front + 3 back pages is a good starting point
4. Click **Confirm Selection**

The system will render high-resolution images of the selected pages.

---

## Step 3: Image Preprocessing

1. For each selected page, you can tune image settings to improve OCR accuracy:
   - **Grayscale**: Convert to grayscale (recommended)
   - **Brightness**: Adjust brightness (-100 to +100)
   - **Contrast**: Adjust contrast (-100 to +100)
   - **Binarization**: Choose Otsu or Adaptive thresholding
   - **Deskew**: Auto-correct page rotation (recommended)
   - **Denoise**: Remove noise from scanned images
2. Click **Preview** to see the processed result before applying
3. Use **Apply to All** to apply the same settings to all pages
4. Click **Run OCR** to start the OCR process

OCR runs as a background task. You'll see a progress indicator while it processes each page.

---

## Step 4: OCR Review

1. After OCR completes, you'll see a side-by-side view:
   - **Left**: The page image with colored bounding boxes around detected text regions
   - **Right**: The extracted text in an editable text area
2. Click a bounding box on the image to highlight the corresponding text
3. Bounding box colors indicate confidence levels:
   - **Green**: High confidence (>80%)
   - **Yellow**: Medium confidence (60-80%)
   - **Red**: Low confidence (<60%)
4. Edit the text in the right panel to correct any OCR errors
5. Use **Previous** / **Next** to navigate between pages
6. Click **Save Corrections** to save your changes

> **Tip**: OCR accuracy on Indic scripts varies. Focus on correcting key fields like title, author, and publisher — these are what the LLM uses for metadata extraction.

---

## Step 5: LLM Configuration & Metadata Extraction

1. Navigate to the **LLM Config** step
2. Configure extraction settings:
   - **Model**: Choose from available Ollama models (Airavata recommended for Indic languages)
   - **Temperature**: Controls randomness (0.3 recommended for factual extraction)
   - **Max Tokens**: Maximum response length per batch
   - **System Prompt**: The instruction given to the model (editable)
   - **Extraction Prompt**: The prompt template used for each batch (editable)
3. View the list of 52 metadata fields organized into 8 batches
4. Click **Run Extraction** to start the LLM processing

> **Note**: On CPU, extraction takes 10-20 minutes per book. The job runs in the background — you can leave and return later.

---

## Step 6: Metadata Review

1. After LLM extraction completes, review all 52 metadata fields:
   - Fields are grouped by category (Core Identity, Contributors, Publication, etc.)
   - Pre-filled values come from the LLM extraction
   - Low-confidence or empty fields are highlighted
   - All fields are editable inline
2. The page image viewer at the top lets you reference the original scan
3. Edit any field values as needed
4. Click **Save Metadata** to finalize

---

## Step 7: Library & Search

The Library page shows all processed books in a card-based layout.

### Browsing
- Browse books with cover thumbnails, titles, authors, and language badges
- Use pagination to navigate through large collections

### Searching
- **Instant search**: Type in the search bar for immediate client-side filtering (Fuse.js)
- **Server search**: For larger result sets, the search hits the PostgreSQL backend with fuzzy matching (pg_trgm)

### Filtering
- Filter by **Language**, **Status**, **Genre**, or **Publisher**
- Combine filters for precise results

### Book Detail
- Click any book card to see its complete metadata record, all page images, OCR text, and LLM run history
- From the detail view, you can return to editing metadata if needed

---

## Job Queue Dashboard

The **Jobs** page shows all background jobs (OCR and LLM) with:
- **Status badges**: Queued (blue), Running (yellow), Completed (green), Failed (red)
- **Progress tracking**: Current progress percentage for active jobs
- **Retry**: Re-run failed jobs with one click
- **Auto-refresh**: The page polls for updates every 2 seconds

You can safely leave the page and return — all jobs persist in the database.

---

## Troubleshooting

### Ollama model not loading
- Check Docker logs: `make logs` and look for the `ollama` service
- Manually download: `make download-model`
- Ensure Docker has at least 8 GB RAM allocated (Docker Desktop > Settings > Resources)

### OCR produces poor results
- Try adjusting preprocessing settings (especially binarization and deskew)
- Higher DPI scans produce better results — 300 DPI minimum recommended
- Degraded or yellowed pages may need denoising enabled

### LLM extraction is slow
- CPU inference is inherently slower than GPU — 10-20 minutes per book is expected
- Monitor progress in the Jobs dashboard
- Consider using a smaller model (Kan-Llama) if speed is critical

### Docker volume issues
- Reset everything: `make clean && make up`
- On Windows, ensure WSL2 backend is enabled in Docker Desktop

### Page images not loading
- Check that the `backend/storage/` directory is mounted correctly in Docker
- Verify file permissions on the storage directory

### "Port already in use" errors
- Stop conflicting services: `make down`
- Check which ports are free: 3000, 5432, 5555, 6379, 8000, 11434

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Tab | Navigate between fields in metadata form |
| Enter | Confirm/save in modal dialogs |

---

## Tips for Best Results

1. **Start with clean scans** — Higher quality input produces better OCR and metadata
2. **Select relevant pages** — Title page, copyright page, and back cover contain most metadata
3. **Tune preprocessing** — Spend time on binarization and deskew settings before running OCR
4. **Correct OCR first** — The better the OCR text, the more accurate the LLM extraction
5. **Review all fields** — LLM extraction is not perfect; always review and correct the metadata
6. **Use consistent language** — Set the correct language hint at upload time for best OCR results

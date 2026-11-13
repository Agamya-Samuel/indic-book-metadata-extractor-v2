# User Guide — Indic Book Metadata Extractor

## Introduction

Indic Book Metadata Extractor is a web application that helps you extract structured bibliographic metadata from scanned PDFs of books in Telugu and Hindi. The application uses Tesseract OCR to read text from scanned pages, then uses a locally-hosted AI model (Qwen2.5 7B by default) to extract 52 metadata fields.

**Browser requirements**: Any modern browser (Chrome, Firefox, Edge, Safari).

---

## Getting Started

1. Ensure the application is running (see the [README](../README.md) for setup instructions)
2. Open **http://localhost:3000** in your browser
3. You'll see the home page with **Start an upload** and a link to log in

Uploading a book and everything else in the workflow requires a signed-in,
approved account. Every account is reviewed by an administrator before it can
be used.

---

## Accounts

### Creating an account

1. Click **Register** in the navbar (or **Create an account** on the login page)
2. Enter a display name, email address, and a password (minimum 10 characters)
3. Check your inbox for the verification email and click the link
4. The account is now active — log in with your email and password

The verification link expires after 24 hours. If it expires, use **Resend
verification** on the login page.

### Signing in and out

- **Log in** with your email address and password from the navbar or
  `http://localhost:3000/login`
- **Forgot password?** — request a reset link on the login page; the link
  expires after one hour and can be used once
- **Log out** from the user menu (display name) in the navbar

Sessions last 7 days. If you are signed out unexpectedly on many devices, an
administrator may have reset your password or deactivated your account.

### What each role can do

| | Visitor | User | Admin |
|---|---|---|---|
| Browse the full catalog (admin **Books** page) | — | — | ✅ |
| See page images, OCR text and job history of a book | — | Own books only | Any book |
| Upload books, run the pipeline, edit metadata | — | Own books | Any book |
| Personal dashboard with own books/jobs and queue position | — | ✅ | ✅ |
| Manage users (create, roles, deactivate, reset password, delete) | — | — | ✅ |
| Bulk operations (OpenRefine / Wikibase export) | — | — | ✅ |

### Your dashboard

**Dashboard** in the navbar shows everything you own:

- **Your books** — total, complete, and awaiting review counts; each book row
  has an **Actions** menu (open, jump to the current step, re-run OCR,
  re-run extraction, reset, delete)
- **Your jobs** — OCR and extraction jobs with status, progress and
  **queue position** ("Next up", "N ahead", "Running now"); you can cancel
  your own queued/running jobs

The **Admin** section (admins only) additionally shows every book and job
across all users, with an owner filter, plus the **Users** page for account
administration.

### Moving through a book's workflow

Every book page uses the same layout: a **stage rail** on the left (collapsed
to a stage picker on narrow screens) lists the eight steps and their state,
the step's content fills the rest of the screen, and a footer carries
**Back**, **Next** and links to any parallel next steps.

The rail marks the current step, completed steps, failed or stale steps, and
any background work still running under the step that owns it. Click any
stage to jump straight there — earlier stages stay reachable after a book is
finished so you can re-run OCR or re-extract metadata.

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

1. Settings are seeded from the selected page's saved configuration, so each
   page keeps its own tuning. Changing a control marks the page **Unsaved**.
2. Controls:
   - **Rotation**: ↺/↻ 90° steps, plus a fine-angle slider (±15°) applied after
     automatic deskew
   - **Grayscale**: Convert to grayscale (recommended)
   - **Brightness / Contrast**: -100 to +100
   - **Binarization**: None, Otsu, Adaptive, or Sauvola (with window/k controls)
   - **Deskew**: Auto-correct page rotation (recommended)
   - **Denoise**: Remove noise; strength is adjustable
   - **Advanced**: upscale to 300 DPI, border removal, auto-preprocess
3. **Preview** renders a temporary image *without saving*. Use the
   Current/Preview toggle to compare before committing.
4. **Apply to this page** writes the processed image and configuration.
   **Reset to defaults** restores the backend defaults.
5. **Apply to all pages** applies the current settings to every page.
6. **Run OCR** starts the OCR job. If OCR has already run, the button becomes
   **Re-run OCR** and asks for confirmation first — it lists exactly what will
   be discarded and what will be kept.

Applied pages show a ✓ badge in the thumbnail rail. OCR runs as a background
task with live progress.

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
4. Click **Edit text**, correct any OCR errors, then **Save corrections**. The
   save button stays disabled until the text actually changes, and clearing the
   text to empty is allowed. Edits are tracked per page: switching pages or
   navigating away with unsaved changes asks for confirmation.
5. The word boxes on the image are the **original OCR layout** — they are not
   updated by text edits.
6. Use **Previous** / **Next** in the toolbar, or the page filmstrip on the
   left, to navigate between pages. The **Pages** button collapses the
   filmstrip to give the editor more room.
7. Use **Save corrections** to save your changes.

> **Tip**: OCR accuracy on Indic scripts varies. Focus on correcting key fields like title, author, and publisher — these are what the LLM uses for metadata extraction.

---

## Step 5: LLM Configuration & Metadata Extraction

1. Navigate to the **LLM Config** step. The configuration form is always
   available — a running job shows as a progress card above the form instead
   of replacing it.
2. Configure extraction settings:
   - **Model**: Choose from available Ollama models (`phi4-mini` is the
     default)
   - **Temperature**: Controls randomness (0.3 recommended for factual extraction)
   - **Max Tokens**: Maximum response length per batch
   - **System Prompt**: The instruction given to the model (editable)
   - **Extraction Prompt**: The prompt template used for each batch (editable)
3. The batch count is derived from the backend's `batch_group` routing — one
   LLM call per field group — rather than a raw field count.
4. If Ollama is unreachable or has no models, a warning appears and the run
   button is disabled.
5. Click **Run Extraction** to start. If a previous run exists, the button
   reads **Run again** and warns that extracted metadata will be replaced.

> **Note**: On CPU, extraction takes 10-20 minutes per book. The job runs in the background — you can leave and return later. A completed run never traps you on a progress screen.

---

## Step 6: Metadata Review

1. After LLM extraction completes, review all 52 metadata fields:
   - Fields are grouped by category (Core Identity, Contributors, Publication, etc.)
   - Pre-filled values come from the LLM extraction
   - Low-confidence or empty fields are highlighted
   - All fields are editable inline
2. The **page image viewer** at the top lets you reference the original scan
3. Click any field to open the **Evidence** pane on the right. It shows where
   the value came from: the source page image, the OCR snippet it was read
   from, the extraction method, and the model's confidence
4. Edit any field values as needed. The sticky **save bar** at the bottom
   counts unsaved changes and offers **Save** and **Discard**
5. Click **Save** to save. **Saving no longer completes the book** — it stays
   in review so you can keep editing.
6. When you are finished, click **Mark review complete**. It confirms first and
   lists any empty or low-confidence fields. This is the only action that
   completes the workflow.
7. If you re-run OCR later, extracted metadata text is kept but marked out of
   date until extraction is re-run.

---

## Step 7: Finding & Searching Books

There is no shared public catalog. What you can see depends on your role:

- **Owners** see their books on the **Dashboard** (`/dashboard`).
- **Admins** see every book across all users on the **Books** page
  (`/admin/books`).

### Browsing (admin Books page)
- Browse books with cover thumbnails, titles, owner, language, and status
- Use pagination to navigate through large collections

### Searching
- **Instant search**: Type in the search bar for immediate client-side filtering (Fuse.js)
- **Server search**: For larger result sets, the search hits the PostgreSQL backend with fuzzy matching (pg_trgm)

### Filtering
- Filter by **Language**, **Status**, **Genre**, or **Publisher**
- Combine filters for precise results

### Book Detail
- Open a book to see its complete metadata record, all page images, OCR text,
  and LLM run history (`/books/{bookId}`)
- From the detail view, you can return to editing metadata if needed
- Regular owners can only open their own books; any other book URL returns 404.
  Admins can open any book.

---

## Job Queue Dashboard

Your own jobs are on the **Dashboard** page (queue position, cancel). The
admin **Jobs** page shows all background jobs (OCR, LLM, page extraction) with:
- **Status badges**: Queued (blue), Running (yellow), Completed (green), Failed (red)
- **Progress tracking**: 0–100% progress for active jobs
- **Cancel**: Cancel a queued/running job from its own row
- **Retry**: Re-run failed jobs with one click
- **Live updates**: Server-Sent Events push progress; if the stream drops, the
  UI falls back to polling and says so

You can safely leave the page and return — all jobs persist in the database.

---

## Notifications

The **bell** in the navbar shows how many notifications are unread. Open it for
the latest eight; **View all notifications** opens the full list.

- **Job results** — page rendering, OCR, preprocessing and metadata extraction
  each report when they finish, fail or are cancelled, with a link back to the
  relevant step of that book.
- **Account decisions** — when an administrator approves your account you get a
  notification pointing at your dashboard.
- **Admins** also get one notification per new registration awaiting approval,
  linking to the pending filter on the Users page.

In the full list, clicking a notification marks it read and follows its link;
**Mark all as read** clears the count. In-app notifications are always on.

### Email alerts

The **Email alerts** switch on the Notifications page mirrors these same events
to your account email address. Turn it off and nothing is emailed, but every
notification still appears in the app. Delivery needs a working mail server; if
one is not configured, the app keeps working and only the email is skipped.

---

## Bulk Operations (OpenRefine & Wikibase)

After processing many books, you can use **Bulk Operations** to clean metadata across the entire collection and export it to Wikibase.

1. Click **Bulk Operations** in the top navbar
2. **Export** — Download all metadata as a CSV file (filter by language/status if needed)
3. **Open in OpenRefine** — Import the CSV into OpenRefine at `http://localhost:3333` for bulk cleaning (clustering publisher names, fixing typos, standardizing values)
4. **Import** — Upload the cleaned CSV back to update all metadata records
5. **Wikibase Export** — Generate QuickStatements TSV for uploading to Wikibase

For detailed instructions, see the [Bulk Operations Guide](admin-bulk.md).

---

## Troubleshooting

### Verification email never arrives
- Registration works without SMTP, but then the link is only written to the
  **backend log**: `make logs-backend` and look for "SMTP disabled"
- For real delivery set `SMTP_ENABLED=true` plus `SMTP_HOST`, `SMTP_PORT`,
  `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` in `.env` and restart
- Verification links expire after 24 hours — request a new one from the login
  page (**Resend verification**)

### Cannot log in
- The account must be **verified** and **active** — a deactivated account
  cannot sign in (admins can reactivate it from **Admin → Users**)
- Password rules: minimum 10 characters (`PASSWORD_MIN_LENGTH`)
- Use **Forgot password?** for a self-service reset; the link expires after one hour

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

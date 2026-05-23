import { test, expect } from "@playwright/test";

const BOOK_ID = "test-book-001";

test.describe("Full Workflow - Mocked API", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/books/upload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: BOOK_ID,
          filename: "test_book.pdf",
          title: null,
          language: "tel",
          total_pages: 5,
          status: "uploaded",
          created_at: "2024-01-01T00:00:00",
        }),
      });
    });

    await page.route(`**/api/books/${BOOK_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: BOOK_ID,
          filename: "test_book.pdf",
          title: null,
          language: "tel",
          total_pages: 5,
          status: "pages_selected",
          created_at: "2024-01-01T00:00:00",
          updated_at: "2024-01-01T00:00:00",
        }),
      });
    });

    await page.route(`**/api/books/${BOOK_ID}/pages`, async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            selected_count: 2,
            status: "pages_selected",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "page-1",
              page_number: 1,
              image_path: "/storage/pages/1/p0001.png",
              preprocessing_config: null,
            },
            {
              id: "page-2",
              page_number: 2,
              image_path: "/storage/pages/1/p0002.png",
              preprocessing_config: null,
            },
          ]),
        });
      }
    });

    await page.route(
      `**/api/books/${BOOK_ID}/pages/*/thumbnail`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "image/png",
          body: Buffer.from(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "base64"
          ),
        });
      }
    );

    await page.route(`**/api/books/${BOOK_ID}/run-ocr`, async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "job-ocr-001",
          book_id: BOOK_ID,
          job_type: "ocr",
          status: "queued",
          progress: 0,
          created_at: "2024-01-01T00:00:00",
          started_at: null,
          completed_at: null,
          error_log: null,
        }),
      });
    });

    await page.route(`**/api/books/${BOOK_ID}/jobs`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "job-ocr-001",
            book_id: BOOK_ID,
            job_type: "ocr",
            status: "completed",
            progress: 1,
            created_at: "2024-01-01T00:00:00",
            started_at: "2024-01-01T00:00:01",
            completed_at: "2024-01-01T00:00:30",
            error_log: null,
          },
        ]),
      });
    });

    await page.route(`**/api/books/${BOOK_ID}/ocr-status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_pages: 2,
          ocr_complete_count: 2,
          ocr_pending_count: 0,
          avg_confidence: 85.5,
          pages: [
            { page_number: 1, page_id: "page-1", has_ocr: true, confidence: 90 },
            { page_number: 2, page_id: "page-2", has_ocr: true, confidence: 81 },
          ],
        }),
      });
    });

    await page.route(`**/api/pages/*/ocr`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          page_id: "page-1",
          raw_text: "తెలుగు పుస్తకం",
          bounding_boxes: [
            {
              text: "తెలుగు",
              confidence: 90,
              bbox: { x: 10, y: 10, w: 50, h: 20 },
              block_num: 1,
              line_num: 1,
              word_num: 1,
            },
            {
              text: "పుస్తకం",
              confidence: 80,
              bbox: { x: 70, y: 10, w: 60, h: 20 },
              block_num: 1,
              line_num: 1,
              word_num: 2,
            },
          ],
          confidence: 85,
          language_detected: "tel",
          corrected_text: null,
        }),
      });
    });

    await page.route(`**/api/pages/*/image`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "image/png",
        body: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
          "base64"
        ),
      });
    });

    await page.route(
      `**/api/pages/*/preprocessing`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            page_id: "page-1",
            processed_image_url: "/storage/processed/1/p0001_processed.png",
            config_applied: {
              grayscale: true,
              brightness: 0,
              contrast: 0,
              binarization: null,
              adaptive_block_size: 11,
              adaptive_c: 2,
              deskew: true,
              denoise: false,
              denoise_strength: 10,
            },
          }),
        });
      }
    );

    await page.route(`**/api/books/models`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { name: "airavata", size_gb: 4.2, parameter_count: "7B" },
        ]),
      });
    });

    await page.route(
      `**/api/books/${BOOK_ID}/run-extraction`,
      async (route) => {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            job_id: "job-llm-001",
            book_id: BOOK_ID,
            status: "queued",
            total_batches: 8,
          }),
        });
      }
    );

    await page.route(`**/api/books/${BOOK_ID}/metadata`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            fields: {
              title: "తెలుగు పుస్తకం",
              author: "రచయిత",
              publisher: "ప్రచురణకర్త",
            },
            updated_at: "2024-01-01T00:01:00",
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            fields: {
              title: "తెలుగు పుస్తకం",
              author: "రచయిత",
              publisher: "ప్రచురణకర్త",
            },
            updated_at: "2024-01-01T00:02:00",
          }),
        });
      }
    });

    await page.route(
      `**/api/books/${BOOK_ID}/metadata/fields`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              field_name: "title",
              display_name: "Title",
              wikidata_property: "P1476",
              batch_group: "core_identity",
            },
            {
              field_name: "author",
              display_name: "Author",
              wikidata_property: "P50",
              batch_group: "core_identity",
            },
            {
              field_name: "publisher",
              display_name: "Publisher",
              wikidata_property: "P123",
              batch_group: "publication",
            },
          ]),
        });
      }
    );

    await page.route(`**/api/books/${BOOK_ID}/llm-runs`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("**/api/library/books*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: BOOK_ID,
              title: "తెలుగు పుస్తకం",
              filename: "test_book.pdf",
              language: "tel",
              status: "complete",
              total_pages: 5,
              created_at: "2024-01-01T00:00:00",
              metadata_fields: {
                title: "తెలుగు పుస్తకం",
                author: "రచయిత",
              },
              thumbnail_url: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          total_pages: 1,
        }),
      });
    });

    await page.route("**/api/library/filters", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          languages: ["tel", "hin"],
          statuses: ["complete"],
          genres: [],
          publishers: [],
        }),
      });
    });

    await page.route(
      `**/api/library/books/${BOOK_ID}/detail`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book: {
              id: BOOK_ID,
              filename: "test_book.pdf",
              title: null,
              language: "tel",
              status: "complete",
              total_pages: 5,
              created_at: "2024-01-01T00:00:00",
              updated_at: "2024-01-01T00:02:00",
            },
            metadata: {
              title: "తెలుగు పుస్తకం",
              author: "రచయిత",
            },
            metadata_updated_at: "2024-01-01T00:02:00",
            pages: [],
            llm_runs: [],
            jobs: [],
          }),
        });
      }
    );
  });

  test("home page shows upload and library links", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Start Upload")).toBeVisible();
    await expect(page.getByText("Browse Library")).toBeVisible();
  });

  test("upload page renders correctly", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByText("Upload Book")).toBeVisible();
    await expect(page.getByText("Upload a file")).toBeVisible();
    await expect(page.getByText("PDF up to 200 MB")).toBeVisible();
  });

  test("library page shows books", async ({ page }) => {
    await page.goto("/library");
    await expect(page.getByText("Library")).toBeVisible();
  });

  test("select pages page renders thumbnails", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/select-pages`);
    await expect(page.getByText("Select Pages")).toBeVisible();
  });

  test("preprocessing page renders settings", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/preprocessing`);
    await expect(page.getByText("Preprocessing")).toBeVisible();
  });

  test("OCR review page renders", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/ocr-review`);
    await expect(page.getByText("OCR Review")).toBeVisible();
  });

  test("LLM config page renders", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/llm-config`);
    await expect(page.getByText("LLM Config")).toBeVisible();
  });

  test("metadata review page renders", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/metadata-review`);
    await expect(page.getByText("Metadata Review")).toBeVisible();
  });

  test("jobs page renders", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/jobs`);
    await expect(page.getByText("Jobs")).toBeVisible();
  });

  test("full navigation from home to upload", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Start Upload");
    await expect(page).toHaveURL(/\/upload/);
    await expect(page.getByText("Upload Book")).toBeVisible();
  });

  test("full navigation from home to library", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Browse Library");
    await expect(page).toHaveURL(/\/library/);
    await expect(page.getByText("Library")).toBeVisible();
  });
});

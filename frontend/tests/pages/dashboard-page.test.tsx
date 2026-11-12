import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import DashboardPage from "@/app/dashboard/page";
import type {
  BookSearchResult,
  BookListResponse,
  DashboardJobRow,
  DashboardJobsResponse,
  DashboardSummary,
} from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    getDashboardSummary: vi.fn(),
    getDashboardBooks: vi.fn(),
    getDashboardJobs: vi.fn(),
    cancelJob: vi.fn(),
    deleteBook: vi.fn(),
    resetBook: vi.fn(),
    rerunOcr: vi.fn(),
    rerunExtraction: vi.fn(),
    getThumbnailUrl: vi.fn(() => "/api/books/x/pages/1/thumbnail"),
  };
});

import {
  getDashboardSummary,
  getDashboardBooks,
  getDashboardJobs,
  cancelJob,
} from "@/lib/api";
const mockGetDashboardSummary = vi.mocked(getDashboardSummary);
const mockGetDashboardBooks = vi.mocked(getDashboardBooks);
const mockGetDashboardJobs = vi.mocked(getDashboardJobs);
const mockCancelJob = vi.mocked(cancelJob);

const mockSummary: DashboardSummary = {
  books: { total: 2, by_status: { complete: 1, awaiting_review: 1 } },
  jobs: {
    total: 5,
    queued: 2,
    running: 1,
    completed: 2,
    failed: 0,
    cancelled: 0,
  },
  queue: { ocr: 2, llm: 0 },
};

const mockBook: BookSearchResult = {
  id: "book-1",
  title: "My Telugu Book",
  filename: "my_book.pdf",
  language: "tel",
  status: "complete",
  total_pages: 42,
  created_at: "2024-01-01",
  metadata_fields: null,
  thumbnail_url: null,
  owner_display_name: "Ada Lovelace",
};

const mockBooksResponse: BookListResponse = {
  items: [mockBook],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

function jobRow(overrides: Partial<DashboardJobRow>): DashboardJobRow {
  return {
    id: "job-1",
    book_id: "book-1",
    book_title: "My Telugu Book",
    book_filename: "my_book.pdf",
    job_type: "ocr",
    status: "queued",
    progress: 0,
    queue_ahead: null,
    created_at: "2024-01-01T00:00:00Z",
    started_at: null,
    completed_at: null,
    error_log: null,
    ...overrides,
  };
}

const mockJobsResponse: DashboardJobsResponse = {
  items: [
    jobRow({ id: "job-next", queue_ahead: 0, status: "queued" }),
    jobRow({ id: "job-third", queue_ahead: 3, status: "queued" }),
    jobRow({ id: "job-running", status: "running", progress: 0.5 }),
  ],
  total: 3,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetDashboardSummary.mockResolvedValue(mockSummary);
    mockGetDashboardBooks.mockResolvedValue(mockBooksResponse);
    mockGetDashboardJobs.mockResolvedValue(mockJobsResponse);
    mockCancelJob.mockResolvedValue({ id: "job-1", status: "cancelled" });
  });

  it("renders the summary cards", async () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("Your books").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Total books")).toBeDefined();
    expect(screen.getByText("OCR queue")).toBeDefined();
    expect(screen.getByText("LLM queue")).toBeDefined();
  });

  it("renders owned books with their status", async () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("My Telugu Book").length).toBeGreaterThan(0);
    });
  });

  it("renders jobs with queue-ahead labels", async () => {
    render(<DashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Next up")).toBeDefined();
    });
    expect(screen.getByText("3 ahead")).toBeDefined();
    expect(screen.getByText("Running now")).toBeDefined();
  });

  it("cancels a queued job", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Next up")).toBeDefined();
    });

    await user.click(screen.getAllByRole("button", { name: "Cancel" })[0]);

    await waitFor(() => {
      expect(mockCancelJob).toHaveBeenCalledWith("job-next");
    });
  });

  it("offers book management actions in a menu", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("My Telugu Book").length).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("button", { name: /Actions for My Telugu Book/i }));

    expect(await screen.findByRole("menu")).toBeDefined();
    expect(screen.getByRole("menuitem", { name: "Open book detail" })).toBeDefined();
    expect(screen.getByRole("menuitem", { name: "Metadata review" })).toBeDefined();
    expect(screen.getByRole("menuitem", { name: "Delete…" })).toBeDefined();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import AdminJobsPage from "@/app/admin/jobs/page";
import {
  getAdminJobs,
  getAdminJobSummary,
  cancelAdminJob,
  cancelAdminJobsBulk,
  retryAdminJob,
  type AdminJobRow,
  type AdminJobsResponse,
  type JobSummaryResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getAdminJobs: vi.fn(),
    getAdminJobSummary: vi.fn(),
    cancelAdminJob: vi.fn(),
    cancelAdminJobsBulk: vi.fn(),
    retryAdminJob: vi.fn(),
  };
});

const mockGetAdminJobs = vi.mocked(getAdminJobs);
const mockGetAdminJobSummary = vi.mocked(getAdminJobSummary);
const mockCancelAdminJob = vi.mocked(cancelAdminJob);
const mockCancelAdminJobsBulk = vi.mocked(cancelAdminJobsBulk);
const mockRetryAdminJob = vi.mocked(retryAdminJob);

function jobRow(overrides: Partial<AdminJobRow>): AdminJobRow {
  return {
    id: "job-1",
    book_id: "book-1",
    requested_by_id: "user-1",
    book_title: "Telugu Epic",
    book_filename: "telugu.pdf",
    owner_display_name: "Alice",
    owner_email: "alice@example.com",
    job_type: "ocr",
    status: "queued",
    progress: 0,
    created_at: "2024-01-01T10:00:00Z",
    started_at: null,
    completed_at: null,
    last_progress_at: null,
    error_log: null,
    celery_task_id: "task-1",
    duration_seconds: null,
    queue_ahead: 0,
    stage_name: "ocr",
    stage_status: "initiated",
    ...overrides,
  };
}

function jobsPage(items: AdminJobRow[]): AdminJobsResponse {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 10,
    total_pages: 1,
  };
}

const summary: JobSummaryResponse = {
  total: 3,
  queued: 1,
  running: 1,
  completed: 1,
  failed: 0,
  cancelled: 0,
  by_type: { ocr: 2, llm: 1 },
  by_user: [
    {
      user_id: "user-1",
      display_name: "Alice",
      email: "alice@example.com",
      total: 3,
      queued: 1,
      running: 1,
      completed: 1,
      failed: 0,
      cancelled: 0,
    },
  ],
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

describe("AdminJobsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAdminJobSummary.mockResolvedValue(summary);
    mockGetAdminJobs.mockResolvedValue(
      jobsPage([
        jobRow({ id: "job-queued", book_title: "Queued Book", status: "queued" }),
        jobRow({ id: "job-failed", book_title: "Failed Book", status: "failed", error_log: "OCR failed" }),
      ]),
    );
    mockCancelAdminJob.mockResolvedValue({ id: "job-queued", status: "cancelled" });
    mockCancelAdminJobsBulk.mockResolvedValue({
      results: [{ id: "job-queued", status: "cancelled", ok: true, error: null }],
    });
    mockRetryAdminJob.mockResolvedValue({
      job_id: "job-retry",
      book_id: "book-1",
      status: "queued",
    });
  });

  it("renders the queue overview from the summary endpoint", async () => {
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Queue overview")).toBeDefined();
    });
    expect(screen.getByText("Total jobs")).toBeDefined();
    expect(screen.getByText("Processing")).toBeDefined();
  });

  it("shows the per-user breakdown when expanded", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("By user")).toBeDefined();
    });
    await user.click(screen.getByRole("button", { name: /By user/ }));

    expect(await screen.findByRole("columnheader", { name: "User" })).toBeDefined();
    expect(screen.getByRole("columnheader", { name: "Cancelled" })).toBeDefined();
  });

  it("sends the selected sort column to the API", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await screen.findByText("Queued Book");
    await user.click(screen.getByRole("button", { name: "Type" }));

    await waitFor(() => {
      const lastCall = mockGetAdminJobs.mock.calls.at(-1)?.[0];
      expect(lastCall?.sort).toBe("job_type");
      expect(lastCall?.order).toBe("desc");
    });
  });

  it("reveals job details in an expanded row", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Queued Book")).toBeDefined();
    });
    const row = screen.getByText("Queued Book").closest("tr");
    expect(row).not.toBeNull();
    await user.click(within(row as HTMLElement).getByRole("button", { name: "Details" }));

    expect(await screen.findByText("Job ID")).toBeDefined();
    expect(screen.getByText("task-1")).toBeDefined();
  });

  it("cancels a single job after confirmation", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Queued Book")).toBeDefined();
    });
    const row = screen.getByText("Queued Book").closest("tr") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Cancel job" }));

    const confirmButtons = screen.getAllByRole("button", { name: "Cancel job" });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockCancelAdminJob).toHaveBeenCalledWith("job-queued");
    });
  });

  it("bulk-cancels selected jobs", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Queued Book")).toBeDefined();
    });
    await user.click(
      screen.getByRole("checkbox", {
        name: /Select ocr job for Queued Book/i,
      }),
    );

    expect(await screen.findByText(/1 job selected/i)).toBeDefined();
    const barButton = screen.getAllByRole("button", {
      name: "Cancel selected jobs",
    })[0];
    await user.click(barButton);

    const confirmButtons = screen.getAllByRole("button", {
      name: "Cancel selected jobs",
    });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockCancelAdminJobsBulk).toHaveBeenCalledWith(["job-queued"]);
    });
  });

  it("retries a failed job", async () => {
    const user = userEvent.setup();
    render(<AdminJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Failed Book")).toBeDefined();
    });
    const row = screen.getByText("Failed Book").closest("tr") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(mockRetryAdminJob).toHaveBeenCalledWith("job-failed");
    });
  });
});

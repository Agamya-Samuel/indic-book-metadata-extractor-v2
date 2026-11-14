import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { useJobProgress } from "@/hooks/use-job-progress";
import type { JobResponse } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getAllBookJobs: vi.fn(),
  cancelJob: vi.fn(),
}));

import { getAllBookJobs, cancelJob } from "@/lib/api";
const mockGetBookJobs = vi.mocked(getAllBookJobs);
const mockCancelJob = vi.mocked(cancelJob);

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

function makeJob(overrides: Partial<JobResponse> = {}): JobResponse {
  return {
    id: "job-1",
    book_id: "book-1",
    job_type: "ocr",
    status: "running",
    progress: 0,
    created_at: "2024-01-02T00:00:00",
    started_at: "2024-01-02T00:00:00",
    completed_at: null,
    error_log: null,
    ...overrides,
  };
}

describe("useJobProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("picks the newest job of the requested type", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ id: "new", job_type: "llm", status: "running", progress: 30 }),
      makeJob({ id: "old", job_type: "ocr", status: "completed" }),
    ]);

    const { result } = renderHook(
      () => useJobProgress({ bookId: "book-1", jobType: "llm" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.job?.id).toBe("new"));
    expect(result.current.progress).toBe(30);
    expect(result.current.isRunning).toBe(true);
  });

  it("ignores a completed run that predates the current run", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({
        id: "old",
        status: "completed",
        created_at: "2024-01-01T00:00:00",
        started_at: "2024-01-01T00:00:00",
        completed_at: "2024-01-01T00:05:00",
      }),
    ]);

    const { result } = renderHook(
      () =>
        useJobProgress({
          bookId: "book-1",
          jobType: "llm",
          startedAt: "2024-01-02T00:00:00",
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.job).toBeNull();
    expect(result.current.isComplete).toBe(false);
  });

  it("tracks the job created after the recorded run start", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({
        id: "new",
        job_type: "llm",
        status: "running",
        created_at: "2024-01-02T00:00:01",
        started_at: "2024-01-02T00:00:01",
      }),
      makeJob({
        id: "old",
        job_type: "llm",
        status: "completed",
        created_at: "2024-01-01T00:00:00",
        started_at: "2024-01-01T00:00:00",
      }),
    ]);

    const { result } = renderHook(
      () =>
        useJobProgress({
          bookId: "book-1",
          jobType: "llm",
          startedAt: "2024-01-02T00:00:00",
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.job?.id).toBe("new"));
  });

  it("uses an explicit jobId when provided", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ id: "a", status: "running" }),
      makeJob({ id: "b", status: "completed" }),
    ]);

    const { result } = renderHook(
      () => useJobProgress({ bookId: "book-1", jobId: "b" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.job?.id).toBe("b"));
    expect(result.current.isComplete).toBe(true);
  });

  it("cancels the scoped job", async () => {
    mockGetBookJobs.mockResolvedValue([makeJob({ id: "job-1" })]);
    mockCancelJob.mockResolvedValue({ id: "job-1", status: "cancelled" });

    const { result } = renderHook(
      () => useJobProgress({ bookId: "book-1", jobType: "ocr" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.job?.id).toBe("job-1"));
    await act(async () => {
      await result.current.cancel();
    });
    expect(mockCancelJob).toHaveBeenCalledWith("job-1");
  });
});
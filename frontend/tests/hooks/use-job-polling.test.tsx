import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { useJobPolling } from "@/hooks/use-job-polling";
import type { JobResponse } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getBookJobs: vi.fn(),
}));

import { getBookJobs } from "@/lib/api";
const mockGetBookJobs = vi.mocked(getBookJobs);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
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
    created_at: "2024-01-01T00:00:00",
    started_at: "2024-01-01T00:00:00",
    completed_at: null,
    error_log: null,
    ...overrides,
  };
}

describe("useJobPolling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns initial state when no jobId", async () => {
    mockGetBookJobs.mockResolvedValue([]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.job).toBeNull();
    });
    expect(result.current.allJobs).toEqual([]);
    expect(result.current.isComplete).toBe(false);
    expect(result.current.isFailed).toBe(false);
  });

  it("returns running job when jobId matches", async () => {
    mockGetBookJobs.mockResolvedValue([makeJob({ status: "running" })]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1", jobId: "job-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isRunning).toBe(true);
    });
    expect(result.current.job?.status).toBe("running");
    expect(result.current.isTerminal).toBe(false);
  });

  it("returns isComplete when job is completed", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ status: "completed", progress: 1 }),
    ]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1", jobId: "job-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isComplete).toBe(true);
    });
    expect(result.current.isTerminal).toBe(true);
  });

  it("returns isFailed when job is failed", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ status: "failed", error_log: "OCR failed" }),
    ]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1", jobId: "job-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isFailed).toBe(true);
    });
    expect(result.current.errorLog).toBe("OCR failed");
    expect(result.current.isTerminal).toBe(true);
  });

  it("returns isCancelled when job is cancelled", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ status: "cancelled" }),
    ]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1", jobId: "job-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isCancelled).toBe(true);
    });
  });

  it("returns progress from job", async () => {
    mockGetBookJobs.mockResolvedValue([
      makeJob({ progress: 0.5 }),
    ]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1", jobId: "job-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.progress).toBe(0.5);
    });
  });

  it("returns progress 0 when no job", async () => {
    mockGetBookJobs.mockResolvedValue([]);
    const { result } = renderHook(
      () => useJobPolling({ bookId: "book-1" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.progress).toBe(0);
    });
  });
});

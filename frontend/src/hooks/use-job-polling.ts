"use client";

import { useQuery } from "@tanstack/react-query";
import { getBookJobs, type JobResponse } from "@/lib/api";

type JobTerminalStatus = "completed" | "failed" | "cancelled";

function isTerminalStatus(status: string): status is JobTerminalStatus {
  return ["completed", "failed", "cancelled"].includes(status);
}

interface UseJobPollingOptions {
  bookId: string;
  jobId?: string;
  jobType?: "ocr" | "llm" | "preprocessing";
  intervalMs?: number;
  enabled?: boolean;
}

interface UseJobPollingReturn {
  job: JobResponse | null;
  allJobs: JobResponse[];
  isRunning: boolean;
  isComplete: boolean;
  isFailed: boolean;
  isCancelled: boolean;
  isTerminal: boolean;
  progress: number;
  errorLog: string | null;
  isPolling: boolean;
}

export function useJobPolling({
  bookId,
  jobId,
  jobType,
  intervalMs = 2000,
  enabled = true,
}: UseJobPollingOptions): UseJobPollingReturn {
  const { data: allJobs = [], isLoading } = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
    refetchInterval: (query) => {
      if (!enabled) return false;
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return false;

      const jobs = query.state.data;
      if (jobId && jobs) {
        const target = jobs.find((j) => j.id === jobId);
        if (target && isTerminalStatus(target.status)) return false;
      }

      const anyRunning = jobs?.some((j) => !isTerminalStatus(j.status));
      if (!jobId && !anyRunning) return false;

      return intervalMs;
    },
    enabled: !!bookId && enabled,
  });

  // Filter jobs by type if specified
  const filteredJobs = jobType
    ? allJobs.filter((j) => j.job_type === jobType)
    : allJobs;

  const job = jobId
    ? filteredJobs.find((j) => j.id === jobId) ?? null
    : filteredJobs[0] ?? null;

  const isRunning = !isLoading && (job?.status === "running" || job?.status === "queued");
  const isComplete = job?.status === "completed";
  const isFailed = job?.status === "failed";
  const isCancelled = job?.status === "cancelled";
  const isTerminal = !!job && isTerminalStatus(job.status);

  const isPolling = enabled && !isTerminal && !isLoading;

  return {
    job,
    allJobs,
    isRunning,
    isComplete,
    isFailed,
    isCancelled,
    isTerminal,
    progress: job?.progress ?? 0,
    errorLog: job?.error_log ?? null,
    isPolling,
  };
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { cancelJob, type JobResponse } from "@/lib/api";
import { useJobPolling } from "@/hooks/use-job-polling";

export type JobKind = "ocr" | "llm" | "preprocessing" | "page_extraction";

interface UseJobProgressOptions {
  bookId: string;
  jobType?: JobKind;
  /** Explicit job to track, e.g. from `/extracting-pages?job=<id>`. */
  jobId?: string;
  /**
   * ISO timestamp recorded when the current run started. Jobs older than
   * this are ignored, which is what stops a completed prior run from
   * shadowing a new one (the LLM-config trap).
   */
  startedAt?: string | null;
  enabled?: boolean;
  intervalMs?: number;
}

interface UseJobProgressReturn {
  /** The job scoped to the current run, or the newest of the type. */
  job: JobResponse | null;
  /** All jobs for the book (newest first). */
  jobs: JobResponse[];
  progress: number;
  isRunning: boolean;
  isComplete: boolean;
  isFailed: boolean;
  isCancelled: boolean;
  isTerminal: boolean;
  isPolling: boolean;
  isLoading: boolean;
  errorLog: string | null;
  /** Milliseconds since the job started (or until it finished). */
  elapsedMs: number;
  cancel: () => Promise<void>;
  cancelling: boolean;
  refetch: () => void;
}

function jobTimestamp(job: JobResponse): number | null {
  const ts = job.started_at ?? job.created_at;
  if (!ts) return null;
  const parsed = Date.parse(ts);
  return Number.isNaN(parsed) ? null : parsed;
}

export function useJobProgress({
  bookId,
  jobType,
  jobId,
  startedAt,
  enabled = true,
  intervalMs = 2000,
}: UseJobProgressOptions): UseJobProgressReturn {
  const queryClient = useQueryClient();
  const polling = useJobPolling({ bookId, jobType, intervalMs, enabled });
  const [now, setNow] = useState(() => Date.now());
  const [cancelling, setCancelling] = useState(false);

  const scopedJob = useMemo<JobResponse | null>(() => {
    const jobs = jobType
      ? polling.allJobs.filter((j) => j.job_type === jobType)
      : polling.allJobs;

    if (jobId) {
      return jobs.find((j) => j.id === jobId) ?? null;
    }

    if (startedAt) {
      const start = Date.parse(startedAt);
      if (!Number.isNaN(start)) {
        const matching = jobs.filter((j) => {
          const ts = jobTimestamp(j);
          return ts !== null && ts >= start - 1000;
        });
        return matching[0] ?? null;
      }
    }

    return jobs[0] ?? null;
  }, [polling.allJobs, jobType, jobId, startedAt]);

  const isRunning =
    scopedJob?.status === "running" || scopedJob?.status === "queued";
  const isComplete = scopedJob?.status === "completed";
  const isFailed = scopedJob?.status === "failed";
  const isCancelled = scopedJob?.status === "cancelled";
  const isTerminal = isComplete || isFailed || isCancelled;

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  const elapsedMs = useMemo(() => {
    if (!scopedJob) return 0;
    const start = jobTimestamp(scopedJob);
    if (start === null) return 0;
    const end = scopedJob.completed_at
      ? Date.parse(scopedJob.completed_at)
      : now;
    return Math.max(0, (Number.isNaN(end) ? now : end) - start);
  }, [scopedJob, now]);

  const cancel = useCallback(async () => {
    if (!scopedJob) return;
    setCancelling(true);
    try {
      await cancelJob(scopedJob.id);
      await queryClient.invalidateQueries({
        queryKey: ["book", bookId, "jobs"],
      });
    } finally {
      setCancelling(false);
    }
  }, [scopedJob, queryClient, bookId]);

  return {
    job: scopedJob,
    jobs: polling.allJobs,
    progress: scopedJob?.progress ?? 0,
    isRunning,
    isComplete,
    isFailed,
    isCancelled,
    isTerminal,
    isPolling: enabled && isRunning,
    isLoading: polling.isLoading,
    errorLog: scopedJob?.error_log ?? null,
    elapsedMs,
    cancel,
    cancelling,
    refetch: polling.refetch,
  };
}

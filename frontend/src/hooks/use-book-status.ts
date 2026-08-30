"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookJobs,
  type BookDetail,
  type JobResponse,
} from "@/lib/api";
import { useSSE } from "@/hooks/use-sse";

type BookStatus =
  | "uploaded"
  | "pages_selected"
  | "ocr_running"
  | "ocr_complete"
  | "llm_running"
  | "awaiting_review"
  | "complete";

const RUNNING_STATUSES: BookStatus[] = [
  "uploaded",
  "pages_selected",
  "ocr_running",
  "llm_running",
];

interface UseBookStatusOptions {
  bookId: string;
  pollIntervalMs?: number;
}

interface UseBookStatusReturn {
  book: BookDetail | null;
  jobs: JobResponse[];
  status: BookStatus | null;
  isRunning: boolean;
  isComplete: boolean;
  isAwaitingReview: boolean;
  needsReview: boolean;
  lowConfidenceCount: number;
  progress: number;
  errorLog: string | null;
  pipelineFailed: boolean;
  pipelineError: string | null;
  isPolling: boolean;
  connectionMode: "sse" | "polling" | "idle";
}

export function useBookStatus({
  bookId,
  pollIntervalMs = 2000,
}: UseBookStatusOptions): UseBookStatusReturn {
  const queryClient = useQueryClient();
  const [pipelineFailed, setPipelineFailed] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    enabled: !!bookId,
    staleTime: 5_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
    enabled: !!bookId,
    refetchInterval: () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return pollIntervalMs;
      }
      const jobs = jobsQuery.data as JobResponse[] | undefined;
      const hasRunning = jobs?.some(
        (j) => j.status === "queued" || j.status === "running"
      );
      const bookStatus = (bookQuery.data?.status ?? "") as BookStatus;
      if (!hasRunning && !RUNNING_STATUSES.includes(bookStatus)) {
        return false;
      }
      return pollIntervalMs;
    },
    staleTime: 1_000,
  });

  useSSE({
    bookId,
    enabled: !!bookId,
    onJobComplete: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
    onJobFailed: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
    },
    onPipelineComplete: () => {
      setPipelineFailed(false);
      setPipelineError(null);
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
    onPipelineFailed: (stage, error) => {
      setPipelineFailed(true);
      setPipelineError(`${stage ?? "pipeline"}: ${error}`);
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
    onAwaitingReview: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
    onBookStatusChanged: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
  });

  const book = bookQuery.data ?? null;
  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);
  const status = (book?.status ?? null) as BookStatus | null;
  const isAwaitingReview = status === "awaiting_review";
  const isComplete = status === "complete" || isAwaitingReview;
  const isRunning = status !== null && RUNNING_STATUSES.includes(status);
  const needsReview = isAwaitingReview && (book?.needs_review ?? false);
  const lowConfidenceCount = book?.low_confidence_count ?? 0;

  const ocrJob = useMemo(
    () => jobs.find((j) => j.job_type === "ocr"),
    [jobs]
  );
  const llmJob = useMemo(
    () => jobs.find((j) => j.job_type === "llm"),
    [jobs]
  );
  const progress = llmJob?.progress ?? ocrJob?.progress ?? 0;
  const errorLog =
    pipelineError ??
    jobs.find((j) => j.status === "failed")?.error_log ??
    null;

  const connectionMode: "sse" | "polling" | "idle" = isRunning ? "sse" : "idle";

  return {
    book,
    jobs,
    status,
    isRunning,
    isComplete,
    isAwaitingReview,
    needsReview,
    lowConfidenceCount,
    progress,
    errorLog,
    pipelineFailed,
    pipelineError,
    isPolling: isRunning,
    connectionMode,
  };
}

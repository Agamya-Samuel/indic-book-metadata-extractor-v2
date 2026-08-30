"use client";

import { useCallback, useMemo, useRef, useState } from "react";
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

  // Refs to avoid TDZ in refetchInterval — the callback is captured as part
  // of the useQuery options object *before* the const is assigned, so closing
  // over `jobsQuery` / `bookQuery` directly triggers "Cannot access … before
  // initialization" in minified builds.
  const bookDataRef = useRef<BookDetail | undefined>(undefined);
  const jobsDataRef = useRef<JobResponse[] | undefined>(undefined);

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    enabled: !!bookId,
    staleTime: 5_000,
  });
  bookDataRef.current = bookQuery.data;

  const jobsQuery = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
    enabled: !!bookId,
    refetchInterval: () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return pollIntervalMs;
      }
      const jobs = jobsDataRef.current as JobResponse[] | undefined;
      const hasRunning = jobs?.some(
        (j) => j.status === "queued" || j.status === "running"
      );
      const bookStatus = (bookDataRef.current?.status ?? "") as BookStatus;
      if (!hasRunning && !RUNNING_STATUSES.includes(bookStatus)) {
        return false;
      }
      return pollIntervalMs;
    },
    staleTime: 1_000,
  });
  jobsDataRef.current = jobsQuery.data;

  const handleJobComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
  }, [queryClient, bookId]);

  const handleJobFailed = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
  }, [queryClient, bookId]);

  const handlePipelineComplete = useCallback(() => {
    setPipelineFailed(false);
    setPipelineError(null);
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
  }, [queryClient, bookId]);

  const handlePipelineFailed = useCallback(
    (stage: string | undefined, error: string) => {
      setPipelineFailed(true);
      setPipelineError(`${stage ?? "pipeline"}: ${error}`);
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    },
    [queryClient, bookId],
  );

  const handleAwaitingReview = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
  }, [queryClient, bookId]);

  const handleBookStatusChanged = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
  }, [queryClient, bookId]);

  useSSE({
    bookId,
    enabled: !!bookId,
    onJobComplete: handleJobComplete,
    onJobFailed: handleJobFailed,
    onPipelineComplete: handlePipelineComplete,
    onPipelineFailed: handlePipelineFailed,
    onAwaitingReview: handleAwaitingReview,
    onBookStatusChanged: handleBookStatusChanged,
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

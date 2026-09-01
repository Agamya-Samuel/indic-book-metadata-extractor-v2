"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { JobResponse } from "@/lib/api";

type SSEEventType =
  | "connected"
  | "snapshot"
  | "heartbeat"
  | "job_started"
  | "job_progress"
  | "job_complete"
  | "job_failed"
  | "job_cancelled"
  | "error"
  | "job.terminal"
  | "job.progress"
  | "pipeline.started"
  | "pipeline.stage_started"
  | "pipeline.stage_completed"
  | "pipeline.stage_failed"
  | "pipeline.completed"
  | "pipeline.failed"
  | "book.status_changed"
  | "book.awaiting_review";

interface SSEEvent {
  type: SSEEventType | string;
  book_id: string;
  id?: string;
  job_id?: string;
  job_type?: string;
  status?: string;
  progress?: number;
  error?: string;
  error_log?: string;
  timestamp?: string;
  stage?: string;
  low_confidence_count?: number;
  from_status?: string;
  language?: string;
  selected_count?: number;
}

interface UseSSEOptions {
  bookId: string;
  enabled?: boolean;
  onJobComplete?: (jobId: string, jobType: string) => void;
  onJobFailed?: (jobId: string, jobType: string, error: string) => void;
  onPipelineComplete?: () => void;
  onPipelineFailed?: (stage: string | undefined, error: string) => void;
  onAwaitingReview?: (lowConfidenceCount: number) => void;
  onBookStatusChanged?: (status: string) => void;
}

// Event names the backend emits with a custom ``event:`` field. The
// default ``onmessage`` only fires for unnamed events, so we attach
// named listeners for everything we care about.
const NAMED_EVENTS = [
  "job.terminal",
  "job.progress",
  "book.status_changed",
  "book.awaiting_review",
  "pipeline.completed",
  "pipeline.failed",
  "pipeline.stage_failed",
] as const;

export function useSSE({
  bookId,
  enabled = true,
  onJobComplete,
  onJobFailed,
  onPipelineComplete,
  onPipelineFailed,
  onAwaitingReview,
  onBookStatusChanged,
}: UseSSEOptions) {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;
  const connectRef = useRef<(() => void) | null>(null);
  const openingRef = useRef(false);

  // Store callbacks in a ref so `connect` doesn't depend on them directly.
  // This prevents the SSE connection from being torn down and recreated on
  // every render when callers pass inline arrow functions.
  const callbacksRef = useRef({
    onJobComplete,
    onJobFailed,
    onPipelineComplete,
    onPipelineFailed,
    onAwaitingReview,
    onBookStatusChanged,
  });
  useEffect(() => {
    callbacksRef.current = {
      onJobComplete,
      onJobFailed,
      onPipelineComplete,
      onPipelineFailed,
      onAwaitingReview,
      onBookStatusChanged,
    };
  });

  const dispatch = useCallback((data: SSEEvent) => {
    if (
      data.type === "snapshot" ||
      data.type === "heartbeat" ||
      data.type === "connected"
    ) {
      return;
    }

    if (
      data.type === "job.progress" ||
      data.type === "job.terminal" ||
      data.type === "job_progress" ||
      data.type === "job_started" ||
      data.type === "job_complete" ||
      data.type === "job_failed" ||
      data.type === "job_cancelled"
    ) {
      // Only update the React Query cache; no immediate re-fetch so a
      // high-frequency progress event stream doesn't hammer the backend
      // with hundreds of GETs.
      queryClient.setQueryData<JobResponse[]>(
        ["book", bookId, "jobs"],
        (oldData) => {
          if (!oldData) return oldData;
          const jobId = data.job_id || data.id;
          if (!jobId) return oldData;
          const jobIndex = oldData.findIndex((j) => j.id === jobId);

          if (jobIndex === -1) {
            const inferredStatus =
              data.status ||
              (data.type === "job_complete" || (data.type === "job.terminal" && data.status === "completed")
                ? "completed"
                : data.type === "job_failed" || (data.type === "job.terminal" && data.status === "failed")
                  ? "failed"
                  : data.type === "job_cancelled"
                    ? "cancelled"
                    : "running");
            const newJob: JobResponse = {
              id: jobId,
              book_id: bookId,
              job_type: data.job_type || "unknown",
              status: inferredStatus,
              progress: data.progress ?? (inferredStatus === "completed" ? 100 : 0),
              error_log: data.error || data.error_log || null,
              created_at: data.timestamp || null,
              started_at: inferredStatus === "running" ? data.timestamp || null : null,
              completed_at:
                inferredStatus === "completed" ||
                inferredStatus === "failed" ||
                inferredStatus === "cancelled"
                  ? data.timestamp || null
                  : null,
            };
            return [...oldData, newJob];
          }

          const updatedJobs = [...oldData];
          const existingJob = updatedJobs[jobIndex];
          let newProgress = existingJob.progress;
          if (data.progress !== undefined) {
            newProgress = data.progress;
          } else if (
            data.type === "job_complete" ||
            (data.type === "job.terminal" && data.status === "completed")
          ) {
            newProgress = 100;
          }
          const isTerminal =
            data.type === "job_complete" ||
            data.type === "job_failed" ||
            data.type === "job_cancelled" ||
            (data.type === "job.terminal" && data.status);
          updatedJobs[jobIndex] = {
            ...existingJob,
            status: data.status || existingJob.status,
            progress: newProgress,
            error_log: data.error || data.error_log || existingJob.error_log,
            completed_at: isTerminal
              ? data.timestamp || existingJob.completed_at || null
              : existingJob.completed_at,
          };
          return updatedJobs;
        },
      );
    }

    const cbs = callbacksRef.current;

    if (
      (data.type === "job_complete" ||
        (data.type === "job.terminal" && data.status === "completed")) &&
      cbs.onJobComplete
    ) {
      cbs.onJobComplete(data.job_id || data.id || "", data.job_type || "");
    }

    if (
      (data.type === "job_failed" ||
        (data.type === "job.terminal" && data.status === "failed")) &&
      cbs.onJobFailed
    ) {
      cbs.onJobFailed(
        data.job_id || data.id || "",
        data.job_type || "",
        data.error || data.error_log || "Unknown error",
      );
    }

    if (data.type === "pipeline.completed" && cbs.onPipelineComplete) {
      cbs.onPipelineComplete();
    }

    if (data.type === "pipeline.failed" && cbs.onPipelineFailed) {
      cbs.onPipelineFailed(data.stage, data.error || "Pipeline failed");
    }

    if (data.type === "book.awaiting_review" && cbs.onAwaitingReview) {
      cbs.onAwaitingReview(data.low_confidence_count ?? 0);
    }

    if (data.type === "book.status_changed" && cbs.onBookStatusChanged) {
      cbs.onBookStatusChanged(data.status || "");
    }
  }, [bookId, queryClient]);

  const connect = useCallback(() => {
    if (!enabled || !bookId) return;
    // Guard against re-entrant connect (e.g. a fresh effect re-firing
    // while a reconnect timeout is pending) so we don't open duplicate
    // EventSource connections.
    if (openingRef.current) return;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    openingRef.current = true;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
    const url = `${apiUrl}/sse/books/${bookId}/events`;

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      openingRef.current = false;
      reconnectAttempts.current = 0;
    };

    // Default-message fallback (any event without a custom ``event:`` field).
    eventSource.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);
        dispatch(data);
      } catch {
        // ignore non-JSON
      }
    };

    // Named-event listeners for events like ``event: job.terminal\ndata: {…}``
    // which the default ``onmessage`` never sees.
    NAMED_EVENTS.forEach((eventName) => {
      eventSource.addEventListener(eventName, (event) => {
        if (!(event instanceof MessageEvent)) return;
        try {
          const data: SSEEvent = JSON.parse(event.data);
          dispatch(data);
        } catch {
          // ignore non-JSON
        }
      });
    });

    eventSource.onerror = () => {
      openingRef.current = false;
      try {
        eventSource.close();
      } catch {
        // ignore
      }
      eventSourceRef.current = null;

      if (reconnectAttempts.current < maxReconnectAttempts) {
        const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts.current);
        reconnectAttempts.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connectRef.current?.();
        }, delay);
      }
    };
  }, [bookId, enabled, dispatch]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    openingRef.current = false;
    reconnectAttempts.current = 0;
  }, []);

  useEffect(() => {
    if (enabled && bookId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [enabled, bookId, connect, disconnect]);

  return {
    disconnect,
    reconnect: connect,
  };
}

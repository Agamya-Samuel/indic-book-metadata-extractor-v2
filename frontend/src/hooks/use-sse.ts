"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { JobResponse } from "@/lib/api";

type SSEEventType =
  | "connected"
  | "job_started"
  | "job_progress"
  | "job_complete"
  | "job_failed"
  | "job_cancelled"
  | "error";

interface SSEEvent {
  type: SSEEventType;
  book_id: string;
  id?: string;
  job_id?: string;
  job_type?: string;
  status?: string;
  progress?: number;
  error?: string;
  error_log?: string;
  timestamp?: string;
}

interface UseSSEOptions {
  bookId: string;
  enabled?: boolean;
  onJobComplete?: (jobId: string, jobType: string) => void;
  onJobFailed?: (jobId: string, jobType: string, error: string) => void;
}

export function useSSE({
  bookId,
  enabled = true,
  onJobComplete,
  onJobFailed,
}: UseSSEOptions) {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;

  const updateJobCache = useCallback((event: SSEEvent) => {
    queryClient.setQueryData<JobResponse[]>(
      ["book", bookId, "jobs"],
      (oldData) => {
        if (!oldData) return oldData;

        const jobId = event.job_id || event.id;
        if (!jobId) return oldData;

        const jobIndex = oldData.findIndex((j) => j.id === jobId);
        
        if (jobIndex === -1) {
          // New job, add it to the list
          const newJob: JobResponse = {
            id: jobId,
            book_id: bookId,
            job_type: event.job_type || "unknown",
            status: event.status || (event.type === "job_complete" ? "completed" : event.type === "job_failed" ? "failed" : "running"),
            progress: event.progress ?? (event.type === "job_complete" ? 100 : 0),
            error_log: event.error || event.error_log || null,
            created_at: event.timestamp || null,
            started_at: event.status === "running" ? event.timestamp || null : null,
            completed_at: event.type === "job_complete" || event.type === "job_failed" ? event.timestamp || null : null,
          };
          return [...oldData, newJob];
        }

        // Update existing job
        const updatedJobs = [...oldData];
        const existingJob = updatedJobs[jobIndex];
        
        let newProgress = existingJob.progress;
        if (event.progress !== undefined) {
          newProgress = event.progress;
        } else if (event.type === "job_complete") {
          newProgress = 100;
        }

        updatedJobs[jobIndex] = {
          ...existingJob,
          status: event.status || existingJob.status,
          progress: newProgress,
          error_log: event.error || event.error_log || existingJob.error_log,
          completed_at: (event.type === "job_complete" || event.type === "job_failed") 
            ? (event.timestamp || existingJob.completed_at || new Date().toISOString())
            : existingJob.completed_at,
        };

        return updatedJobs;
      }
    );

    // Also invalidate to ensure fresh data
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
  }, [bookId, queryClient]);

  const connect = useCallback(() => {
    if (!enabled || !bookId) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
    const url = `${apiUrl}/sse/books/${bookId}/events`;
    
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log(`SSE connected for book ${bookId}`);
      reconnectAttempts.current = 0;
    };

    eventSource.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);
        
        // Update React Query cache with job data
        updateJobCache(data);

        // Call specific callbacks
        if (data.type === "job_complete" && onJobComplete) {
          onJobComplete(data.job_id || data.id || "", data.job_type || "");
        }
        
        if (data.type === "job_failed" && onJobFailed) {
          onJobFailed(data.job_id || data.id || "", data.job_type || "", data.error || data.error_log || "Unknown error");
        }
      } catch (e) {
        console.error("Failed to parse SSE message:", e);
      }
    };

    eventSource.onerror = (error) => {
      console.error(`SSE error for book ${bookId}:`, error);
      eventSource.close();
      eventSourceRef.current = null;

      // Attempt reconnection with exponential backoff
      if (reconnectAttempts.current < maxReconnectAttempts) {
        const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts.current);
        reconnectAttempts.current++;
        
        console.log(`SSE reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
        
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        console.log(`SSE max reconnection attempts reached for book ${bookId}`);
      }
    };
  }, [bookId, enabled, onJobComplete, onJobFailed, updateJobCache]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
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

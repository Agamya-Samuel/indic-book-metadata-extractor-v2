"use client";

import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookJobs,
  retryExtraction,
  DEFAULT_EXTRACTION_CONFIG,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/error-handler";
import StatusBadge from "@/components/shared/status-badge";
import { SkeletonTable, SkeletonPageHeader } from "@/components/shared/skeleton";

export default function JobsPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: jobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
    staleTime: 0,
    gcTime: 60 * 1000,
    refetchInterval: (query) => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible")
        return false;
      const data = query.state.data;
      const anyRunning = data?.some(
        (j) => !["completed", "failed", "cancelled"].includes(j.status)
      );
      return anyRunning ? 2000 : false;
    },
  });

  const handleRetry = async (_jobId: string) => {
    try {
      await retryExtraction(bookId, DEFAULT_EXTRACTION_CONFIG);
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
    } catch (err) {
      console.error("Retry failed:", getErrorMessage(err));
    }
  };

  if (isLoadingBook || isLoadingJobs) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4">
          <div className="max-w-5xl mx-auto">
            <SkeletonPageHeader />
          </div>
        </div>
        <div className="max-w-5xl mx-auto p-6">
          <SkeletonTable rows={4} />
        </div>
      </div>
    );
  }

  const sortedJobs = [...(jobs ?? [])].sort((a, b) => {
    const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
    const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
    return dateB - dateA;
  });

  const anyRunning = sortedJobs.some(
    (j) => !["completed", "failed", "cancelled"].includes(j.status)
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Job Queue</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {book?.title || book?.filename || "Book"} &bull;{" "}
              {sortedJobs.length} job{sortedJobs.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {anyRunning && (
              <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400" aria-live="polite">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
                </span>
                Auto-refreshing...
              </div>
            )}
            <a
              href={`/books/${bookId}/llm-config`}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
            >
              LLM Config
            </a>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6">
        {sortedJobs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400 mb-4">No jobs found for this book.</p>
            <a
              href={`/books/${bookId}/llm-config`}
              className="text-blue-600 dark:text-blue-400 hover:underline text-sm"
            >
              Go to LLM Config to start extraction
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {sortedJobs.map((job) => (
              <div
                key={job.id}
                className="bg-white dark:bg-gray-800 shadow rounded-lg border-l-4 hover:shadow-md transition-shadow"
                style={{
                  borderLeftColor:
                    job.status === "completed"
                      ? "#22c55e"
                      : job.status === "failed"
                        ? "#ef4444"
                        : job.status === "running"
                          ? "#3b82f6"
                          : "#d1d5db",
                }}
              >
                <div className="px-5 py-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded ${
                          job.job_type === "ocr"
                            ? "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
                            : job.job_type === "llm"
                              ? "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300"
                              : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {job.job_type === "llm"
                          ? "LLM Extraction"
                          : job.job_type === "ocr"
                            ? "OCR"
                            : job.job_type}
                      </span>
                      <StatusBadge status={job.status} />
                    </div>
                    <div className="flex items-center gap-2">
                      {job.status === "failed" && job.job_type === "llm" && (
                        <button
                          onClick={() => handleRetry(job.id)}
                          className="px-3 py-1 text-xs text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50"
                          aria-label="Retry extraction"
                        >
                          Retry
                        </button>
                      )}
                      {job.status === "completed" && job.job_type === "llm" && (
                        <a
                          href={`/books/${bookId}/metadata-review`}
                          className="px-3 py-1 text-xs text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded hover:bg-blue-100 dark:hover:bg-blue-900/50"
                          aria-label="View extraction results"
                        >
                          View Results
                        </a>
                      )}
                      {job.status === "completed" && job.job_type === "ocr" && (
                        <a
                          href={`/books/${bookId}/ocr-review`}
                          className="px-3 py-1 text-xs text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-800 rounded hover:bg-indigo-100 dark:hover:bg-indigo-900/50"
                        >
                          View OCR
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                    <div className="flex-1">
                      {(job.status === "running" || job.status === "queued") && (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                            <div
                              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                              style={{
                                width: `${Math.round(job.progress)}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400 w-10">
                            {Math.round(job.progress)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-400 dark:text-gray-500">
                    {job.created_at && (
                      <span>
                        Created: {new Date(job.created_at).toLocaleString()}
                      </span>
                    )}
                    {job.started_at && (
                      <span>
                        Started: {new Date(job.started_at).toLocaleString()}
                      </span>
                    )}
                    {job.completed_at && (
                      <span>
                        Completed: {new Date(job.completed_at).toLocaleString()}
                      </span>
                    )}
                  </div>

                  {job.error_log && (
                    <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-700 dark:text-red-400">
                      <p className="font-medium">Error:</p>
                      <p className="mt-0.5 whitespace-pre-wrap">
                        {job.error_log}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

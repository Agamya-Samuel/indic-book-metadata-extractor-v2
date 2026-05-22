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

export default function JobsPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
  });

  const { data: jobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
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
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
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
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Job Queue</h1>
            <p className="text-sm text-gray-500">
              {book?.title || book?.filename || "Book"} &bull;{" "}
              {sortedJobs.length} job{sortedJobs.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {anyRunning && (
              <div className="flex items-center gap-2 text-sm text-blue-600">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
                </span>
                Auto-refreshing...
              </div>
            )}
            <a
              href={`/books/${bookId}/llm-config`}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
            >
              LLM Config
            </a>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6">
        {sortedJobs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-4">No jobs found for this book.</p>
            <a
              href={`/books/${bookId}/llm-config`}
              className="text-blue-600 hover:underline text-sm"
            >
              Go to LLM Config to start extraction
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {sortedJobs.map((job) => (
              <div
                key={job.id}
                className="bg-white shadow rounded-lg border-l-4 hover:shadow-md transition-shadow"
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
                            ? "bg-indigo-100 text-indigo-700"
                            : job.job_type === "llm"
                              ? "bg-purple-100 text-purple-700"
                              : "bg-gray-100 text-gray-700"
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
                          className="px-3 py-1 text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100"
                        >
                          Retry
                        </button>
                      )}
                      {job.status === "completed" && job.job_type === "llm" && (
                        <a
                          href={`/books/${bookId}/metadata-review`}
                          className="px-3 py-1 text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100"
                        >
                          View Results
                        </a>
                      )}
                      {job.status === "completed" && job.job_type === "ocr" && (
                        <a
                          href={`/books/${bookId}/ocr-review`}
                          className="px-3 py-1 text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded hover:bg-indigo-100"
                        >
                          View OCR
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <div className="flex-1">
                      {(job.status === "running" || job.status === "queued") && (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                            <div
                              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                              style={{
                                width: `${Math.round(job.progress)}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-10">
                            {Math.round(job.progress)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
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
                    <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
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

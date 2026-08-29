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
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, EmptyState, Progress } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

export default function JobsPage() {
  useDocumentTitle("Jobs");
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
      <div className="min-h-screen bg-[var(--background)]">
        <PageContainer>
          <SkeletonPageHeader />
          <div className="mt-6">
            <SkeletonTable rows={4} />
          </div>
        </PageContainer>
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
    <div className="min-h-screen bg-[var(--background)]">
      <PageContainer>
        <PageHeader
          title="Job Queue"
          description={
            <>
              {book?.title || book?.filename || "Book"} &bull;{" "}
              {sortedJobs.length} job{sortedJobs.length !== 1 ? "s" : ""}
            </>
          }
          actions={
            <div className="flex items-center gap-3">
              {anyRunning && (
                <div
                  className="flex items-center gap-2 text-[var(--text-sm)] text-[var(--info-700)] dark:text-[var(--info-100)]"
                  aria-live="polite"
                >
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--info-500)] opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--info-600)]" />
                  </span>
                  Auto-refreshing...
                </div>
              )}
              <LinkButton href={`/books/${bookId}/llm-config`} variant="outline">
                LLM Config
              </LinkButton>
            </div>
          }
        />

        {sortedJobs.length === 0 ? (
          <EmptyState
            title="No jobs found"
            description="This book has no processing jobs yet."
            action={
              <LinkButton href={`/books/${bookId}/llm-config`}>
                Go to LLM Config to start extraction
              </LinkButton>
            }
          />
        ) : (
          <Stack gap={3}>
            {sortedJobs.map((job) => {
              const accentColor =
                job.status === "completed"
                  ? "border-l-[var(--success-600)]"
                  : job.status === "failed"
                    ? "border-l-[var(--danger-600)]"
                    : job.status === "running"
                      ? "border-l-[var(--info-600)]"
                      : "border-l-[var(--border-strong)]";
              const jobTypeClasses =
                job.job_type === "ocr"
                  ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                  : job.job_type === "llm"
                    ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                    : "bg-[var(--surface-sunken)] text-[var(--text-muted)]";
              return (
                <Card
                  key={job.id}
                  className={cn("border-l-4", accentColor)}
                >
                  <Stack gap={2}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span
                          className={cn(
                            "px-2 py-0.5 text-[11px] font-medium rounded-[var(--radius-xs)] uppercase tracking-wide",
                            jobTypeClasses
                          )}
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
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleRetry(job.id)}
                            aria-label="Retry extraction"
                          >
                            Retry
                          </Button>
                        )}
                        {job.status === "completed" && job.job_type === "llm" && (
                          <LinkButton
                            size="sm"
                            variant="secondary"
                            href={`/books/${bookId}/metadata-review`}
                            aria-label="View extraction results"
                          >
                            View Results
                          </LinkButton>
                        )}
                        {job.status === "completed" && job.job_type === "ocr" && (
                          <LinkButton
                            size="sm"
                            variant="secondary"
                            href={`/books/${bookId}/ocr-review`}
                          >
                            View OCR
                          </LinkButton>
                        )}
                      </div>
                    </div>

                    {(job.status === "running" || job.status === "queued") && (
                      <div className="flex items-center gap-2">
                        <div className="flex-1">
                          <Progress value={job.progress} />
                        </div>
                        <span className="text-[var(--text-xs)] text-[var(--text-muted)] w-10 text-right tabular-nums">
                          {Math.round(job.progress)}%
                        </span>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-4 text-[var(--text-xs)] text-[var(--text-subtle)]">
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
                      <ErrorState
                        title="Error"
                        description={job.error_log}
                      />
                    )}
                  </Stack>
                </Card>
              );
            })}
          </Stack>
        )}
      </PageContainer>
    </div>
  );
}

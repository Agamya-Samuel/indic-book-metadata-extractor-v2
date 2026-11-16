"use client";

import { useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getBook } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobProgress } from "@/hooks/use-job-progress";
import { useSSE } from "@/hooks/use-sse";
import { toast } from "sonner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
import { LinkButton } from "@/components/shared/button";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import JobProgressCard from "@/components/shared/job-progress-card";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function LlmProcessingPage() {
  useDocumentTitle("Extracting metadata");
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;
  const jobId = searchParams.get("job") ?? undefined;

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const progress = useJobProgress({
    bookId,
    jobType: "llm",
    jobId,
    enabled: !!bookId,
  });

  useSSE({
    bookId,
    enabled: !!bookId,
    onJobComplete: (_jobId, jobType) => {
      if (jobType === "llm") toast.success("Metadata extraction completed");
    },
    onJobFailed: (_jobId, jobType, error) => {
      if (jobType === "llm") toast.error(`Extraction failed: ${error}`);
    },
  });

  useEffect(() => {
    if (!progress.isComplete) return;
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "metadata"] });
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
    const timer = setTimeout(() => {
      router.replace(`/books/${bookId}/metadata-review`);
    }, 800);
    return () => clearTimeout(timer);
  }, [progress.isComplete, bookId, queryClient, router]);

  if (isLoadingBook || progress.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <Spinner className="h-12 w-12 border-[3px] text-[var(--accent-text)]" />
      </div>
    );
  }

  if (!book) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState title="Book not found" />
      </div>
    );
  }

  if (!progress.job && !jobId) {
    return (
      <WorkflowShell bookId={bookId}>
        <PageContainer>
          <PageHeader
            eyebrow={getLanguageName(book.language)}
            title={book.title || book.filename}
            description="No metadata extraction is running for this book."
          />
          <EmptyState
            title="Nothing to extract"
            description="Configure the extraction settings, then start a run."
          />
          <div className="mt-4">
            <LinkButton href={`/books/${bookId}/llm-config`}>
              Go to LLM Configuration
            </LinkButton>
          </div>
        </PageContainer>
      </WorkflowShell>
    );
  }

  const failed = progress.isFailed;
  const cancelled = progress.isCancelled;
  const completed = progress.isComplete;

  return (
    <WorkflowShell bookId={bookId}>
      <PageContainer>
        <PageHeader
          eyebrow={getLanguageName(book.language)}
          title={book.title || book.filename}
          description="Extracting bibliographic metadata from the OCR text. This can take several minutes on CPU."
        />

        <Card>
          <JobProgressCard
            title={
              failed
                ? "Metadata extraction failed"
                : cancelled
                  ? "Metadata extraction cancelled"
                  : completed
                    ? "Metadata extraction complete"
                    : "Running LLM extraction"
            }
            progress={progress.progress}
            status={progress.job?.status ?? "queued"}
            phase="Extracting metadata fields in batch groups"
            itemLabel={`${Math.round(progress.progress)}% of batch groups complete`}
            elapsedMs={progress.elapsedMs}
            error={progress.errorLog}
            onCancel={progress.cancel}
            cancelling={progress.cancelling}
            onRetry={failed ? () => router.push(`/books/${bookId}/llm-config`) : undefined}
          />

          {(failed || cancelled) && (
            <div className="mt-4 flex flex-wrap gap-3">
              <LinkButton href={`/books/${bookId}/llm-config`} variant="outline">
                Back to LLM Configuration
              </LinkButton>
              <LinkButton href={`/books/${bookId}/jobs`} variant="outline">
                View Jobs
              </LinkButton>
            </div>
          )}
        </Card>
      </PageContainer>
    </WorkflowShell>
  );
}

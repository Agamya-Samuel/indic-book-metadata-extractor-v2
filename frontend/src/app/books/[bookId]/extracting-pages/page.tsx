"use client";

import { useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getBook } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobProgress } from "@/hooks/use-job-progress";
import { toast } from "sonner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import JobProgressCard from "@/components/shared/job-progress-card";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function ExtractingPagesPage() {
  useDocumentTitle("Extracting pages");
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
    jobType: "page_extraction",
    jobId,
    enabled: !!bookId,
  });

  useEffect(() => {
    if (!progress.isComplete) return;
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
    const timer = setTimeout(() => {
      router.replace(`/books/${bookId}/preprocessing`);
    }, 800);
    return () => clearTimeout(timer);
  }, [progress.isComplete, bookId, queryClient, router]);

  useEffect(() => {
    if (progress.isFailed) {
      toast.error(progress.errorLog || "Page extraction failed");
    }
  }, [progress.isFailed, progress.errorLog]);

  if (isLoadingBook || progress.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <Spinner className="h-12 w-12 border-[3px] text-[var(--accent)]" />
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
            description="No page extraction job is running for this book."
          />
          <EmptyState
            title="Nothing to extract"
            description="Choose the pages you want to process, then confirm the selection."
          />
          <div className="mt-4">
            <LinkButton href={`/books/${bookId}/select-pages`}>
              Select pages
            </LinkButton>
          </div>
        </PageContainer>
      </WorkflowShell>
    );
  }

  return (
    <WorkflowShell bookId={bookId}>
      <PageContainer>
        <PageHeader
          eyebrow={getLanguageName(book.language)}
          title={book.title || book.filename}
          description="Rendering the selected PDF pages into images. You can cancel at any time."
        />

        <Card>
          <JobProgressCard
            title="Extracting pages"
            progress={progress.progress}
            status={progress.job?.status ?? "queued"}
            phase="Rendering selected PDF pages"
            itemLabel={`${Math.round(progress.progress)}% of selected pages rendered`}
            elapsedMs={progress.elapsedMs}
            error={progress.errorLog}
            onCancel={progress.cancel}
            cancelling={progress.cancelling}
            onRetry={() => router.push(`/books/${bookId}/select-pages`)}
          />

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <LinkButton
              href={`/books/${bookId}/select-pages`}
              variant="outline"
            >
              Back to page selection
            </LinkButton>
            {progress.isComplete && (
              <Button
                onClick={() =>
                  router.replace(`/books/${bookId}/preprocessing`)
                }
              >
                Continue to preprocessing
              </Button>
            )}
          </div>
        </Card>
      </PageContainer>
    </WorkflowShell>
  );
}
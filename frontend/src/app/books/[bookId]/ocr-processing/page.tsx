"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getBook, getBookPages } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobProgress } from "@/hooks/use-job-progress";
import { useSSE } from "@/hooks/use-sse";
import { toast } from "sonner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { PageContainer } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function OcrProcessingPage() {
  useDocumentTitle("Processing OCR");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: pages } = useQuery({
    queryKey: ["book", bookId, "pages"],
    queryFn: () => getBookPages(bookId),
    enabled: !!bookId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const pageCount = pages?.length ?? 0;

  const {
    job,
    isComplete,
    isFailed,
    isCancelled,
    progress,
    isPolling,
    errorLog,
    cancel,
    cancelling,
  } = useJobProgress({
    bookId,
    jobType: "ocr",
    enabled: true,
  });

  // Use SSE for real-time updates (with fallback to polling)
  useSSE({
    bookId,
    enabled: true,
    onJobComplete: (jobId, jobType) => {
      if (jobType === "ocr") {
        toast.success("OCR completed successfully");
      }
    },
    onJobFailed: (jobId, jobType, error) => {
      if (jobType === "ocr") {
        toast.error(`OCR failed: ${error}`);
      }
    },
  });

  useEffect(() => {
    if (isComplete) {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      // Small delay to allow SSE to update cache
      setTimeout(() => {
        router.push(`/books/${bookId}/ocr-review`);
      }, 500);
    }
  }, [isComplete, bookId, router, queryClient]);

  if (isLoadingBook) {
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

  return (
    <WorkflowShell bookId={bookId}>
      <div className="flex min-h-[calc(100dvh-var(--nav-height))] flex-col bg-[var(--background)]">

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-md mx-auto">
          {isPolling && !isComplete && !isFailed && (
            <>
              <div className="mb-6">
                <Spinner className="h-16 w-16 border-[3px] text-[var(--accent-text)] mx-auto" />
              </div>
              <h2 className="text-[length:var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                Running OCR
              </h2>
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mb-6">
                Processing {pageCount} page{pageCount !== 1 ? "s" : ""} from{" "}
                <span className="font-medium">{book.title || book.filename}</span>
              </p>
              <div className="mb-4">
                <Progress value={progress} />
              </div>
              <p className="text-[length:var(--text-xs)] text-[var(--text-muted)] tabular-nums">
                {Math.round(progress)}% complete
              </p>
              {job && (
                <div className="mt-6 flex justify-center">
                  <Button
                    variant="outline"
                    onClick={() => void cancel()}
                    loading={cancelling}
                    disabled={cancelling}
                  >
                    Cancel OCR
                  </Button>
                </div>
              )}
            </>
          )}

          {isComplete && (
            <>
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-[var(--success-600)] flex items-center justify-center animate-success-glow">
                  <svg
                    className="w-8 h-8 text-[var(--text-inverse)] animate-step-check"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              </div>
              <h2 className="text-[length:var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                OCR Complete
              </h2>
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mb-6">
                All {pageCount} page{pageCount !== 1 ? "s" : ""} processed successfully.
                You can now review and correct the OCR text.
              </p>
              {errorLog && (
                <div className="mb-6 text-left bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/20 border border-[var(--warning-500)]/30 rounded-[var(--radius-lg)] p-4">
                  <p className="text-[length:var(--text-sm)] font-medium text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                    Some pages could not be read
                  </p>
                  <pre className="mt-2 text-[length:var(--text-xs)] text-[var(--warning-700)] dark:text-[var(--warning-100)] whitespace-pre-wrap font-mono">
                    {errorLog}
                  </pre>
                </div>
              )}
              <Button onClick={() => router.push(`/books/${bookId}/ocr-review`)}>
                Review OCR Text
              </Button>
            </>
          )}

          {isFailed && (
            <>
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-[var(--danger-600)] flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-[var(--text-inverse)]"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                    />
                  </svg>
                </div>
              </div>
              <h2 className="text-[length:var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                OCR Failed
              </h2>
              {errorLog && (
                <div className="mb-6 text-left bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-4">
                  <pre className="text-[length:var(--text-xs)] text-[var(--danger-700)] dark:text-[var(--danger-100)] whitespace-pre-wrap font-mono">
                    {errorLog}
                  </pre>
                </div>
              )}
              <div className="flex gap-3 justify-center">
                <LinkButton
                  href={`/books/${bookId}/preprocessing`}
                  variant="outline"
                >
                  Back to Preprocessing
                </LinkButton>
              </div>
            </>
          )}

          {isCancelled && (
            <>
              <h2 className="text-[length:var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                OCR Cancelled
              </h2>
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mb-6">
                This OCR run was cancelled. Pages that finished before the
                cancel keep their text.
              </p>
              <div className="flex flex-wrap gap-3 justify-center">
                <LinkButton
                  href={`/books/${bookId}/preprocessing`}
                  variant="outline"
                >
                  Back to Preprocessing
                </LinkButton>
                <LinkButton href={`/books/${bookId}/ocr-review`} variant="outline">
                  Review available text
                </LinkButton>
              </div>
            </>
          )}

          {!job && !isPolling && !isComplete && !isFailed && !isCancelled && (
            <>
              <h2 className="text-[length:var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                No OCR run found
              </h2>
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mb-6">
                Start OCR from the preprocessing step to read this book.
              </p>
              <LinkButton href={`/books/${bookId}/preprocessing`}>
                Back to Preprocessing
              </LinkButton>
            </>
          )}
        </div>
      </div>

      <div className="border-t border-[var(--border)] bg-[var(--surface)]">
        <PageContainer className="!py-4">
          <div className="flex items-center justify-between text-[length:var(--text-sm)] text-[var(--text-muted)]">
            <div className="flex items-center gap-4">
              <span>
                {book.title || book.filename}
              </span>
              <span className="text-[var(--border-strong)]">&bull;</span>
              <span>{getLanguageName(book.language)}</span>
              <span className="text-[var(--border-strong)]">&bull;</span>
              <span>{pageCount} pages</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 bg-[var(--accent-soft)] text-[var(--accent-soft-text)] rounded-[var(--radius)] text-[length:var(--text-xs)] font-medium">
                {isComplete
                  ? "OCR complete"
                  : isFailed
                    ? "OCR failed"
                    : isCancelled
                      ? "OCR cancelled"
                      : "OCR processing"}
              </span>
            </div>
          </div>
        </PageContainer>
      </div>
      </div>
    </WorkflowShell>
  );
}

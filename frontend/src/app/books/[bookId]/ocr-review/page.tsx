"use client";

import { useState, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  getOcrResult,
  updateOcrCorrection,
  getPageImageUrl,
  type OcrResultResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import BoundingBoxCanvas from "@/components/ocr/bounding-box-canvas";
import OcrTextEditor from "@/components/ocr/text-editor";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { OcrReviewSkeleton } from "@/components/shared/skeleton";
import { PageContainer, Card } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

export default function OcrReviewPage() {
  useDocumentTitle("OCR review");
  const params = useParams();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;
  const jobId = searchParams.get("jobId");

  useWorkflowHydration(bookId);
  const { currentStep, completedStep } = useWorkflowStore();

  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const [selectedWordIndex, setSelectedWordIndex] = useState<number | undefined>(undefined);

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: pages, isLoading: isLoadingPages } = useQuery({
    queryKey: ["book", bookId, "pages"],
    queryFn: () => getBookPages(bookId),
    enabled: !!bookId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { isComplete, isFailed, progress, isPolling, errorLog } = useJobPolling({
    bookId,
    jobId: jobId ?? undefined,
    enabled: !!jobId,
  });

  const currentPage = pages?.[currentPageIndex];

  const { data: ocrResult, isLoading: isLoadingOcr } = useQuery({
    queryKey: ["ocr", currentPage?.id],
    queryFn: () => getOcrResult(currentPage!.id),
    enabled: !!currentPage?.id && (!jobId || isComplete || isFailed || !isPolling),
    retry: 1,
    staleTime: 0,
    gcTime: 2 * 60 * 1000,
  });

  const saveMutation = useMutation({
    mutationFn: async ({ pageId, text }: { pageId: string; text: string }) => {
      return updateOcrCorrection(pageId, text);
    },
    onSuccess: async (result: OcrResultResponse) => {
      queryClient.setQueryData(["ocr", currentPage?.id], result);
      // Invalidate the cached query so a page refresh re-fetches the latest
      // state from the DB and avoids showing a stale `corrected_text`.
      await queryClient.invalidateQueries({ queryKey: ["ocr", currentPage?.id] });
      toast.success("OCR correction saved");
    },
  });

  const handleSave = useCallback(
    (correctedText: string) => {
      if (!currentPage) return;
      saveMutation.mutate({ pageId: currentPage.id, text: correctedText });
    },
    [currentPage, saveMutation]
  );

  const handleBoxClick = useCallback((index: number) => {
    setSelectedWordIndex(index);
  }, []);

  const handleWordClick = useCallback((index: number) => {
    setSelectedWordIndex(index);
  }, []);

  const handlePrevPage = useCallback(() => {
    setCurrentPageIndex((prev) => Math.max(0, prev - 1));
    setSelectedWordIndex(undefined);
  }, []);

  const handleNextPage = useCallback(() => {
    if (!pages) return;
    setCurrentPageIndex((prev) => Math.min(pages.length - 1, prev + 1));
    setSelectedWordIndex(undefined);
  }, [pages]);

  const handlePageSelect = useCallback((idx: number) => {
    setCurrentPageIndex(idx);
    setSelectedWordIndex(undefined);
  }, []);

  const getCachedOcrForPage = (pageId: string): OcrResultResponse | undefined => {
    return queryClient.getQueryData(["ocr", pageId]);
  };

  if (isLoadingBook || isLoadingPages) {
    return <OcrReviewSkeleton />;
  }

  if (!book || !pages || pages.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState
          title="No pages found for this book"
          description="Select pages first before running OCR."
          action={
            <LinkButton href={`/books/${bookId}/select-pages`}>
              Go to Page Selection
            </LinkButton>
          }
        />
      </div>
    );
  }

  const showPollingOverlay = isPolling && !ocrResult;

  return (
    <div className="h-screen bg-[var(--background)] flex flex-col overflow-hidden">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 4 ? 4 : currentStep} completedStep={completedStep} />

      <div className="border-b border-[var(--border)] bg-[var(--surface)]">
        <PageContainer className="!py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-[var(--text-xl)] font-bold text-[var(--text)]">OCR Review</h1>
              <p className="text-[var(--text-sm)] text-[var(--text-muted)]">
                {book.title || book.filename} &bull;{" "}
                {getLanguageName(book.language)}
              </p>
            </div>

            <div className="flex items-center gap-4">
              {ocrResult && (
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-2 py-1 text-[var(--text-xs)] rounded-[var(--radius)] font-medium",
                      (ocrResult.confidence ?? 0) >= 80
                        ? "bg-[var(--success-50)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]"
                        : (ocrResult.confidence ?? 0) >= 60
                          ? "bg-[var(--warning-50)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]"
                          : "bg-[var(--danger-50)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]"
                    )}
                  >
                    Avg: {Math.round(ocrResult.confidence ?? 0)}%
                  </span>
                  {ocrResult.language_detected && (
                    <span className="px-2 py-1 text-[var(--text-xs)] bg-[var(--surface-sunken)] text-[var(--text-muted)] rounded-[var(--radius)]">
                      {ocrResult.language_detected}
                    </span>
                  )}
                </div>
              )}

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrevPage}
                  disabled={currentPageIndex === 0}
                >
                  Previous
                </Button>
                <span className="text-[var(--text-sm)] text-[var(--text-muted)] min-w-[80px] text-center tabular-nums">
                  Page {currentPageIndex + 1} of {pages.length}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={currentPageIndex === pages.length - 1}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        </PageContainer>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        {showPollingOverlay ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center max-w-md">
              <Spinner className="h-12 w-12 border-[3px] text-[var(--accent)] mx-auto mb-4" />
              <p className="text-[var(--text)] font-medium">Running OCR...</p>
              <p className="text-[var(--text-muted)] text-[var(--text-sm)] mt-1">
                {Math.round(progress)}% complete
              </p>
              <div className="w-64 mx-auto mt-3">
                <Progress value={progress} />
              </div>
              {isFailed && errorLog && (
                <div className="mt-4">
                  <ErrorState
                    title="OCR Failed"
                    description={errorLog}
                  />
                </div>
              )}
            </div>
          </div>
        ) : isLoadingOcr ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center">
              <Spinner className="h-8 w-8 border-2 text-[var(--accent)] mx-auto mb-3" />
              <p className="text-[var(--text-muted)] text-[var(--text-sm)]">Loading OCR results...</p>
            </div>
          </div>
        ) : ocrResult ? (
          <>
            <div className="w-full lg:w-[60%] p-4 overflow-hidden min-h-0">
              <Card>
                <BoundingBoxCanvas
                  imageUrl={getPageImageUrl(currentPage!.id)}
                  boxes={ocrResult.bounding_boxes ?? []}
                  selectedIndex={selectedWordIndex}
                  onBoxClick={handleBoxClick}
                  highlightLowConfidence={true}
                  lowConfidenceThreshold={60}
                />
              </Card>
            </div>

            <div className="w-full lg:w-[40%] border-l border-[var(--border)] bg-[var(--surface)] flex flex-col min-h-0">
              <OcrTextEditor
                words={ocrResult.bounding_boxes ?? []}
                rawText={ocrResult.raw_text}
                correctedText={ocrResult.corrected_text}
                selectedIndex={selectedWordIndex}
                onWordClick={handleWordClick}
                onSave={handleSave}
                isSaving={saveMutation.isPending}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center">
              <ErrorState
                title="No OCR results for this page"
                description="Run OCR from the Preprocessing step to generate text."
                action={
                  <LinkButton href={`/books/${bookId}/preprocessing`}>
                    Run OCR from Preprocessing
                  </LinkButton>
                }
              />
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-[var(--border)] bg-[var(--surface)]">
        <PageContainer className="!py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 overflow-x-auto flex-1 min-w-0">
              {pages.map((page, idx) => {
                const hasOcr = !!getCachedOcrForPage(page.id);
                return (
                  <Button
                    key={page.id}
                    size="sm"
                    variant={idx === currentPageIndex ? "primary" : "ghost"}
                    onClick={() => handlePageSelect(idx)}
                    aria-label={`Go to page ${page.page_number}`}
                    title={`Page ${page.page_number}${hasOcr ? " (OCR loaded)" : ""}`}
                    className={cn(
                      "shrink-0",
                      idx === currentPageIndex
                        ? ""
                        : hasOcr
                          ? "text-[var(--success-700)] dark:text-[var(--success-100)]"
                          : ""
                    )}
                  >
                    {page.page_number}
                  </Button>
                );
              })}
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <LinkButton
                href={`/books/${bookId}/preprocessing`}
                variant="outline"
                size="sm"
              >
                Back to Preprocessing
              </LinkButton>
              <LinkButton
                href={`/books/${bookId}/llm-config`}
                variant="primary"
                size="sm"
              >
                Proceed to LLM Config
              </LinkButton>
            </div>
          </div>
        </PageContainer>
      </div>
    </div>
  );
}

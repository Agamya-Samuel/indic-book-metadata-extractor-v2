"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import {
  getBook,
  getBookPages,
  getOcrResult,
  updateOcrCorrection,
  getPageImageUrl,
  getThumbnailUrl,
  type OcrResultResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { getErrorMessage } from "@/lib/error-handler";
import { useJobPolling } from "@/hooks/use-job-polling";
import BoundingBoxCanvas from "@/components/ocr/bounding-box-canvas";
import OcrTextEditor from "@/components/ocr/text-editor";
import { toast } from "sonner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { OcrReviewSkeleton } from "@/components/shared/skeleton";
import { PageContainer, Card } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { Toolbar, ToolbarGroup } from "@/components/shared/toolbar";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import {
  useUnsavedChanges,
  confirmDiscard,
} from "@/hooks/use-unsaved-changes";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";

export default function OcrReviewPage() {
  useDocumentTitle("OCR review");
  const params = useParams();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;
  const jobId = searchParams.get("jobId");

  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const [selectedWordIndex, setSelectedWordIndex] = useState<number | undefined>(undefined);
  const [editorDirty, setEditorDirty] = useState(false);
  const [filmstripOpen, setFilmstripOpen] = useState(true);
  const filmstripRef = useRef<HTMLDivElement>(null);

  useUnsavedChanges(editorDirty);

  // Keep the page being reviewed in view as the reviewer pages through.
  useEffect(() => {
    const container = filmstripRef.current;
    if (!container) return;
    container
      .querySelector<HTMLElement>(`[data-page-index="${currentPageIndex}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [currentPageIndex]);

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
    onMutate: async ({ pageId, text }) => {
      await queryClient.cancelQueries({ queryKey: ["ocr", pageId] });
      const previous = queryClient.getQueryData<OcrResultResponse>(["ocr", pageId]);
      if (previous) {
        queryClient.setQueryData<OcrResultResponse>(["ocr", pageId], {
          ...previous,
          corrected_text: text,
        });
      }
      return { pageId, previous };
    },
    onSuccess: (result, { pageId }) => {
      queryClient.setQueryData(["ocr", pageId], result);
      toast.success("OCR correction saved");
    },
    onError: (err, { pageId }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["ocr", pageId], context.previous);
      }
      toast.error(`Could not save corrections: ${getErrorMessage(err)}`);
    },
    onSettled: (_result, _error, { pageId }) => {
      void queryClient.invalidateQueries({ queryKey: ["ocr", pageId] });
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

  const canLeavePage = useCallback(() => {
    if (!editorDirty) return true;
    if (!confirmDiscard()) return false;
    setEditorDirty(false);
    return true;
  }, [editorDirty]);

  const handlePrevPage = useCallback(() => {
    if (!canLeavePage()) return;
    setCurrentPageIndex((prev) => Math.max(0, prev - 1));
    setSelectedWordIndex(undefined);
  }, [canLeavePage]);

  const handleNextPage = useCallback(() => {
    if (!pages) return;
    if (!canLeavePage()) return;
    setCurrentPageIndex((prev) => Math.min(pages.length - 1, prev + 1));
    setSelectedWordIndex(undefined);
  }, [pages, canLeavePage]);

  const handlePageSelect = useCallback(
    (idx: number) => {
      if (!canLeavePage()) return;
      setCurrentPageIndex(idx);
      setSelectedWordIndex(undefined);
    },
    [canLeavePage],
  );

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
    <WorkflowShell bookId={bookId}>
      <div className="flex h-[calc(100dvh-var(--nav-height))] flex-col overflow-hidden bg-[var(--background)]">

      <div className="border-b border-[var(--border)] bg-[var(--surface)]">
        <PageContainer className="!py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-[length:var(--text-2xl)] font-semibold tracking-tight text-[var(--text)]">OCR Review</h1>
              <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                {book.title || book.filename} &bull;{" "}
                {getLanguageName(book.language)}
              </p>
            </div>

            <div className="flex items-center gap-4">
              {ocrResult && (
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-2 py-1 text-[length:var(--text-xs)] rounded-[var(--radius)] font-medium",
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
                    <span className="px-2 py-1 text-[length:var(--text-xs)] bg-[var(--surface-sunken)] text-[var(--text-muted)] rounded-[var(--radius)]">
                      {ocrResult.language_detected}
                    </span>
                  )}
                </div>
              )}

            </div>
          </div>
        </PageContainer>
      </div>

      <div className="px-3 pt-3">
        <Toolbar>
          <ToolbarGroup>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFilmstripOpen((open) => !open)}
              aria-pressed={filmstripOpen}
            >
              Pages
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrevPage}
              disabled={currentPageIndex === 0}
            >
              Previous
            </Button>
            <span className="min-w-[80px] text-center text-[length:var(--text-sm)] tabular-nums text-[var(--text-muted)]">
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
          </ToolbarGroup>
          <ToolbarGroup align="end">
            <LinkButton
              href={`/books/${bookId}/preprocessing`}
              variant="outline"
              size="sm"
            >
              Back to Preprocessing
            </LinkButton>
            <LinkButton href={`/books/${bookId}/llm-config`} size="sm">
              Proceed to LLM Config
            </LinkButton>
          </ToolbarGroup>
        </Toolbar>
      </div>

      <div className="flex-1 flex min-h-0">
        {filmstripOpen && !showPollingOverlay && (
          <div
            ref={filmstripRef}
            className="hidden w-28 shrink-0 overflow-y-auto border-r border-[var(--border)] bg-[var(--surface)] p-2 lg:block"
          >
            <div className="flex flex-col gap-2">
              {pages.map((page, idx) => {
                const hasOcr = !!getCachedOcrForPage(page.id);
                return (
                  <button
                    key={page.id}
                    type="button"
                    data-page-index={idx}
                    onClick={() => handlePageSelect(idx)}
                    aria-label={`Go to page ${page.page_number}${hasOcr ? ", OCR loaded" : ""}`}
                    aria-current={idx === currentPageIndex ? "true" : undefined}
                    className={cn(
                      "relative aspect-[3/4] overflow-hidden rounded-[var(--radius)] border-2 transition-colors",
                      focusRing,
                      idx === currentPageIndex
                        ? "border-[var(--accent-ring)]"
                        : "border-[var(--border)] hover:border-[var(--border-strong)]",
                    )}
                  >
                    <Image
                      src={getThumbnailUrl(bookId, page.page_number)}
                      alt=""
                      fill
                      sizes="7rem"
                      className="object-cover"
                      unoptimized
                    />
                    <span className="absolute inset-x-0 bottom-0 bg-[var(--neutral-1000)]/70 py-0.5 text-center text-[10px] font-medium text-[var(--text-inverse)]">
                      {page.page_number}
                    </span>
                    {hasOcr && (
                      <span
                        aria-hidden="true"
                        className="absolute right-1 top-1 size-2 rounded-full bg-[var(--success-600)]"
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {showPollingOverlay ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center max-w-md">
              <Spinner className="h-12 w-12 border-[3px] text-[var(--accent-text)] mx-auto mb-4" />
              <p className="text-[var(--text)] font-medium">Running OCR...</p>
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mt-1">
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
              <Spinner className="h-8 w-8 border-2 text-[var(--accent-text)] mx-auto mb-3" />
              <p className="text-[var(--text-muted)] text-[length:var(--text-sm)]">Loading OCR results...</p>
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
                key={currentPage!.id}
                words={ocrResult.bounding_boxes ?? []}
                rawText={ocrResult.raw_text}
                correctedText={ocrResult.corrected_text}
                selectedIndex={selectedWordIndex}
                onWordClick={handleWordClick}
                onSave={handleSave}
                isSaving={saveMutation.isPending}
                onDirtyChange={setEditorDirty}
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
      </div>
      </div>
    </WorkflowShell>
  );
}

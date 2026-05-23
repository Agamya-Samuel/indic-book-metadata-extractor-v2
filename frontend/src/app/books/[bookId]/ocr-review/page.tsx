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
import { useJobPolling } from "@/hooks/use-job-polling";
import BoundingBoxCanvas from "@/components/ocr/bounding-box-canvas";
import OcrTextEditor from "@/components/ocr/text-editor";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { OcrReviewSkeleton } from "@/components/shared/skeleton";

export default function OcrReviewPage() {
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
    onSuccess: (result: OcrResultResponse) => {
      queryClient.setQueryData(["ocr", currentPage?.id], result);
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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <p className="text-gray-600 dark:text-gray-400 mb-4">No pages found for this book.</p>
          <a
            href={`/books/${bookId}/select-pages`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Go to Page Selection
          </a>
        </div>
      </div>
    );
  }

  const showPollingOverlay = isPolling && !ocrResult;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 4 ? 4 : currentStep} completedStep={completedStep} />

      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">OCR Review</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {book.title || book.filename} &bull;{" "}
              {book.language === "tel" ? "Telugu" : "Hindi"}
            </p>
          </div>

          <div className="flex items-center gap-4">
            {ocrResult && (
              <div className="flex items-center gap-3">
                <span
                  className={`px-2 py-1 text-xs rounded font-medium ${
                    (ocrResult.confidence ?? 0) >= 80
                      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                      : (ocrResult.confidence ?? 0) >= 60
                        ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                  }`}
                >
                  Avg: {Math.round(ocrResult.confidence ?? 0)}%
                </span>
                {ocrResult.language_detected && (
                  <span className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                    {ocrResult.language_detected}
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevPage}
                disabled={currentPageIndex === 0}
                className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600 dark:text-gray-400 min-w-[80px] text-center">
                Page {currentPageIndex + 1} of {pages.length}
              </span>
              <button
                onClick={handleNextPage}
                disabled={currentPageIndex === pages.length - 1}
                className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row">
        {showPollingOverlay ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-blue-400 mx-auto mb-4" />
              <p className="text-gray-700 dark:text-gray-300 font-medium">Running OCR...</p>
              <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                {Math.round(progress)}% complete
              </p>
              <div className="w-64 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-3 mx-auto">
                <div
                  className="bg-blue-600 dark:bg-blue-400 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round(progress)}%` }}
                />
              </div>
              {isFailed && errorLog && (
                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-400 max-w-md">
                  <p className="font-medium">OCR Failed</p>
                  <p className="mt-1">{errorLog}</p>
                </div>
              )}
            </div>
          </div>
        ) : isLoadingOcr ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400 text-sm">Loading OCR results...</p>
            </div>
          </div>
        ) : ocrResult ? (
          <>
            <div className="w-full lg:w-[60%] p-4 overflow-hidden">
              <BoundingBoxCanvas
                imageUrl={getPageImageUrl(currentPage!.id)}
                boxes={ocrResult.bounding_boxes ?? []}
                selectedIndex={selectedWordIndex}
                onBoxClick={handleBoxClick}
                highlightLowConfidence={true}
                lowConfidenceThreshold={60}
              />
            </div>

            <div className="w-full lg:w-[40%] border-l dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col">
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
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 dark:text-gray-400 mb-2">No OCR results for this page.</p>
              <a
                href={`/books/${bookId}/preprocessing`}
                className="text-blue-600 dark:text-blue-400 hover:underline text-sm"
              >
                Run OCR from Preprocessing
              </a>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 border-t dark:border-gray-700 px-6 py-3">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            {pages.map((page, idx) => {
              const hasOcr = !!getCachedOcrForPage(page.id);
              return (
                <PageButton
                  key={page.id}
                  pageNumber={page.page_number}
                  isActive={idx === currentPageIndex}
                  hasOcr={hasOcr}
                  onSelect={() => handlePageSelect(idx)}
                />
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <a
              href={`/books/${bookId}/preprocessing`}
              className="px-4 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition-colors"
            >
              Back to Preprocessing
            </a>
            <a
              href={`/books/${bookId}/llm-config`}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 dark:hover:bg-blue-500 transition-colors"
            >
              Proceed to LLM Config
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

function PageButton({
  pageNumber,
  isActive,
  hasOcr,
  onSelect,
}: {
  pageNumber: number;
  isActive: boolean;
  hasOcr: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-8 h-8 text-xs rounded border transition-colors ${
        isActive
          ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-medium"
          : hasOcr
            ? "border-green-300 bg-green-50 text-green-700 dark:border-green-700 dark:bg-green-900/30 dark:text-green-400"
            : "border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
      }`}
      title={`Page ${pageNumber}${hasOcr ? " (OCR loaded)" : ""}`}
    >
      {pageNumber}
    </button>
  );
}

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
  });

  const { data: pages, isLoading: isLoadingPages } = useQuery({
    queryKey: ["book", bookId, "pages"],
    queryFn: () => getBookPages(bookId),
    enabled: !!bookId,
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
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!book || !pages || pages.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-4">No pages found for this book.</p>
          <a
            href={`/books/${bookId}/select-pages`}
            className="text-blue-600 hover:underline"
          >
            Go to Page Selection
          </a>
        </div>
      </div>
    );
  }

  const showPollingOverlay = isPolling && !ocrResult;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 4 ? 4 : currentStep} completedStep={completedStep} />

      <div className="bg-white border-b px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">OCR Review</h1>
            <p className="text-sm text-gray-500">
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
                      ? "bg-green-100 text-green-700"
                      : (ocrResult.confidence ?? 0) >= 60
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-red-100 text-red-700"
                  }`}
                >
                  Avg: {Math.round(ocrResult.confidence ?? 0)}%
                </span>
                {ocrResult.language_detected && (
                  <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                    {ocrResult.language_detected}
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevPage}
                disabled={currentPageIndex === 0}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600 min-w-[80px] text-center">
                Page {currentPageIndex + 1} of {pages.length}
              </span>
              <button
                onClick={handleNextPage}
                disabled={currentPageIndex === pages.length - 1}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex">
        {showPollingOverlay ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
              <p className="text-gray-700 font-medium">Running OCR...</p>
              <p className="text-gray-500 text-sm mt-1">
                {Math.round(progress)}% complete
              </p>
              <div className="w-64 bg-gray-200 rounded-full h-2 mt-3 mx-auto">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round(progress)}%` }}
                />
              </div>
              {isFailed && errorLog && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700 max-w-md">
                  <p className="font-medium">OCR Failed</p>
                  <p className="mt-1">{errorLog}</p>
                </div>
              )}
            </div>
          </div>
        ) : isLoadingOcr ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">Loading OCR results...</p>
            </div>
          </div>
        ) : ocrResult ? (
          <>
            <div className="w-[60%] p-4 overflow-hidden">
              <BoundingBoxCanvas
                imageUrl={getPageImageUrl(currentPage!.id)}
                boxes={ocrResult.bounding_boxes ?? []}
                selectedIndex={selectedWordIndex}
                onBoxClick={handleBoxClick}
                highlightLowConfidence={true}
                lowConfidenceThreshold={60}
              />
            </div>

            <div className="w-[40%] border-l bg-white flex flex-col">
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
              <p className="text-gray-600 mb-2">No OCR results for this page.</p>
              <a
                href={`/books/${bookId}/preprocessing`}
                className="text-blue-600 hover:underline text-sm"
              >
                Run OCR from Preprocessing
              </a>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border-t px-6 py-3">
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
              className="px-4 py-2 text-sm border rounded hover:bg-gray-50 transition-colors"
            >
              Back to Preprocessing
            </a>
            <a
              href={`/books/${bookId}/llm-config`}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
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
          ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
          : hasOcr
            ? "border-green-300 bg-green-50 text-green-700"
            : "border-gray-200 text-gray-500 hover:bg-gray-100"
      }`}
      title={`Page ${pageNumber}${hasOcr ? " (OCR loaded)" : ""}`}
    >
      {pageNumber}
    </button>
  );
}

"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  getOcrResult,
  getPageImageUrl,
  getMetadata,
  updateMetadata,
  getMetadataFieldDefinitions,
  getLlmRuns,
  type MetadataResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getErrorMessage } from "@/lib/error-handler";
import BoundingBoxCanvas from "@/components/ocr/bounding-box-canvas";
import MetadataForm from "@/components/metadata/metadata-form";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { MetadataReviewSkeleton } from "@/components/shared/skeleton";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";

export default function MetadataReviewPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  useWorkflowHydration(bookId);
  const { currentStep, completedStep, setStep: setWorkflowStep, setCompletedStep } = useWorkflowStore();

  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const [selectedBoxIndex, setSelectedBoxIndex] = useState<
    number | undefined
  >(undefined);
  const [showLlmHistory, setShowLlmHistory] = useState(false);

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

  const { data: metadata, isLoading: isLoadingMetadata } = useQuery({
    queryKey: ["metadata", bookId],
    queryFn: () => getMetadata(bookId),
    enabled: !!bookId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: fieldDefs, isLoading: isLoadingFields } = useQuery({
    queryKey: ["metadata-fields", bookId],
    queryFn: () => getMetadataFieldDefinitions(bookId),
    enabled: !!bookId,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const { data: llmRuns } = useQuery({
    queryKey: ["llm-runs", bookId],
    queryFn: () => getLlmRuns(bookId),
    enabled: !!bookId && showLlmHistory,
  });

  const { isFailed, progress, isPolling, errorLog } =
    useJobPolling({
      bookId,
      enabled: book?.status === "llm_running",
    });

  const currentPage = pages?.[currentPageIndex];

  const { data: ocrResult } = useQuery({
    queryKey: ["ocr", currentPage?.id],
    queryFn: () => getOcrResult(currentPage!.id),
    enabled: !!currentPage?.id,
    retry: 1,
  });

  const saveMutation = useMutation({
    mutationFn: async (
      fields: Record<string, string | Record<string, string>>
    ) => {
      const cleaned: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(fields)) {
        cleaned[k] = v;
      }
      return updateMetadata(bookId, cleaned as Record<string, string>);
    },
    onSuccess: (result: MetadataResponse) => {
      queryClient.setQueryData(["metadata", bookId], result);
      toast.success("Metadata saved successfully");
      setWorkflowStep(7);
      setCompletedStep(7);
    },
    onError: (err) => {
      toast.error(`Failed to save metadata: ${getErrorMessage(err)}`);
    },
  });

  const handleSave = useCallback(
    (fields: Record<string, string | Record<string, string>>) => {
      saveMutation.mutate(fields);
    },
    [saveMutation]
  );

  const handleCopyText = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
  }, []);

  if (isLoadingBook || isLoadingPages || isLoadingMetadata || isLoadingFields) {
    return <MetadataReviewSkeleton />;
  }

  if (!book) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <p className="text-gray-600 dark:text-gray-400">Book not found.</p>
      </div>
    );
  }

  if (isPolling) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center max-w-md mx-auto">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
            LLM Extraction in Progress
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
            {Math.round(progress)}% complete
          </p>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-4">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.round(progress)}%` }}
            />
          </div>
          {isFailed && errorLog && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-400">
              <p className="font-medium">Extraction Failed</p>
              <p className="mt-1">{errorLog}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  const metadataValues = metadata?.fields ?? {};

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 6 ? 6 : currentStep} completedStep={completedStep} />

      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-4 sm:px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              Metadata Review
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {book.title || book.filename} &bull;{" "}
              {getLanguageName(book.language)} &bull;{" "}
              {Object.keys(metadataValues).length} fields extracted
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowLlmHistory(!showLlmHistory)}
              className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
            >
              {showLlmHistory ? "Hide" : "Show"} LLM History
            </button>
            <a
              href={`/books/${bookId}/llm-config`}
              className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
            >
              Back to LLM Config
            </a>
          </div>
        </div>
      </div>

      <div className="flex-1 max-w-screen-2xl mx-auto w-full p-4 sm:p-6">
        {showLlmHistory && llmRuns && llmRuns.length > 0 && (
          <div className="mb-6">
            <CollapsibleSection
              title="LLM Run History"
              count={llmRuns.length}
              defaultOpen={true}
            >
              <div className="space-y-3">
                {llmRuns.map((run) => (
                  <div
                    key={run.id}
                    className="border rounded p-3 text-sm dark:border-gray-700"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          {run.model}
                        </span>
                        {run.created_at && (
                          <span className="text-xs text-gray-400 dark:text-gray-500">
                            {new Date(run.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                    {run.prompt_template && (
                      <details className="mt-1">
                        <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                          View prompt
                        </summary>
                        <pre className="mt-1 text-xs bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto whitespace-pre-wrap">
                          {run.prompt_template}
                        </pre>
                      </details>
                    )}
                    {run.parsed_fields && (
                      <details className="mt-1">
                        <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                          View extracted fields ({
                            Object.keys(run.parsed_fields).length
                          })
                        </summary>
                        <div className="mt-1 grid grid-cols-2 gap-1">
                          {Object.entries(run.parsed_fields).map(
                            ([k, v]) => (
                              <div key={k} className="text-xs">
                                <span className="text-gray-500 dark:text-gray-400">{k}:</span>{" "}
                                <span className="text-gray-700 dark:text-gray-300">{v ?? "null"}</span>
                              </div>
                            )
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          </div>
        )}

        {pages && pages.length > 0 && ocrResult && (
          <div className="mb-6 bg-white dark:bg-gray-800 shadow rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Page Image Viewer
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setCurrentPageIndex((prev) => Math.max(0, prev - 1));
                    setSelectedBoxIndex(undefined);
                  }}
                  disabled={currentPageIndex === 0}
                  className="px-3 py-1 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Prev
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400 min-w-[80px] text-center">
                  Page {currentPageIndex + 1} of {pages.length}
                </span>
                <button
                  onClick={() => {
                    setCurrentPageIndex((prev) =>
                      Math.min(pages.length - 1, prev + 1)
                    );
                    setSelectedBoxIndex(undefined);
                  }}
                  disabled={currentPageIndex === pages.length - 1}
                  className="px-3 py-1 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
            <BoundingBoxCanvas
              imageUrl={getPageImageUrl(currentPage!.id)}
              boxes={ocrResult.bounding_boxes ?? []}
              selectedIndex={selectedBoxIndex}
              onBoxClick={(idx) => {
                setSelectedBoxIndex(idx);
                const word = ocrResult.bounding_boxes?.[idx];
                if (word?.text) {
                  handleCopyText(word.text);
                }
              }}
              highlightLowConfidence={true}
              lowConfidenceThreshold={60}
            />
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Click a bounding box to copy its text to clipboard
            </p>
          </div>
        )}

        {fieldDefs && (
          <MetadataForm
            fieldDefinitions={fieldDefs}
            values={metadataValues}
            onSave={handleSave}
            isSaving={saveMutation.isPending}
          />
        )}

        {saveMutation.isError && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
            {getErrorMessage(saveMutation.error)}
          </p>
        )}

        <div className="mt-6 flex items-center gap-3 border-t dark:border-gray-700 pt-4">
          <a
            href={`/books/${bookId}/llm-config`}
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
          >
            Re-run Extraction
          </a>
          <Link
            href="/library"
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
          >
            Go to Library
          </Link>
        </div>
      </div>
    </div>
  );
}

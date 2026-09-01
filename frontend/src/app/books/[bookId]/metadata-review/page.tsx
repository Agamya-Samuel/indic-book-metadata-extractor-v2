"use client";

import { useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  getOcrResult,
  getPageImageUrl,
  getMetadata,
  updateMetadata,
  getMetadataFieldDefinitions,
  getMetadataEvidence,
  getLlmRuns,
  type MetadataResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import { useBookStatus } from "@/hooks/use-book-status";
import { getErrorMessage } from "@/lib/error-handler";
import BoundingBoxCanvas from "@/components/ocr/bounding-box-canvas";
import MetadataForm from "@/components/metadata/metadata-form";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { MetadataReviewSkeleton } from "@/components/shared/skeleton";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, Progress, EmptyState } from "@/components/shared/empty-state";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function MetadataReviewPage() {
  useDocumentTitle("Metadata review");
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

  const { data: fieldEvidence } = useQuery({
    queryKey: ["metadata-evidence", bookId],
    queryFn: () => getMetadataEvidence(bookId),
    enabled: !!bookId,
    staleTime: 30 * 1000,
  });

  const confidenceByField = useMemo(() => {
    const map: Record<string, {
      confidence: number | null;
      extraction_method: string;
      source_page_number: number | null;
      source_text_snippet: string | null;
    }> = {};
    if (fieldEvidence) {
      for (const ev of fieldEvidence) {
        map[ev.field_name] = {
          confidence: ev.confidence,
          extraction_method: ev.extraction_method,
          source_page_number: ev.source_page_number,
          source_text_snippet: ev.source_text_snippet,
        };
      }
    }
    return map;
  }, [fieldEvidence]);

  const { isFailed, progress, isPolling, errorLog } =
    useJobPolling({
      // Poll on any active job state, not only ``llm_running``, so the
      // brief ``llm_running`` → ``awaiting_review`` transition isn't missed.
      bookId,
      enabled:
        book?.status === "llm_running" ||
        book?.status === "ocr_running" ||
        book?.status === "preprocessing",
    });

  const bookStatus = useBookStatus({ bookId });

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
      return updateMetadata(bookId, fields);
    },
    onSuccess: (result: MetadataResponse) => {
      queryClient.setQueryData(["metadata", bookId], result);
      toast.success("Metadata saved successfully");
      // Don't advance the workflow to step 7 from here. The backend
      // transitions the book to ``complete`` after the PUT succeeds;
      // the SSE ``book.status_changed`` event drives the stepper, so
      // a refresh doesn't bounce the user back to step 6.
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
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState title="Book not found" />
      </div>
    );
  }

  if (isPolling) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="text-center max-w-md mx-auto px-4">
          <Spinner className="h-12 w-12 border-[3px] text-[var(--accent)] mx-auto mb-4" />
          <h2 className="text-[var(--text-lg)] font-semibold text-[var(--text)] mb-2">
            LLM Extraction in Progress
          </h2>
          <p className="text-[var(--text-muted)] text-[var(--text-sm)] mb-4">
            {Math.round(progress)}% complete
          </p>
          <div className="mb-4">
            <Progress value={progress} />
          </div>
          {isFailed && errorLog && (
            <ErrorState title="Extraction Failed" description={errorLog} />
          )}
        </div>
      </div>
    );
  }

  const metadataValues = metadata?.fields ?? {};

  return (
    <div className="min-h-screen bg-[var(--background)] flex flex-col">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 6 ? 6 : currentStep} completedStep={completedStep} />

      <PageContainer className="flex-1 flex flex-col">
        <PageHeader
          title="Metadata Review"
          description={
            <>
              {book.title || book.filename} &bull;{" "}
              {getLanguageName(book.language)} &bull;{" "}
              {Object.keys(metadataValues).length} fields extracted
            </>
          }
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => setShowLlmHistory(!showLlmHistory)}
              >
                {showLlmHistory ? "Hide" : "Show"} LLM History
              </Button>
              <LinkButton
                href={`/books/${bookId}/llm-config`}
                variant="outline"
              >
                Back to LLM Config
              </LinkButton>
            </div>
          }
        />

        {bookStatus.isRunning && (
          <Card>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-[var(--text-base)] font-semibold text-[var(--text)]">
                  Auto-processing in progress
                </h2>
                <span className="text-[var(--text-sm)] text-[var(--text-muted)]">
                  {Math.round(bookStatus.progress)}%
                </span>
              </div>
              <Progress value={bookStatus.progress} />
              <p className="text-[var(--text-sm)] text-[var(--text-muted)]">
                Status: <span className="font-mono">{bookStatus.status}</span>
                {bookStatus.connectionMode === "polling" && (
                  <span className="ml-2 text-[var(--warning-700)]">
                    (SSE disconnected — using polling fallback)
                  </span>
                )}
              </p>
            </div>
          </Card>
        )}

        <Stack gap={6}>
          {showLlmHistory && (
            <Card title="LLM Run History" description="Past LLM extraction runs and their outputs.">
              {llmRuns && llmRuns.length > 0 ? (
                <CollapsibleSection
                  title="All Runs"
                  count={llmRuns.length}
                  defaultOpen={true}
                >
                  <Stack gap={3}>
                    {llmRuns.map((run) => (
                      <div
                        key={run.id}
                        className="border border-[var(--border)] rounded-[var(--radius)] p-3 text-[var(--text-sm)]"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-[var(--text)]">
                              {run.model}
                            </span>
                            {run.created_at && (
                              <span className="text-[var(--text-xs)] text-[var(--text-subtle)]">
                                {new Date(run.created_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                        {run.prompt_template && (
                          <details className="mt-1">
                            <summary className="text-[var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                              View prompt
                            </summary>
                            <pre className="mt-1 text-[var(--text-xs)] bg-[var(--surface-sunken)] p-2 rounded-[var(--radius)] overflow-x-auto whitespace-pre-wrap text-[var(--text)]">
                              {run.prompt_template}
                            </pre>
                          </details>
                        )}
                        {run.parsed_fields && (
                          <details className="mt-1">
                            <summary className="text-[var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                              View extracted fields (
                              {Object.keys(run.parsed_fields).length})
                            </summary>
                            <div className="mt-1 grid grid-cols-2 gap-1">
                              {Object.entries(run.parsed_fields).map(
                                ([k, v]) => (
                                  <div key={k} className="text-[var(--text-xs)]">
                                    <span className="text-[var(--text-muted)]">{k}:</span>{" "}
                                    <span className="text-[var(--text)]">{v ?? "null"}</span>
                                  </div>
                                )
                              )}
                            </div>
                          </details>
                        )}
                      </div>
                    ))}
                  </Stack>
                </CollapsibleSection>
              ) : (
                <EmptyState
                  title="No LLM runs yet"
                  description="Past LLM extraction runs will appear here."
                />
              )}
            </Card>
          )}

          {pages && pages.length > 0 && ocrResult && currentPage && (
            <Card
              title="Page Image Viewer"
              description="Click a bounding box to copy its text to clipboard."
              headerAction={
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setCurrentPageIndex((prev) => Math.max(0, prev - 1));
                      setSelectedBoxIndex(undefined);
                    }}
                    disabled={currentPageIndex === 0}
                  >
                    Prev
                  </Button>
                  <span className="text-[var(--text-sm)] text-[var(--text-muted)] min-w-[80px] text-center tabular-nums">
                    Page {currentPageIndex + 1} of {pages.length}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setCurrentPageIndex((prev) =>
                        Math.min(pages.length - 1, prev + 1)
                      );
                      setSelectedBoxIndex(undefined);
                    }}
                    disabled={currentPageIndex === pages.length - 1}
                  >
                    Next
                  </Button>
                </div>
              }
            >
              <BoundingBoxCanvas
                imageUrl={getPageImageUrl(currentPage.id)}
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
            </Card>
          )}

          {fieldDefs && (
            <MetadataForm
              fieldDefinitions={fieldDefs}
              values={metadataValues}
              onSave={handleSave}
              isSaving={saveMutation.isPending}
              confidenceByField={confidenceByField}
            />
          )}

          {saveMutation.isError && (
            <ErrorState
              title="Failed to save metadata"
              description={getErrorMessage(saveMutation.error)}
            />
          )}

          <div className="flex items-center gap-3 border-t border-[var(--border)] pt-4">
            <LinkButton
              href={`/books/${bookId}/llm-config`}
              variant="outline"
            >
              Re-run Extraction
            </LinkButton>
            <LinkButton href="/library" variant="outline">
              Go to Library
            </LinkButton>
          </div>
        </Stack>
      </PageContainer>
    </div>
  );
}

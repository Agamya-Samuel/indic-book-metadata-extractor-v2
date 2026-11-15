"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getMetadata,
  updateMetadata,
  getAllMetadataFieldDefinitions,
  getAllMetadataEvidence,
  getLlmRuns,
  completeReview,
  type MetadataResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import { useBookStatus } from "@/hooks/use-book-status";
import { useOcrCorpus } from "@/hooks/use-ocr-corpus";
import { getErrorMessage } from "@/lib/error-handler";
import MetadataForm, {
  type MetadataFormActions,
  type MetadataFormStats,
} from "@/components/metadata/metadata-form";
import OcrReferencePane from "@/components/metadata/ocr-reference-pane";
import ReviewWorkspace from "@/components/metadata/review-workspace";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { MetadataReviewSkeleton } from "@/components/shared/skeleton";
import { toast } from "sonner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { WorkflowNav } from "@/components/shared/workflow-nav";
import { ErrorState, Progress, EmptyState } from "@/components/shared/empty-state";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import SaveBar from "@/components/shared/save-bar";
import { Spinner } from "@/components/shared/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import Pagination from "@/components/shared/pagination";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";

const EMPTY_STATS: MetadataFormStats = { dirty: 0, missing: 0, uncertain: 0 };

function isBelowDesktop(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(max-width: 1023.98px)").matches;
}

export default function MetadataReviewPage() {
  useDocumentTitle("Metadata review");
  const params = useParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const [focusedField, setFocusedField] = useState<string | undefined>(
    undefined,
  );
  const [showLlmHistory, setShowLlmHistory] = useState(false);
  const [confirmCompleteOpen, setConfirmCompleteOpen] = useState(false);
  const [runsPage, setRunsPage] = useState(1);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [paneOpened, setPaneOpened] = useState(
    () =>
      typeof window !== "undefined" &&
      !!window.matchMedia &&
      window.matchMedia("(min-width: 1024px)").matches,
  );
  const [formStats, setFormStats] = useState<MetadataFormStats>(EMPTY_STATS);
  const [panePage, setPanePage] = useState<number | null>(null);
  const formActionsRef = useRef<MetadataFormActions | null>(null);

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
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
    queryKey: ["metadata-fields", bookId, "all"],
    queryFn: () => getAllMetadataFieldDefinitions(bookId),
    enabled: !!bookId,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const { data: llmRuns } = useQuery({
    queryKey: ["llm-runs", bookId, runsPage],
    queryFn: () =>
      getLlmRuns(bookId, { page: runsPage, page_size: DEFAULT_PAGE_SIZE }),
    enabled: !!bookId && showLlmHistory,
  });

  const { data: fieldEvidence } = useQuery({
    queryKey: ["metadata-evidence", bookId, "all"],
    queryFn: () => getAllMetadataEvidence(bookId),
    enabled: !!bookId,
    staleTime: 30 * 1000,
  });

  const corpusQuery = useOcrCorpus(bookId, paneOpened);

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
        book?.status === "llm_running" || book?.status === "ocr_running",
    });

  const bookStatus = useBookStatus({ bookId });

  const saveMutation = useMutation({
    mutationFn: async (
      fields: Record<string, string | Record<string, string>>
    ) => {
      return updateMetadata(bookId, fields);
    },
    onSuccess: (result: MetadataResponse) => {
      queryClient.setQueryData(["metadata", bookId], result);
      toast.success("Metadata saved successfully");
      // Saving does not finish the workflow; the explicit "Mark review
      // complete" action (or a re-run that supersedes this state) does.
    },
    onError: (err) => {
      toast.error(`Failed to save metadata: ${getErrorMessage(err)}`);
    },
  });

  const handleSave = useCallback(
    async (fields: Record<string, string | Record<string, string>>) => {
      await saveMutation.mutateAsync(fields);
    },
    [saveMutation]
  );

  const completeMutation = useMutation({
    mutationFn: () => completeReview(bookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "stages"] });
      queryClient.invalidateQueries({
        queryKey: ["book", bookId, "stages", "current"],
      });
      toast.success("Review marked complete");
    },
    onError: (err) => {
      toast.error(`Could not complete review: ${getErrorMessage(err)}`);
    },
  });

  const openSheet = useCallback(() => {
    setPaneOpened(true);
    setSheetOpen(true);
  }, []);

  const handleFieldFocus = useCallback(
    (fieldName: string) => {
      setFocusedField(fieldName);
      const sourcePage = confidenceByField[fieldName]?.source_page_number;
      if (sourcePage != null) setPanePage(sourcePage);
    },
    [confidenceByField],
  );

  const handleShowSource = useCallback(
    (fieldName: string) => {
      setFocusedField(fieldName);
      setPaneOpened(true);
      const sourcePage = confidenceByField[fieldName]?.source_page_number;
      if (sourcePage != null) setPanePage(sourcePage);
      if (isBelowDesktop()) setSheetOpen(true);
    },
    [confidenceByField],
  );

  const handleAppend = useCallback(
    (text: string) => {
      if (!focusedField) return;
      formActionsRef.current?.appendToField(focusedField, text);
    },
    [focusedField],
  );

  if (isLoadingBook || isLoadingMetadata || isLoadingFields) {
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
          <Spinner className="h-12 w-12 border-[3px] text-[var(--accent-text)] mx-auto mb-4" />
          <h2 className="text-[length:var(--text-lg)] font-semibold text-[var(--text)] mb-2">
            LLM Extraction in Progress
          </h2>
          <p className="text-[var(--text-muted)] text-[length:var(--text-sm)] mb-4">
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

  const evidence = focusedField ? confidenceByField[focusedField] : undefined;
  const focusedFieldLabel = focusedField
    ? (fieldDefs?.find((f) => f.field_name === focusedField)?.display_name ??
      focusedField)
    : undefined;

  const metadataValues = metadata?.fields ?? {};
  const rawFocusedValue = focusedField ? metadataValues[focusedField] : undefined;
  const focusedValue =
    typeof rawFocusedValue === "string" ? rawFocusedValue : undefined;
  const alreadyComplete = book.status === "complete";

  return (
    <WorkflowShell bookId={bookId}>
      <PageContainer layout="workspace" className="flex-1 flex flex-col">
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
                className="lg:hidden"
                onClick={openSheet}
              >
                OCR
              </Button>
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
              <Button
                onClick={() => setConfirmCompleteOpen(true)}
                disabled={completeMutation.isPending || alreadyComplete}
                loading={completeMutation.isPending}
              >
                {alreadyComplete ? "Review complete" : "Mark review complete"}
              </Button>
            </div>
          }
        />

        <ReviewWorkspace
          sheetOpen={sheetOpen}
          onSheetOpenChange={setSheetOpen}
          renderPane={(controls) => (
            <OcrReferencePane
              bookId={bookId}
              pages={corpusQuery.data}
              isLoading={corpusQuery.isLoading}
              error={corpusQuery.error}
              onRetry={() => {
                void corpusQuery.refetch();
              }}
              focusedField={focusedField}
              focusedFieldLabel={focusedFieldLabel}
              focusedValue={focusedValue}
              evidence={evidence}
              pageNumber={panePage}
              onPageNumberChange={setPanePage}
              canAppend={!!focusedField}
              onAppend={handleAppend}
              onCollapse={
                controls.variant === "split" ? controls.onCollapse : undefined
              }
              onRequestCloseSheet={controls.onRequestCloseSheet}
            />
          )}
        >
          <Stack gap={6}>
            {bookStatus.isRunning && (
              <Card>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h2 className="text-[length:var(--text-base)] font-semibold text-[var(--text)]">
                      Auto-processing in progress
                    </h2>
                    <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                      {Math.round(bookStatus.progress)}%
                    </span>
                  </div>
                  <Progress value={bookStatus.progress} />
                  <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
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

            {showLlmHistory && (
              <Card title="LLM Run History" description="Past LLM extraction runs and their outputs.">
                {llmRuns && llmRuns.total > 0 ? (
                  <CollapsibleSection
                    title="All Runs"
                    count={llmRuns.total}
                    defaultOpen={true}
                  >
                    <Stack gap={3}>
                      {llmRuns.items.map((run) => (
                        <div
                          key={run.id}
                          className="border border-[var(--border)] rounded-[var(--radius)] p-3 text-[length:var(--text-sm)]"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-[var(--text)]">
                                {run.model}
                              </span>
                              {run.created_at && (
                                <span className="text-[length:var(--text-xs)] text-[var(--text-subtle)]">
                                  {new Date(run.created_at).toLocaleString()}
                                </span>
                              )}
                            </div>
                          </div>
                          {run.prompt_template && (
                            <details className="mt-1">
                              <summary className="text-[length:var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                                View prompt
                              </summary>
                              <pre className="mt-1 text-[length:var(--text-xs)] bg-[var(--surface-sunken)] p-2 rounded-[var(--radius)] overflow-x-auto whitespace-pre-wrap text-[var(--text)]">
                                {run.prompt_template}
                              </pre>
                            </details>
                          )}
                          {run.parsed_fields && (
                            <details className="mt-1">
                              <summary className="text-[length:var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                                View extracted fields (
                                {Object.keys(run.parsed_fields).length})
                              </summary>
                              <div className="mt-1 grid grid-cols-2 gap-1">
                                {Object.entries(run.parsed_fields).map(
                                  ([k, v]) => (
                                    <div key={k} className="text-[length:var(--text-xs)]">
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
                    <Pagination
                      page={runsPage}
                      totalPages={llmRuns.total_pages}
                      onPageChange={setRunsPage}
                    />
                  </CollapsibleSection>
                ) : (
                  <EmptyState
                    title="No LLM runs yet"
                    description="Past LLM extraction runs will appear here."
                  />
                )}
              </Card>
            )}

            {fieldDefs && (
              <MetadataForm
                fieldDefinitions={fieldDefs}
                values={metadataValues}
                onSave={handleSave}
                isSaving={saveMutation.isPending}
                confidenceByField={confidenceByField}
                onFieldFocus={handleFieldFocus}
                onShowSource={handleShowSource}
                onStatsChange={setFormStats}
                onRegisterActions={(actions) => {
                  formActionsRef.current = actions;
                }}
              />
            )}

            {saveMutation.isError && (
              <ErrorState
                title="Failed to save metadata"
                description={getErrorMessage(saveMutation.error)}
              />
            )}

            <WorkflowNav
              prev={{
                href: `/books/${bookId}/llm-config`,
                label: "Re-run extraction",
              }}
            >
              <LinkButton href="/dashboard" variant="outline" size="sm">
                Go to dashboard
              </LinkButton>
            </WorkflowNav>
          </Stack>
        </ReviewWorkspace>

        <SaveBar
          dirtyCount={formStats.dirty}
          saving={saveMutation.isPending}
          saveLabel="Save metadata"
          onSave={() => formActionsRef.current?.save()}
          onDiscard={() => formActionsRef.current?.discard()}
        />

        <ConfirmDialog
          open={confirmCompleteOpen}
          onClose={() => setConfirmCompleteOpen(false)}
          onConfirm={() => {
            setConfirmCompleteOpen(false);
            completeMutation.mutate();
          }}
          title="Mark review complete?"
          description={
            <div className="space-y-2">
              <p>
                This finalizes the book and completes the workflow. Saving
                metadata no longer completes a book automatically.
              </p>
              {(formStats.missing > 0 || formStats.uncertain > 0) && (
                <ul className="list-disc pl-4 space-y-1 text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                  {formStats.missing > 0 && (
                    <li>
                      {formStats.missing} field
                      {formStats.missing === 1 ? "" : "s"}{" "}
                      {formStats.missing === 1 ? "is" : "are"} still empty.
                    </li>
                  )}
                  {formStats.uncertain > 0 && (
                    <li>
                      {formStats.uncertain} field
                      {formStats.uncertain === 1 ? " has" : "s have"} low
                      confidence or an uncertain value — consider reviewing the
                      evidence.
                    </li>
                  )}
                </ul>
              )}
            </div>
          }
          confirmLabel="Mark complete"
          variant="warning"
          loading={completeMutation.isPending}
        />
      </PageContainer>
    </WorkflowShell>
  );
}

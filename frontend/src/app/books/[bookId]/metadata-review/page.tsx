"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import Image from "next/image";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  getPageImageUrl,
  getMetadata,
  updateMetadata,
  getMetadataFieldDefinitions,
  getMetadataEvidence,
  getLlmRuns,
  completeReview,
  type MetadataResponse,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import { useBookStatus } from "@/hooks/use-book-status";
import { getErrorMessage } from "@/lib/error-handler";
import MetadataForm from "@/components/metadata/metadata-form";
import { Chip } from "@/components/shared/chip";
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

  const [metadataDirtyCount, setMetadataDirtyCount] = useState(0);
  const formActionsRef = useRef<{ save: () => void; discard: () => void } | null>(
    null,
  );

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

  const evidence = focusedField ? confidenceByField[focusedField] : undefined;
  const evidencePage =
    evidence?.source_page_number != null
      ? pages?.find((page) => page.page_number === evidence.source_page_number)
      : undefined;
  const focusedFieldLabel = focusedField
    ? (fieldDefs?.find((f) => f.field_name === focusedField)?.display_name ??
      focusedField)
    : undefined;

  const metadataValues = metadata?.fields ?? {};

  const emptyFieldCount = (fieldDefs ?? []).filter((f) => {
    const v = metadataValues[f.field_name];
    return v === undefined || v === null || String(v).trim() === "";
  }).length;
  const lowConfidenceFieldCount = Object.values(confidenceByField).filter(
    (e) => e.confidence !== null && e.confidence < 0.5,
  ).length;
  const alreadyComplete = book.status === "complete";

  return (
    <WorkflowShell bookId={bookId}>
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

          <Card
            title="Evidence"
            description={
              focusedField
                ? "Where the focused field's value came from."
                : "Focus a field below to see where its value came from."
            }
          >
            {focusedField && evidence ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip
                    dot
                    tone={
                      evidence.confidence == null
                        ? "neutral"
                        : evidence.confidence >= 0.85
                          ? "success"
                          : evidence.confidence >= 0.5
                            ? "warning"
                            : "danger"
                    }
                  >
                    {evidence.confidence == null
                      ? "no score"
                      : `${Math.round(evidence.confidence * 100)}% confidence`}
                  </Chip>
                  <Chip mono>{evidence.extraction_method}</Chip>
                  {evidence.source_page_number != null && (
                    <Chip>page {evidence.source_page_number}</Chip>
                  )}
                  <span className="text-[var(--text-xs)] text-[var(--text-muted)]">
                    {focusedFieldLabel}
                  </span>
                </div>

                {evidencePage && (
                  <Image
                    src={getPageImageUrl(evidencePage.id)}
                    alt={`Source page ${evidence.source_page_number}`}
                    width={900}
                    height={1200}
                    sizes="(min-width: 1024px) 40vw, 100vw"
                    className="max-h-[420px] w-auto rounded-[var(--radius)] border border-[var(--border)]"
                    unoptimized
                  />
                )}

                {evidence.source_text_snippet ? (
                  <p className="rounded-[var(--radius)] bg-[var(--surface-sunken)] p-3 text-[var(--text-sm)] leading-relaxed text-[var(--text)]">
                    …{evidence.source_text_snippet}…
                  </p>
                ) : (
                  <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                    No source snippet was recorded for this field.
                  </p>
                )}

                <LinkButton
                  href={`/books/${bookId}/ocr-review`}
                  variant="outline"
                  size="sm"
                >
                  Open in OCR review
                </LinkButton>
              </div>
            ) : (
              <p className="text-[var(--text-sm)] text-[var(--text-muted)]">
                Focus a field to see its source page, snippet, confidence and
                extraction method.
              </p>
            )}
          </Card>

          {fieldDefs && (
            <MetadataForm
              fieldDefinitions={fieldDefs}
              values={metadataValues}
              onSave={handleSave}
              isSaving={saveMutation.isPending}
              confidenceByField={confidenceByField}
              onFieldFocus={setFocusedField}
              onDirtyCountChange={setMetadataDirtyCount}
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

        <SaveBar
          dirtyCount={metadataDirtyCount}
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
              {(emptyFieldCount > 0 || lowConfidenceFieldCount > 0) && (
                <ul className="list-disc pl-4 space-y-1 text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                  {emptyFieldCount > 0 && (
                    <li>
                      {emptyFieldCount} field{emptyFieldCount === 1 ? "" : "s"}{" "}
                      {emptyFieldCount === 1 ? "is" : "are"} still empty.
                    </li>
                  )}
                  {lowConfidenceFieldCount > 0 && (
                    <li>
                      {lowConfidenceFieldCount} field
                      {lowConfidenceFieldCount === 1 ? " has" : "s have"} low
                      confidence — consider reviewing the evidence.
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

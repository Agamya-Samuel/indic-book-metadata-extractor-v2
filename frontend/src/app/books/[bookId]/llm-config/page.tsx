"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getAllMetadataFieldDefinitions,
  getPromptDefaults,
  runExtraction,
  retryExtraction,
  DEFAULT_EXTRACTION_CONFIG,
  type ExtractionRequest,
  type MetadataFieldDefinition,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobProgress } from "@/hooks/use-job-progress";
import { toastError } from "@/lib/error-handler";
import { toast } from "sonner";
import SliderControl from "@/components/shared/slider-control";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { Chip } from "@/components/shared/chip";
import WorkflowShell from "@/components/shared/workflow-shell";
import { WorkflowPageSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Textarea } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { WorkflowNav } from "@/components/shared/workflow-nav";
import { ErrorState } from "@/components/shared/empty-state";
import JobProgressCard from "@/components/shared/job-progress-card";
import { useDocumentTitle } from "@/hooks/use-document-title";

const BATCH_DISPLAY_NAMES: Record<string, string> = {
  core_identity: "Core Identity",
  contributors: "Contributors",
  publication: "Publication",
  content_classification: "Content Classification",
  edition_series: "Edition & Series",
  relationships: "Relationships",
  ancillary_content: "Ancillary Content",
  physical_extra: "Physical & Extra",
};

export default function LlmConfigPage() {
  useDocumentTitle("LLM configuration");
  const params = useParams();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const [config, setConfig] = useState<ExtractionRequest>({
    ...DEFAULT_EXTRACTION_CONFIG,
  });
  // `null` means "untouched": the live backend default is shown instead of a
  // copy, so the two can never drift apart.
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [extractionPrompt, setExtractionPrompt] = useState<string | null>(null);
  // ISO timestamp of the current run. Scopes job lookups so a completed run
  // from a previous attempt can never shadow the form.
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: fieldDefs, isLoading: isLoadingFields } = useQuery({
    queryKey: ["metadata-fields", bookId, "all"],
    queryFn: () => getAllMetadataFieldDefinitions(bookId),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const { data: promptDefaults } = useQuery({
    queryKey: ["prompt-defaults"],
    queryFn: getPromptDefaults,
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  });

  const defaultSystemPrompt = promptDefaults?.system_prompt ?? "";
  const defaultExtractionPrompt = promptDefaults?.extraction_prompt ?? "";
  const effectiveSystemPrompt = systemPrompt ?? defaultSystemPrompt;
  const effectiveExtractionPrompt = extractionPrompt ?? defaultExtractionPrompt;

  const progress = useJobProgress({
    bookId,
    jobType: "llm",
    startedAt,
    enabled: !!bookId,
  });

  const fieldsByBatch = useMemo(() => {
    if (!fieldDefs) return {};
    const grouped: Record<string, MetadataFieldDefinition[]> = {};
    for (const field of fieldDefs) {
      if (!grouped[field.batch_group]) {
        grouped[field.batch_group] = [];
      }
      grouped[field.batch_group].push(field);
    }
    return grouped;
  }, [fieldDefs]);

  // The backend processes one call per batch_group, not per N fields.
  const totalBatches = Object.keys(fieldsByBatch).length;
  const totalFields = fieldDefs?.length ?? 0;

  const runMutation = useMutation({
    mutationFn: () => {
      const payload: ExtractionRequest = {
        ...config,
        custom_system_prompt:
          effectiveSystemPrompt !== defaultSystemPrompt
            ? effectiveSystemPrompt
            : null,
        custom_extraction_prompt:
          effectiveExtractionPrompt !== defaultExtractionPrompt
            ? effectiveExtractionPrompt
            : null,
      };
      if (book?.status === "complete") {
        return retryExtraction(bookId, payload);
      }
      return runExtraction(bookId, payload);
    },
    onMutate: () => {
      // Record the run start *before* the request so the new job is scoped in
      // and any older job is scoped out.
      setStartedAt(new Date().toISOString());
      setError(null);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
      toast.info("LLM extraction started");
    },
    onError: (err) => {
      setStartedAt(null);
      setError(toastError(err, "Could not start extraction"));
    },
  });

  const hasPriorRun = progress.jobs.some(
    (j) =>
      j.job_type === "llm" &&
      (j.status === "completed" ||
        j.status === "failed" ||
        j.status === "cancelled"),
  );
  const systemPromptModified =
    Boolean(promptDefaults) && systemPrompt !== null && systemPrompt !== defaultSystemPrompt;
  const extractionPromptModified =
    Boolean(promptDefaults) &&
    extractionPrompt !== null &&
    extractionPrompt !== defaultExtractionPrompt;
  const currentRunActive = Boolean(startedAt) && progress.isRunning;
  const currentRunComplete = Boolean(startedAt) && progress.isComplete;
  const currentRunFailed = Boolean(startedAt) && progress.isFailed;

  if (isLoadingBook || isLoadingFields) {
    return <WorkflowPageSkeleton />;
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
      <PageContainer>
        <PageHeader
          title="LLM Configuration"
          description={
            <>
              {book.title || book.filename} &bull;{" "}
              {getLanguageName(book.language)} &bull; Configure extraction
              parameters
            </>
          }
        />

        {currentRunActive && (
          <div className="mb-6">
            <JobProgressCard
              title="Running LLM extraction"
              progress={progress.progress}
              status={progress.job?.status}
              phase={`Extracting ${totalBatches} batch groups of metadata fields`}
              elapsedMs={progress.elapsedMs}
              onCancel={progress.cancel}
              cancelling={progress.cancelling}
            />
          </div>
        )}

        {currentRunComplete && (
          <div className="mb-6 rounded-[var(--radius-lg)] border border-[var(--success-500)]/30 bg-[var(--success-50)] px-4 py-3 text-[length:var(--text-sm)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>Extraction complete.</span>
              <LinkButton
                href={`/books/${bookId}/metadata-review`}
                size="sm"
              >
                Review metadata
              </LinkButton>
            </div>
          </div>
        )}

        {currentRunFailed && (
          <div className="mb-6">
            <JobProgressCard
              title="Extraction failed"
              progress={progress.progress}
              status="failed"
              error={progress.errorLog ?? "The extraction job failed."}
              onRetry={() => runMutation.mutate()}
            />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3">
            <Stack gap={4}>
              <Card title="Model" description="The extractor is pinned for production.">
                <Stack gap={4}>
                  <Field label="LLM Model">
                    <div className="flex min-h-11 items-center rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-3 text-[length:var(--text-sm)]">
                      <span className="font-medium">{config.model}</span>
                      <span className="ml-2 text-[var(--text-muted)]">
                        pinned
                      </span>
                    </div>
                  </Field>

                  <SliderControl
                    label="Temperature"
                    value={config.temperature}
                    min={0}
                    max={2}
                    step={0.1}
                    onChange={(v) =>
                      setConfig((prev) => ({ ...prev, temperature: v }))
                    }
                    formatValue={(v) => v.toFixed(1)}
                  />

                  <SliderControl
                    label="Max Tokens"
                    value={config.max_tokens}
                    min={100}
                    max={4096}
                    step={100}
                    onChange={(v) =>
                      setConfig((prev) => ({ ...prev, max_tokens: v }))
                    }
                  />
                </Stack>
              </Card>

              <Card title="Batching" description="One call per field group.">
                <Stack gap={3}>
                  <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                    {totalBatches} LLM call{totalBatches !== 1 ? "s" : ""} will be
                    made across {totalFields} fields (one per batch group).
                  </p>

                  <div className="pt-3 border-t border-[var(--border)] space-y-2">
                    {hasPriorRun && (
                      <p className="text-[length:var(--text-xs)] text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                        A previous run exists. Running again replaces the
                        extracted metadata.
                      </p>
                    )}
                    <Button
                      onClick={() => runMutation.mutate()}
                      disabled={runMutation.isPending || currentRunActive}
                      loading={runMutation.isPending}
                      className="w-full"
                    >
                      {runMutation.isPending
                        ? "Starting..."
                        : hasPriorRun
                          ? "Run again"
                          : "Run Extraction"}
                    </Button>

                    {error && (
                      <ErrorState title="Could not start extraction" description={error} />
                    )}
                  </div>
                </Stack>
              </Card>

              </Stack>
          </div>

          <div className="lg:col-span-5">
            <Stack gap={4}>
              <CollapsibleSection
                title="System prompt"
                defaultOpen={false}
                meta={
                  systemPromptModified ? (
                    <Chip tone="warning">modified</Chip>
                  ) : undefined
                }
              >
                <p className="mb-2 text-[length:var(--text-xs)] text-[var(--text-muted)]">
                  Instructs the model on its role and output format. The backend
                  renders this as a Jinja2 template; available variables:{" "}
                  {promptDefaults?.variables.map((name) => `{{ ${name} }}`).join(", ") ||
                    "loading…"}
                </p>
                <Textarea
                  value={effectiveSystemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={8}
                  className="font-mono"
                  aria-label="System prompt"
                />
                {systemPromptModified && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => setSystemPrompt(null)}
                  >
                    Reset to default
                  </Button>
                )}
              </CollapsibleSection>

              <CollapsibleSection
                title="Extraction prompt"
                defaultOpen={false}
                meta={
                  extractionPromptModified ? (
                    <Chip tone="warning">modified</Chip>
                  ) : undefined
                }
              >
                <p className="mb-2 text-[length:var(--text-xs)] text-[var(--text-muted)]">
                  The user-turn prompt that requests field extraction. The field
                  list is available as{" "}
                  <code>{"{% for field in fields %}"}</code> with{" "}
                  <code>{"{{ field.name }}"}</code>,{" "}
                  <code>{"{{ field.description }}"}</code> and{" "}
                  <code>{"{{ field.guidance }}"}</code> inside the loop.
                </p>
                <Textarea
                  value={effectiveExtractionPrompt}
                  onChange={(e) => setExtractionPrompt(e.target.value)}
                  rows={12}
                  className="font-mono"
                  aria-label="Extraction prompt"
                />
                {extractionPromptModified && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => setExtractionPrompt(null)}
                  >
                    Reset to default
                  </Button>
                )}
              </CollapsibleSection>
            </Stack>
          </div>

          <div className="lg:col-span-4">
            <Card title="Metadata Fields by Batch" description="Grouped by batch_group, ready to send to the LLM.">
              <div className="space-y-2 max-h-[700px] overflow-y-auto">
                {Object.entries(fieldsByBatch).map(([batch, fields]) => (
                  <CollapsibleSection
                    key={batch}
                    title={BATCH_DISPLAY_NAMES[batch] ?? batch}
                    count={fields.length}
                    defaultOpen={batch === "core_identity"}
                  >
                    <div className="space-y-1">
                      {fields.map((field) => (
                        <div
                          key={field.field_name}
                          className="flex items-center justify-between px-2 py-1.5 rounded-[var(--radius)] hover:bg-[var(--surface-sunken)]"
                        >
                          <span className="text-[length:var(--text-sm)] text-[var(--text)]">
                            {field.display_name}
                          </span>
                          {field.wikidata_property && (
                            <span className="text-[length:var(--text-xs)] px-1.5 py-0.5 bg-[var(--accent-soft)] text-[var(--accent-soft-text)] rounded-[var(--radius-xs)]">
                              {field.wikidata_property}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                ))}
              </div>
            </Card>
          </div>
        </div>
      <WorkflowNav
          prev={{
            href: `/books/${bookId}/ocr-review`,
            label: "Back to OCR Review",
          }}
        >
          <LinkButton href={`/books/${bookId}/jobs`} variant="outline" size="sm">
            View Jobs
          </LinkButton>
        </WorkflowNav>
      </PageContainer>
    </WorkflowShell>
  );
}
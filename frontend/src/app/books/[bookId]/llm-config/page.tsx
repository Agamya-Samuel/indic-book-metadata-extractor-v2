"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getAllAvailableModels,
  getAllMetadataFieldDefinitions,
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
import { Field, Select, Textarea } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { WorkflowNav } from "@/components/shared/workflow-nav";
import { Banner, ErrorState } from "@/components/shared/empty-state";
import JobProgressCard from "@/components/shared/job-progress-card";
import { useDocumentTitle } from "@/hooks/use-document-title";

const DEFAULT_SYSTEM_PROMPT = `You are an expert bibliographic metadata extractor specializing in {{language}} language books.
You will be given OCR-extracted text from scanned book pages. The text may contain OCR errors — use your knowledge of {{language}} to interpret corrupted words.
Extract the requested metadata fields as accurately as possible from the provided text.
If a field cannot be determined from the text, return null for that field.
Always respond with valid JSON matching the exact schema provided. Do not include any text outside the JSON object.`;

const DEFAULT_EXTRACTION_PROMPT = `Extract the following metadata fields from this {{language}} book text.

Fields to extract:
{{field_descriptions}}

OCR Text (from {{page_count}} pages of a scanned book):
---
{{ocr_text}}
---

Respond with a JSON object containing exactly these fields. Use null for fields not found in the text.
Do not include any explanation or text outside the JSON object.`;

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
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [extractionPrompt, setExtractionPrompt] = useState(
    DEFAULT_EXTRACTION_PROMPT
  );
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

  const {
    data: models,
    isLoading: isLoadingModels,
    isError: modelsError,
  } = useQuery({
    queryKey: ["models", "all"],
    queryFn: getAllAvailableModels,
    staleTime: 60 * 1000,
    gcTime: 10 * 60 * 1000,
    retry: 1,
  });

  const { data: fieldDefs, isLoading: isLoadingFields } = useQuery({
    queryKey: ["metadata-fields", bookId, "all"],
    queryFn: () => getAllMetadataFieldDefinitions(bookId),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const progress = useJobProgress({
    bookId,
    jobType: "llm",
    startedAt,
    enabled: !!bookId,
  });

  const ollamaUnreachable =
    modelsError || (models !== undefined && models.length === 0);

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
          systemPrompt !== DEFAULT_SYSTEM_PROMPT ? systemPrompt : null,
        custom_extraction_prompt:
          extractionPrompt !== DEFAULT_EXTRACTION_PROMPT
            ? extractionPrompt
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
  const systemPromptModified = systemPrompt !== DEFAULT_SYSTEM_PROMPT;
  const extractionPromptModified =
    extractionPrompt !== DEFAULT_EXTRACTION_PROMPT;
  const currentRunActive = Boolean(startedAt) && progress.isRunning;
  const currentRunComplete = Boolean(startedAt) && progress.isComplete;
  const currentRunFailed = Boolean(startedAt) && progress.isFailed;

  if (isLoadingBook || isLoadingModels || isLoadingFields) {
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

        {ollamaUnreachable && (
          <Banner tone="warning" className="mb-6">
            Ollama is unreachable or has no models installed. Start Ollama and
            pull a model before running extraction.
          </Banner>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3">
            <Stack gap={4}>
              <Card title="Model Selection" description="Pick the LLM and tune sampling.">
                <Stack gap={4}>
                  <Field label="LLM Model">
                    <Select
                      value={config.model}
                      onChange={(e) =>
                        setConfig((prev) => ({ ...prev, model: e.target.value }))
                      }
                    >
                      <option value="phi4-mini">phi4-mini (default)</option>
                      {models
                        ?.filter((m) => m.name !== "phi4-mini")
                        .map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name}
                            {m.size_gb ? ` (${m.size_gb.toFixed(1)} GB)` : ""}
                          </option>
                        ))}
                    </Select>
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
                      disabled={
                        runMutation.isPending ||
                        currentRunActive ||
                        ollamaUnreachable
                      }
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
                  Instructs the model on its role and output format. Variables:{" "}
                  {"{{language}}"}
                </p>
                <Textarea
                  value={systemPrompt}
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
                    onClick={() => setSystemPrompt(DEFAULT_SYSTEM_PROMPT)}
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
                  The user-turn prompt that requests field extraction. Variables:{" "}
                  {"{{language}}"}, {"{{field_descriptions}}"}, {"{{ocr_text}}"},{" "}
                  {"{{page_count}}"}
                </p>
                <Textarea
                  value={extractionPrompt}
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
                    onClick={() => setExtractionPrompt(DEFAULT_EXTRACTION_PROMPT)}
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
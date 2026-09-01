"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getAvailableModels,
  getMetadataFieldDefinitions,
  getBookJobs,
  runExtraction,
  retryExtraction,
  DEFAULT_EXTRACTION_CONFIG,
  type ExtractionRequest,
  type MetadataFieldDefinition,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getErrorMessage } from "@/lib/error-handler";
import SliderControl from "@/components/shared/slider-control";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { WorkflowPageSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Select, Textarea } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { Spinner } from "@/components/shared/spinner";
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
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  useWorkflowHydration(bookId);
  const { currentStep, completedStep, setStep: setWorkflowStep, setCompletedStep } = useWorkflowStore();

  const [config, setConfig] = useState<ExtractionRequest>({
    ...DEFAULT_EXTRACTION_CONFIG,
  });
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [extractionPrompt, setExtractionPrompt] = useState(
    DEFAULT_EXTRACTION_PROMPT
  );
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: models, isLoading: isLoadingModels } = useQuery({
    queryKey: ["models"],
    queryFn: getAvailableModels,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const { data: fieldDefs, isLoading: isLoadingFields } = useQuery({
    queryKey: ["metadata-fields", bookId],
    queryFn: () => getMetadataFieldDefinitions(bookId),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const { isComplete, isFailed, progress, isPolling, errorLog, allJobs } =
    useJobPolling({
      bookId,
      jobId: activeJobId ?? undefined,
      jobType: "llm",
      enabled: !!activeJobId || book?.status === "llm_running" || book?.status === "awaiting_review",
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

  const totalBatches = useMemo(() => {
    return Math.ceil((fieldDefs?.length ?? 0) / config.fields_per_batch);
  }, [fieldDefs, config.fields_per_batch]);

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
    onSuccess: (result) => {
      setActiveJobId(result.job_id);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
      toast.info("LLM extraction started");
      setWorkflowStep(5);
      setCompletedStep(5);
    },
    onError: (err) => {
      const msg = getErrorMessage(err);
      setError(msg);
      toast.error(msg);
    },
  });

  useEffect(() => {
    if (isComplete && activeJobId) {
      toast.success("LLM extraction completed successfully");
      setWorkflowStep(6);
      setCompletedStep(6);
    }
    if (isFailed && activeJobId && errorLog) {
      toast.error("LLM extraction failed");
    }
  }, [isComplete, isFailed, activeJobId, errorLog, setWorkflowStep, setCompletedStep]);

  // On page refresh, discover an in-flight LLM job so the progress view
  // is restored instead of showing the config form. Skip terminal jobs
  // (completed/failed/cancelled) so a cancelled run doesn't trap the user
  // on the polling screen.
  useEffect(() => {
    if (!activeJobId && allJobs.length > 0) {
      const llmJob = allJobs.find((j) => j.job_type === "llm");
      if (
        llmJob &&
        llmJob.status !== "completed" &&
        llmJob.status !== "failed" &&
        llmJob.status !== "cancelled"
      ) {
        setActiveJobId(llmJob.id);
      }
    }
  }, [activeJobId, allJobs]);

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

  if (isPolling || isComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="text-center max-w-md mx-auto px-4">
          <Spinner className="h-12 w-12 border-[3px] text-[var(--accent)] mx-auto mb-4" />
          <h2 className="text-[var(--text-lg)] font-semibold text-[var(--text)] mb-2">
            {isComplete
              ? "Extraction complete"
              : isFailed
                ? "Extraction failed"
                : "Running LLM extraction"}
          </h2>
          {!isComplete && !isFailed && (
            <>
              <p className="text-[var(--text-muted)] text-[var(--text-sm)] mb-4">
                {Math.round(progress)}% complete
              </p>
              <div className="mb-4">
                <Progress value={progress} />
              </div>
              <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                Processing {totalBatches} batch groups of metadata fields
              </p>
            </>
          )}
          {isFailed && errorLog && (
            <div className="mb-4 text-left">
              <ErrorState title="Error" description={errorLog} />
            </div>
          )}
          <div className="flex gap-3 justify-center mt-4">
            {isComplete && (
              <Button
                onClick={() =>
                  router.push(`/books/${bookId}/metadata-review`)
                }
              >
                Review Metadata
              </Button>
            )}
            {(isComplete || isFailed) && (
              <Button
                variant="outline"
                onClick={() => setActiveJobId(null)}
              >
                Back to Config
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 5 ? 5 : currentStep} completedStep={completedStep} />

      <PageContainer>
        <PageHeader
          title="LLM Configuration"
          description={
            <>
              {book.title || book.filename} &bull;{" "}
              {getLanguageName(book.language)} &bull; Configure
              extraction parameters
            </>
          }
        />

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
                      <option value="qwen2.5">qwen2.5 (default)</option>
  {models
    ?.filter((m) => m.name !== "qwen2.5")
                        .map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name}
                            {m.size_gb ? ` (${m.size_gb.toFixed(1)} GB)` : ""}
                          </option>
                        ))}
                    </Select>
                  </Field>
                  {models && models.length === 0 && (
                    <p className="text-[var(--text-xs)] text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                      No models detected. Ensure Ollama is running with a model
                      pulled.
                    </p>
                  )}

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

              <Card title="Batching" description="How many fields per LLM call.">
                <Stack gap={3}>
                  <SliderControl
                    label="Fields per Batch"
                    value={config.fields_per_batch}
                    min={3}
                    max={20}
                    onChange={(v) =>
                      setConfig((prev) => ({ ...prev, fields_per_batch: v }))
                    }
                  />
                  <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                    {totalBatches} LLM call{totalBatches !== 1 ? "s" : ""} will be
                    made ({fieldDefs?.length ?? 0} fields ÷ {config.fields_per_batch}{" "}
                    per batch)
                  </p>

                  <div className="pt-3 border-t border-[var(--border)] space-y-2">
                    <Button
                      onClick={() => runMutation.mutate()}
                      disabled={
                        runMutation.isPending || book.status === "llm_running"
                      }
                      loading={runMutation.isPending}
                      className="w-full"
                    >
                      {runMutation.isPending
                        ? "Starting..."
                        : "Run Extraction"}
                    </Button>

                    {error && (
                      <ErrorState title="Could not start extraction" description={error} />
                    )}
                  </div>
                </Stack>
              </Card>

              <div className="flex gap-2">
                <LinkButton
                  href={`/books/${bookId}/ocr-review`}
                  variant="outline"
                  className="flex-1"
                >
                  Back to OCR Review
                </LinkButton>
                <LinkButton
                  href={`/books/${bookId}/jobs`}
                  variant="outline"
                  className="flex-1"
                >
                  View Jobs
                </LinkButton>
              </div>
            </Stack>
          </div>

          <div className="lg:col-span-5">
            <Stack gap={4}>
              <Card title="System Prompt" description="Instructs the model on its role and output format.">
                <Textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={8}
                  className="font-mono"
                />
                <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">
                  Available variables: {"{{language}}"}
                </p>
              </Card>

              <Card title="Extraction Prompt" description="The user-turn prompt that requests field extraction.">
                <Textarea
                  value={extractionPrompt}
                  onChange={(e) => setExtractionPrompt(e.target.value)}
                  rows={12}
                  className="font-mono"
                />
                <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">
                  Variables: {"{{language}}"}, {"{{field_descriptions}}"},{" "}
                  {"{{ocr_text}}"}, {"{{page_count}}"}
                </p>
              </Card>
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
                          <span className="text-[var(--text-sm)] text-[var(--text)]">
                            {field.display_name}
                          </span>
                          {field.wikidata_property && (
                            <span className="text-[var(--text-xs)] px-1.5 py-0.5 bg-[var(--accent-soft)] text-[var(--accent-soft-text)] rounded-[var(--radius-xs)]">
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
      </PageContainer>
    </div>
  );
}

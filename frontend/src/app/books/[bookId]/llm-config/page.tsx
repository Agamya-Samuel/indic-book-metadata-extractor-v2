"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getAvailableModels,
  getMetadataFieldDefinitions,
  runExtraction,
  retryExtraction,
  DEFAULT_EXTRACTION_CONFIG,
  type ExtractionRequest,
  type MetadataFieldDefinition,
} from "@/lib/api";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getErrorMessage } from "@/lib/error-handler";
import SliderControl from "@/components/shared/slider-control";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";

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
  });

  const { data: models, isLoading: isLoadingModels } = useQuery({
    queryKey: ["models"],
    queryFn: getAvailableModels,
  });

  const { data: fieldDefs, isLoading: isLoadingFields } = useQuery({
    queryKey: ["metadata-fields", bookId],
    queryFn: () => getMetadataFieldDefinitions(bookId),
  });

  const { isComplete, isFailed, progress, isPolling, errorLog } =
    useJobPolling({
      bookId,
      jobId: activeJobId ?? undefined,
      enabled: !!activeJobId,
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

  if (isLoadingBook || isLoadingModels || isLoadingFields) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!book) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Book not found.</p>
      </div>
    );
  }

  if (isPolling || isComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md mx-auto">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            {isComplete
              ? "Extraction Complete!"
              : isFailed
                ? "Extraction Failed"
                : "Running LLM Extraction..."}
          </h2>
          {!isComplete && !isFailed && (
            <>
              <p className="text-gray-600 text-sm mb-4">
                {Math.round(progress)}% complete
              </p>
              <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${Math.round(progress)}%` }}
                />
              </div>
              <p className="text-xs text-gray-500">
                Processing {totalBatches} batch groups of metadata fields
              </p>
            </>
          )}
          {isFailed && errorLog && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700 mb-4">
              <p className="font-medium">Error</p>
              <p className="mt-1">{errorLog}</p>
            </div>
          )}
          <div className="flex gap-3 justify-center mt-4">
            {isComplete && (
              <button
                onClick={() =>
                  router.push(`/books/${bookId}/metadata-review`)
                }
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Review Metadata
              </button>
            )}
            {(isComplete || isFailed) && (
              <button
                onClick={() => setActiveJobId(null)}
                className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
              >
                Back to Config
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 5 ? 5 : currentStep} completedStep={completedStep} />

      <div className="bg-white border-b px-6 py-4">
        <div className="max-w-screen-2xl mx-auto">
          <h1 className="text-xl font-bold text-gray-900">
            LLM Configuration
          </h1>
          <p className="text-sm text-gray-500">
            {book.title || book.filename} &bull;{" "}
            {book.language === "tel" ? "Telugu" : "Hindi"} &bull; Configure
            extraction parameters
          </p>
        </div>
      </div>

      <div className="max-w-screen-2xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-white shadow rounded-lg p-4 space-y-4">
              <h3 className="text-sm font-medium text-gray-700 border-b pb-2">
                Model Selection
              </h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  LLM Model
                </label>
                <select
                  value={config.model}
                  onChange={(e) =>
                    setConfig((prev) => ({ ...prev, model: e.target.value }))
                  }
                  className="w-full border rounded px-3 py-2 text-sm"
                >
                  <option value="airavata">airavata (default)</option>
                  {models
                    ?.filter((m) => m.name !== "airavata")
                    .map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                        {m.size_gb ? ` (${m.size_gb.toFixed(1)} GB)` : ""}
                      </option>
                    ))}
                </select>
                {models && models.length === 0 && (
                  <p className="mt-1 text-xs text-yellow-600">
                    No models detected. Ensure Ollama is running with a model
                    pulled.
                  </p>
                )}
              </div>

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
            </div>

            <div className="bg-white shadow rounded-lg p-4 space-y-3">
              <SliderControl
                label="Fields per Batch"
                value={config.fields_per_batch}
                min={3}
                max={20}
                onChange={(v) =>
                  setConfig((prev) => ({ ...prev, fields_per_batch: v }))
                }
              />
              <p className="text-xs text-gray-500">
                {totalBatches} LLM call{totalBatches !== 1 ? "s" : ""} will be
                made ({fieldDefs?.length ?? 0} fields ÷ {config.fields_per_batch}{" "}
                per batch)
              </p>

              <div className="pt-3 border-t space-y-2">
                <button
                  onClick={() => runMutation.mutate()}
                  disabled={
                    runMutation.isPending || book.status === "llm_running"
                  }
                  className="w-full px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {runMutation.isPending
                    ? "Starting..."
                    : "Run Extraction"}
                </button>

                {error && (
                  <p className="text-sm text-red-600">{error}</p>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <a
                href={`/books/${bookId}/ocr-review`}
                className="flex-1 text-center px-4 py-2 text-sm border rounded hover:bg-gray-50"
              >
                Back to OCR Review
              </a>
              <a
                href={`/books/${bookId}/jobs`}
                className="flex-1 text-center px-4 py-2 text-sm border rounded hover:bg-gray-50"
              >
                View Jobs
              </a>
            </div>
          </div>

          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white shadow rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                System Prompt
              </h3>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={8}
                className="w-full border rounded px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                Available variables: {"{{language}}"}
              </p>
            </div>

            <div className="bg-white shadow rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Extraction Prompt
              </h3>
              <textarea
                value={extractionPrompt}
                onChange={(e) => setExtractionPrompt(e.target.value)}
                rows={12}
                className="w-full border rounded px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                Variables: {"{{language}}"}, {"{{field_descriptions}}"},{" "}
                {"{{ocr_text}}"}, {"{{page_count}}"}
              </p>
            </div>
          </div>

          <div className="lg:col-span-4">
            <div className="bg-white shadow rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3 border-b pb-2">
                Metadata Fields by Batch
              </h3>
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
                          className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-gray-50"
                        >
                          <span className="text-sm text-gray-700">
                            {field.display_name}
                          </span>
                          {field.wikidata_property && (
                            <span className="text-xs px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded">
                              {field.wikidata_property}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

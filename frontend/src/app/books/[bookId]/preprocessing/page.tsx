"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  updatePreprocessing,
  getPageImageUrl,
  getThumbnailUrl,
  runOcr,
  DEFAULT_PREPROCESSING_CONFIG,
  type PreprocessingConfig,
} from "@/lib/api";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getErrorMessage } from "@/lib/error-handler";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { getLanguageName } from "@/lib/utils";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { WorkflowPageSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import Image from "next/image";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

export default function PreprocessingPage() {
  useDocumentTitle("Preprocessing");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  useWorkflowHydration(bookId);
  const { currentStep, completedStep, setStep: setWorkflowStep, setCompletedStep } = useWorkflowStore();

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

  const [selectedPageIndex, setSelectedPageIndex] = useState(0);
  const [config, setConfig] = useState<PreprocessingConfig>({
    ...DEFAULT_PREPROCESSING_CONFIG,
  });
  const [previewKey, setPreviewKey] = useState(0);

  const preprocessingMutation = useMutation({
    mutationFn: async (params: { pageId: string; cfg: PreprocessingConfig }) => {
      return updatePreprocessing(params.pageId, params.cfg);
    },
    onSuccess: () => {
      setPreviewKey((k) => k + 1);
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
      toast.success("Preprocessing applied to page");
    },
    onError: (err) => {
      toast.error(`Preprocessing failed: ${getErrorMessage(err)}`);
    },
  });

  const applyToAllMutation = useMutation({
    mutationFn: async () => {
      if (!pages) return [];
      return Promise.all(
        pages.map((p) => updatePreprocessing(p.id, config))
      );
    },
    onSuccess: () => {
      setPreviewKey((k) => k + 1);
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
      toast.success("Preprocessing applied to all pages");
    },
    onError: (err) => {
      toast.error(`Preprocessing failed: ${getErrorMessage(err)}`);
    },
  });

  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const runOcrMutation = useMutation({
    mutationFn: () => runOcr(bookId),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      setActiveJobId(job.id);
      toast.info("OCR job started");
      setWorkflowStep(3);
      setCompletedStep(3);
    },
    onError: (err) => {
      toast.error(`OCR failed to start: ${getErrorMessage(err)}`);
    },
  });

  const { isComplete, isFailed, progress, isPolling, errorLog } = useJobPolling({
    bookId,
    jobId: activeJobId ?? undefined,
    enabled: !!activeJobId,
  });

  useEffect(() => {
    if (activeJobId && isComplete) {
      toast.success("OCR completed successfully");
      setWorkflowStep(4);
      setCompletedStep(4);
      router.push(`/books/${bookId}/ocr-review?jobId=${activeJobId}`);
    }
  }, [activeJobId, isComplete, bookId, router, setWorkflowStep, setCompletedStep]);

  if (isLoadingBook || isLoadingPages) {
    return <WorkflowPageSkeleton />;
  }

  if (!book || !pages || pages.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState
          title="No pages found"
          description="Please select pages first."
        />
      </div>
    );
  }

  const currentPage = pages[selectedPageIndex];

  const handleConfigChange = <K extends keyof PreprocessingConfig>(
    key: K,
    value: PreprocessingConfig[K]
  ) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handlePreview = () => {
    if (!currentPage) return;
    preprocessingMutation.mutate({ pageId: currentPage.id, cfg: config });
  };

  const handlePrevPage = () => {
    setSelectedPageIndex((prev) => Math.max(0, prev - 1));
    setPreviewKey((k) => k + 1);
  };

  const handleNextPage = () => {
    setSelectedPageIndex((prev) => Math.min(pages.length - 1, prev + 1));
    setPreviewKey((k) => k + 1);
  };

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 3 ? 3 : currentStep} completedStep={completedStep} />

      <PageContainer>
        <PageHeader
          eyebrow="Image Preprocessing"
          title={book.title || book.filename}
          description={
            <>
              Language: {getLanguageName(book.language)} &bull;{" "}
              {pages.length} pages
            </>
          }
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-2">
            <Card title="Pages" description="Click a thumbnail to preview." flush>
              <div className="grid grid-cols-3 lg:grid-cols-2 gap-2 max-h-[600px] overflow-y-auto">
                {pages.map((page, idx) => (
                  <button
                    key={page.id}
                    onClick={() => {
                      setSelectedPageIndex(idx);
                      setPreviewKey((k) => k + 1);
                    }}
                    aria-label={`Select page ${page.page_number}`}
                    aria-current={idx === selectedPageIndex ? "true" : undefined}
                    className={cn(
                      "relative aspect-[3/4] rounded-[var(--radius)] overflow-hidden border-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
                      idx === selectedPageIndex
                        ? "border-[var(--accent)] ring-2 ring-[var(--accent-ring)]/30"
                        : "border-[var(--border)] hover:border-[var(--border-strong)]"
                    )}
                  >
                    <Image
                      src={getThumbnailUrl(bookId, page.page_number)}
                      alt={`Page ${page.page_number}`}
                      fill
                      sizes="(min-width: 1024px) 16vw, (min-width: 640px) 25vw, 50vw"
                      className="object-cover"
                      unoptimized
                    />
                  </button>
                ))}
              </div>
            </Card>
          </div>

          <div className="lg:col-span-6">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                  Page {currentPage.page_number} &mdash; Preview
                </h3>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrevPage}
                    disabled={selectedPageIndex === 0}
                  >
                    Previous
                  </Button>
                  <span className="text-[var(--text-sm)] text-[var(--text-muted)] tabular-nums">
                    {selectedPageIndex + 1} / {pages.length}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextPage}
                    disabled={selectedPageIndex === pages.length - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>

              <div className="border border-[var(--border)] rounded-[var(--radius)] bg-[var(--surface-sunken)] flex items-center justify-center min-h-[400px]">
                <Image
                  key={previewKey}
                  src={`${getPageImageUrl(currentPage.id)}?v=${previewKey}`}
                  alt={`Page ${currentPage.page_number}`}
                  width={1200}
                  height={1600}
                  sizes="(min-width: 1024px) 50vw, 100vw"
                  className="max-w-full max-h-[600px] w-auto h-auto object-contain"
                  unoptimized
                />
              </div>

              {currentPage.preprocessing_config && (
                <p className="mt-2 text-[var(--text-xs)] text-[var(--success-700)] dark:text-[var(--success-100)]">
                  Custom preprocessing applied to this page
                </p>
              )}
            </Card>
          </div>

          <div className="lg:col-span-4">
            <Card title="Preprocessing Settings" description="Tune the image processing pipeline.">
              <Stack gap={4}>
                <ToggleControl
                  label="Grayscale"
                  checked={config.grayscale}
                  onChange={(v) => handleConfigChange("grayscale", v)}
                />

                <SliderControl
                  label="Brightness"
                  value={config.brightness}
                  min={-100}
                  max={100}
                  onChange={(v) => handleConfigChange("brightness", v)}
                />

                <SliderControl
                  label="Contrast"
                  value={config.contrast}
                  min={-100}
                  max={100}
                  onChange={(v) => handleConfigChange("contrast", v)}
                />

                <Field label="Binarization">
                  <Select
                    value={config.binarization || "none"}
                    onChange={(e) =>
                      handleConfigChange(
                        "binarization",
                        e.target.value === "none"
                          ? null
                          : (e.target.value as "otsu" | "adaptive")
                      )
                    }
                  >
                    <option value="none">None</option>
                    <option value="otsu">Otsu</option>
                    <option value="adaptive">Adaptive</option>
                  </Select>
                </Field>

                {config.binarization === "adaptive" && (
                  <>
                    <SliderControl
                      label="Adaptive Block Size"
                      value={config.adaptive_block_size}
                      min={3}
                      max={51}
                      onChange={(v) => handleConfigChange("adaptive_block_size", v)}
                    />
                    <SliderControl
                      label="Adaptive C"
                      value={config.adaptive_c}
                      min={-10}
                      max={10}
                      onChange={(v) => handleConfigChange("adaptive_c", v)}
                    />
                  </>
                )}

                <ToggleControl
                  label="Deskew"
                  checked={config.deskew}
                  onChange={(v) => handleConfigChange("deskew", v)}
                />

                <ToggleControl
                  label="Denoise"
                  checked={config.denoise}
                  onChange={(v) => handleConfigChange("denoise", v)}
                />

                {config.denoise && (
                  <SliderControl
                    label="Denoise Strength"
                    value={config.denoise_strength}
                    min={1}
                    max={50}
                    onChange={(v) => handleConfigChange("denoise_strength", v)}
                  />
                )}

                <div className="pt-3 border-t border-[var(--border)] space-y-3">
                  <Button
                    onClick={handlePreview}
                    disabled={preprocessingMutation.isPending}
                    loading={preprocessingMutation.isPending}
                    className="w-full"
                  >
                    {preprocessingMutation.isPending
                      ? "Processing..."
                      : "Preview Current Page"}
                  </Button>

                  <Button
                    variant="secondary"
                    onClick={() => applyToAllMutation.mutate()}
                    disabled={applyToAllMutation.isPending}
                    loading={applyToAllMutation.isPending}
                    className="w-full"
                  >
                    {applyToAllMutation.isPending
                      ? "Applying..."
                      : "Apply to All Pages"}
                  </Button>

                  <Button
                    onClick={() => runOcrMutation.mutate()}
                    disabled={runOcrMutation.isPending || !!activeJobId}
                    loading={runOcrMutation.isPending}
                    className="w-full"
                  >
                    {runOcrMutation.isPending
                      ? "Starting OCR..."
                      : isPolling
                        ? `Running OCR... ${Math.round(progress)}%`
                        : "Run OCR on All Pages"}
                  </Button>

                  {isPolling && (
                    <Progress value={progress} />
                  )}

                  {(runOcrMutation.isError || (isFailed && errorLog)) && (
                    <ErrorState
                      title="OCR failed"
                      description={
                        runOcrMutation.isError
                          ? getErrorMessage(runOcrMutation.error)
                          : errorLog || undefined
                      }
                    />
                  )}
                </div>
              </Stack>
            </Card>
          </div>
        </div>
      </PageContainer>
    </div>
  );
}

function SliderControl({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[var(--text-sm)] font-medium text-[var(--text)]">{label}</label>
        <span className="text-[var(--text-sm)] text-[var(--text-muted)] tabular-nums">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        aria-label={label}
        className="w-full accent-[var(--accent)]"
      />
    </div>
  );
}

function ToggleControl({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <label className="text-[var(--text-sm)] font-medium text-[var(--text)]">{label}</label>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked ? "bg-[var(--accent)]" : "bg-[var(--surface-sunken)] border border-[var(--border)]"
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-[var(--surface)] shadow-[var(--shadow-xs)] transition-transform",
            checked ? "translate-x-6" : "translate-x-1"
          )}
        />
      </button>
    </div>
  );
}

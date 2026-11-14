"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  updatePreprocessing,
  previewPreprocessing,
  getPageImageUrl,
  getPreprocessingPreviewUrl,
  getThumbnailUrl,
  runOcr,
  rerunOcr,
  applyPreprocessingToAll,
  DEFAULT_PREPROCESSING_CONFIG,
  type PageResponse,
  type PreprocessingConfig,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/error-handler";
import { toast } from "sonner";
import { focusRing } from "@/lib/focus-ring";
import WorkflowShell from "@/components/shared/workflow-shell";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { getLanguageName } from "@/lib/utils";
import { WorkflowPageSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Toolbar, ToolbarGroup } from "@/components/shared/toolbar";
import { Field, Select } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import Image from "next/image";
import { ErrorState } from "@/components/shared/empty-state";
import JobProgressCard from "@/components/shared/job-progress-card";
import { useJobProgress } from "@/hooks/use-job-progress";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

function mergeConfig(page: PageResponse | undefined): PreprocessingConfig {
  return {
    ...DEFAULT_PREPROCESSING_CONFIG,
    ...(page?.preprocessing_config ?? {}),
  };
}

/**
 * Starting points, not guarantees. Each writes a partial config through the same
 * `updateConfig` path the sliders use, so every value stays editable afterwards.
 */
const PRESETS: {
  name: string;
  description: string;
  patch: Partial<PreprocessingConfig>;
}[] = [
  {
    name: "Original",
    description: "Turn every stage off",
    patch: {
      grayscale: false,
      brightness: 0,
      contrast: 0,
      binarization: null,
      deskew: false,
      denoise: false,
      rotation: 0,
      rotation_angle: 0,
    },
  },
  {
    name: "Standard scan",
    description: "Grayscale, deskew, trimmed borders, 300 DPI",
    patch: {
      grayscale: true,
      brightness: 0,
      contrast: 0,
      binarization: null,
      deskew: true,
      denoise: false,
      remove_borders: true,
      upscale_to_300dpi: true,
    },
  },
  {
    name: "Faded print",
    description: "Lift contrast and reduce noise",
    patch: {
      grayscale: true,
      brightness: 8,
      contrast: 25,
      denoise: true,
      deskew: true,
    },
  },
  {
    name: "High-contrast text",
    description: "Sauvola binarization for clean text extraction",
    patch: { grayscale: true, binarization: "sauvola", deskew: true },
  },
];

export default function PreprocessingPage() {
  useDocumentTitle("Preprocessing");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

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
  // Null means "not edited yet" — the effective config is seeded from the
  // selected page's persisted config. Editing sets a draft; switching pages
  // clears it so each page shows its own settings.
  const [draft, setDraft] = useState<PreprocessingConfig | null>(null);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [compareMode, setCompareMode] = useState<"current" | "preview">(
    "current",
  );
  const [confirmRerunOpen, setConfirmRerunOpen] = useState(false);
  const [bulkStartedAt, setBulkStartedAt] = useState<string | null>(null);
  const bulkCompletedRef = useRef(false);

  const bulkProgress = useJobProgress({
    bookId,
    jobType: "preprocessing",
    startedAt: bulkStartedAt,
    enabled: !!bookId && !!bulkStartedAt,
  });

  const currentPage = pages?.[selectedPageIndex];
  const baseConfig = mergeConfig(currentPage);
  const config = draft ?? baseConfig;
  const isDirty =
    draft !== null && JSON.stringify(draft) !== JSON.stringify(baseConfig);

  const updateConfig = (patch: Partial<PreprocessingConfig>) => {
    setDraft({ ...config, ...patch });
  };

  const previewMutation = useMutation({
    mutationFn: () => previewPreprocessing(currentPage!.id, config),
    onSuccess: () => {
      setPreviewVersion((v) => v + 1);
      setCompareMode("preview");
      toast.success("Preview rendered (not saved yet)");
    },
    onError: (err) => {
      toast.error(`Preview failed: ${getErrorMessage(err)}`);
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => updatePreprocessing(currentPage!.id, config),
    onSuccess: () => {
      setDraft(null);
      setPreviewVersion(0);
      setCompareMode("current");
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
      toast.success(`Settings applied to page ${currentPage?.page_number}`);
    },
    onError: (err) => {
      toast.error(`Preprocessing failed: ${getErrorMessage(err)}`);
    },
  });

  const applyToAllMutation = useMutation({
    mutationFn: () => applyPreprocessingToAll(bookId, config),
    onMutate: () => {
      bulkCompletedRef.current = false;
      setBulkStartedAt(new Date().toISOString());
    },
    onSuccess: () => {
      toast.info("Applying settings to all pages…");
    },
    onError: (err) => {
      setBulkStartedAt(null);
      toast.error(`Preprocessing failed: ${getErrorMessage(err)}`);
    },
  });

  useEffect(() => {
    if (!bulkStartedAt || !bulkProgress.isComplete || bulkCompletedRef.current) {
      return;
    }
    bulkCompletedRef.current = true;
    queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
    toast.success("Settings applied to all pages");
  }, [
    bulkStartedAt,
    bulkProgress.isComplete,
    bookId,
    queryClient,
  ]);

  const runOcrMutation = useMutation({
    // `run-ocr` only accepts a book in `pages_selected`; re-running an
    // already-OCR'd book must go to `rerun-ocr`, which resets the downstream
    // stages. Sending both to `run-ocr` made every re-run fail with 400.
    mutationFn: async () => {
      if (isRerun) {
        await rerunOcr(bookId);
        return;
      }
      await runOcr(bookId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      toast.info("OCR job started");
      router.push(`/books/${bookId}/ocr-processing`);
    },
    onError: (err) => {
      toast.error(`OCR failed to start: ${getErrorMessage(err)}`);
    },
  });

  if (isLoadingBook || isLoadingPages) {
    return <WorkflowPageSkeleton />;
  }

  if (!book || !pages || pages.length === 0 || !currentPage) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState
          title="No pages found"
          description="Please select pages first."
        />
      </div>
    );
  }

  const isRerun = [
    "ocr_running",
    "ocr_complete",
    "llm_running",
    "awaiting_review",
    "complete",
  ].includes(book.status);

  const selectPage = (idx: number) => {
    setSelectedPageIndex(idx);
    setDraft(null);
    setPreviewVersion(0);
    setCompareMode("current");
  };

  const handleRunOcr = () => {
    if (isRerun) {
      setConfirmRerunOpen(true);
      return;
    }
    runOcrMutation.mutate();
  };

  const previewSrc =
    compareMode === "preview" && previewVersion > 0
      ? `${getPreprocessingPreviewUrl(currentPage.id)}?v=${previewVersion}`
      : `${getPageImageUrl(currentPage.id)}?v=${previewVersion}`;

  return (
    <WorkflowShell bookId={bookId}>
      <PageContainer layout="workspace">
        <PageHeader
          eyebrow="Image Preprocessing"
          title={book.title || book.filename}
          description={
            <>
              Language: {getLanguageName(book.language)} &bull; {pages.length}{" "}
              pages
            </>
          }
        />

        <Toolbar className="mb-4">
          <ToolbarGroup>
            <span className="mr-1 text-[var(--text-xs)] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Presets
            </span>
            {PRESETS.map((preset) => (
              <Button
                key={preset.name}
                variant="outline"
                size="sm"
                title={preset.description}
                onClick={() => updateConfig(preset.patch)}
              >
                {preset.name}
              </Button>
            ))}
          </ToolbarGroup>
          <ToolbarGroup align="end">
            <span className="text-[var(--text-xs)] text-[var(--text-muted)]">
              Presets set sliders — nothing is applied until you click Apply.
            </span>
          </ToolbarGroup>
        </Toolbar>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-2">
            <Card title="Pages" description="Click a thumbnail to preview." flush>
              <div className="grid grid-cols-3 lg:grid-cols-2 gap-2 max-h-[600px] overflow-y-auto">
                {pages.map((page, idx) => {
                  const processed =
                    page.has_processed_image || !!page.preprocessing_config;
                  return (
                    <button
                      key={page.id}
                      onClick={() => selectPage(idx)}
                      aria-label={`Select page ${page.page_number}${processed ? ", processed" : ""}`}
                      aria-current={idx === selectedPageIndex ? "true" : undefined}
                      className={cn(
                        "relative aspect-[3/4] rounded-[var(--radius)] overflow-hidden border-2 transition-all",
                        focusRing,
                        idx === selectedPageIndex
                          ? "border-[var(--accent-ring)] ring-2 ring-[var(--accent-ring)]/30"
                          : "border-[var(--border)] hover:border-[var(--border-strong)]",
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
                      {processed && (
                        <span className="absolute top-1 right-1 rounded-full bg-[var(--success-600)] px-1.5 py-0.5 text-[9px] font-semibold text-[var(--text-inverse)]">
                          ✓
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </Card>
          </div>

          <div className="lg:col-span-6">
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                  Page {currentPage.page_number} &mdash;{" "}
                  {compareMode === "preview" ? "Preview" : "Current"}
                </h3>
                <div className="flex items-center gap-2">
                  {previewVersion > 0 && (
                    <div className="flex rounded-[var(--radius)] border border-[var(--border)] p-0.5">
                      <Button
                        size="sm"
                        variant={compareMode === "current" ? "secondary" : "ghost"}
                        onClick={() => setCompareMode("current")}
                      >
                        Current
                      </Button>
                      <Button
                        size="sm"
                        variant={compareMode === "preview" ? "secondary" : "ghost"}
                        onClick={() => setCompareMode("preview")}
                      >
                        Preview
                      </Button>
                    </div>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => selectPage(Math.max(0, selectedPageIndex - 1))}
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
                    onClick={() =>
                      selectPage(Math.min(pages.length - 1, selectedPageIndex + 1))
                    }
                    disabled={selectedPageIndex === pages.length - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>

              <div className="border border-[var(--border)] rounded-[var(--radius)] bg-[var(--surface-sunken)] flex items-center justify-center min-h-[400px]">
                <Image
                  key={previewSrc}
                  src={previewSrc}
                  alt={`Page ${currentPage.page_number}`}
                  width={1200}
                  height={1600}
                  sizes="(min-width: 1024px) 50vw, 100vw"
                  className="max-w-full max-h-[600px] w-auto h-auto object-contain"
                  unoptimized
                />
              </div>

              {previewVersion > 0 && compareMode === "preview" && (
                <p className="mt-2 text-[var(--text-xs)] text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                  This preview is not saved. Click Apply to commit it to the
                  page.
                </p>
              )}
              {currentPage.has_processed_image && compareMode === "current" && (
                <p className="mt-2 text-[var(--text-xs)] text-[var(--success-700)] dark:text-[var(--success-100)]">
                  This page has saved preprocessing applied.
                </p>
              )}
            </Card>
          </div>

          <div className="lg:col-span-4">
            <Card
              title="Preprocessing Settings"
              description="Tune the image processing pipeline."
              headerAction={
                isDirty ? (
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                    Unsaved
                  </span>
                ) : undefined
              }
            >
              <Stack gap={4}>
                <CollapsibleSection title="Rotate" defaultOpen>
                <div className="space-y-4">
                <div>
                  <p className="mb-1 text-[var(--text-sm)] font-medium text-[var(--text)]">
                    Rotation
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        updateConfig({
                          rotation: (((config.rotation ?? 0) - 90) % 360 + 360) % 360,
                        })
                      }
                      aria-label="Rotate 90 degrees counter-clockwise"
                    >
                      ↺ 90°
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        updateConfig({
                          rotation: (((config.rotation ?? 0) + 90) % 360 + 360) % 360,
                        })
                      }
                      aria-label="Rotate 90 degrees clockwise"
                    >
                      ↻ 90°
                    </Button>
                    <span className="text-[var(--text-sm)] text-[var(--text-muted)] tabular-nums">
                      {(config.rotation ?? 0)}°
                    </span>
                    {!!config.rotation && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => updateConfig({ rotation: 0 })}
                      >
                        Reset rotation
                      </Button>
                    )}
                  </div>
                  <div className="mt-3">
                    <SliderControl
                      label="Fine angle"
                      value={config.rotation_angle ?? 0}
                      min={-15}
                      max={15}
                      step={0.5}
                      onChange={(v) => updateConfig({ rotation_angle: v })}
                      formatValue={(v) => `${v.toFixed(1)}°`}
                    />
                  </div>
                </div>

                </div>
                </CollapsibleSection>

                <CollapsibleSection title="Enhance" defaultOpen>
                <div className="space-y-4">
                <ToggleControl
                  label="Grayscale"
                  checked={config.grayscale}
                  onChange={(v) => updateConfig({ grayscale: v })}
                />

                <SliderControl
                  label="Brightness"
                  value={config.brightness}
                  min={-100}
                  max={100}
                  onChange={(v) => updateConfig({ brightness: v })}
                />

                <SliderControl
                  label="Contrast"
                  value={config.contrast}
                  min={-100}
                  max={100}
                  onChange={(v) => updateConfig({ contrast: v })}
                />

                </div>
                </CollapsibleSection>

                <CollapsibleSection title="Binarize" defaultOpen>
                <div className="space-y-4">
                <Field label="Binarization">
                  <Select
                    value={config.binarization || "none"}
                    onChange={(e) =>
                      updateConfig({
                        binarization:
                          e.target.value === "none"
                            ? null
                            : (e.target.value as "otsu" | "adaptive" | "sauvola"),
                      })
                    }
                  >
                    <option value="none">None</option>
                    <option value="otsu">Otsu</option>
                    <option value="adaptive">Adaptive</option>
                    <option value="sauvola">Sauvola</option>
                  </Select>
                </Field>

                {config.binarization === "adaptive" && (
                  <>
                    <SliderControl
                      label="Adaptive Block Size"
                      value={config.adaptive_block_size}
                      min={3}
                      max={51}
                      onChange={(v) => updateConfig({ adaptive_block_size: v })}
                    />
                    <SliderControl
                      label="Adaptive C"
                      value={config.adaptive_c}
                      min={-10}
                      max={10}
                      onChange={(v) => updateConfig({ adaptive_c: v })}
                    />
                  </>
                )}

                {config.binarization === "sauvola" && (
                  <>
                    <SliderControl
                      label="Sauvola Window"
                      value={config.sauvola_window ?? 25}
                      min={3}
                      max={75}
                      step={2}
                      onChange={(v) => updateConfig({ sauvola_window: v })}
                    />
                    <SliderControl
                      label="Sauvola K"
                      value={config.sauvola_k ?? 0.2}
                      min={0}
                      max={1}
                      step={0.05}
                      onChange={(v) => updateConfig({ sauvola_k: v })}
                      formatValue={(v) => v.toFixed(2)}
                    />
                  </>
                )}

                </div>
                </CollapsibleSection>

                <CollapsibleSection title="Cleanup" defaultOpen>
                <div className="space-y-4">
                <ToggleControl
                  label="Deskew"
                  checked={config.deskew}
                  onChange={(v) => updateConfig({ deskew: v })}
                />

                <ToggleControl
                  label="Denoise"
                  checked={config.denoise}
                  onChange={(v) => updateConfig({ denoise: v })}
                />

                {config.denoise && (
                  <SliderControl
                    label="Denoise Strength"
                    value={config.denoise_strength}
                    min={1}
                    max={50}
                    onChange={(v) => updateConfig({ denoise_strength: v })}
                  />
                )}

                </div>
                </CollapsibleSection>

                <CollapsibleSection title="Advanced" defaultOpen={false}>
                  <Stack gap={3}>
                    <ToggleControl
                      label="Upscale to 300 DPI"
                      checked={config.upscale_to_300dpi ?? true}
                      onChange={(v) => updateConfig({ upscale_to_300dpi: v })}
                    />
                    <ToggleControl
                      label="Remove borders"
                      checked={config.remove_borders ?? true}
                      onChange={(v) => updateConfig({ remove_borders: v })}
                    />
                    {(config.remove_borders ?? true) && (
                      <SliderControl
                        label="Border content ratio"
                        value={Math.round((config.border_content_ratio ?? 0.85) * 100)}
                        min={50}
                        max={100}
                        onChange={(v) =>
                          updateConfig({ border_content_ratio: v / 100 })
                        }
                        formatValue={(v) => `${v}%`}
                      />
                    )}
                    <ToggleControl
                      label="Auto preprocess"
                      checked={config.auto_preprocess ?? true}
                      onChange={(v) => updateConfig({ auto_preprocess: v })}
                    />
                  </Stack>
                </CollapsibleSection>

                {bulkStartedAt &&
                  (bulkProgress.isRunning || bulkProgress.isFailed) && (
                    <JobProgressCard
                      title="Applying to all pages"
                      progress={bulkProgress.progress}
                      status={bulkProgress.job?.status ?? "queued"}
                      phase={`Applying settings across ${pages.length} pages`}
                      elapsedMs={bulkProgress.elapsedMs}
                      error={bulkProgress.errorLog}
                      onCancel={bulkProgress.cancel}
                      cancelling={bulkProgress.cancelling}
                    />
                  )}

                <div className="pt-3 border-t border-[var(--border)] space-y-3">
                  <Button
                    variant="outline"
                    onClick={() => previewMutation.mutate()}
                    disabled={previewMutation.isPending}
                    loading={previewMutation.isPending}
                    className="w-full"
                  >
                    {previewMutation.isPending ? "Rendering..." : "Preview"}
                  </Button>

                  <Button
                    onClick={() => applyMutation.mutate()}
                    disabled={applyMutation.isPending || !isDirty}
                    loading={applyMutation.isPending}
                    className="w-full"
                  >
                    {applyMutation.isPending
                      ? "Applying..."
                      : "Apply to this page"}
                  </Button>

                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDraft({ ...DEFAULT_PREPROCESSING_CONFIG })}
                      className="flex-1"
                    >
                      Reset to defaults
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => applyToAllMutation.mutate()}
                      disabled={applyToAllMutation.isPending || bulkProgress.isRunning}
                      loading={applyToAllMutation.isPending || bulkProgress.isRunning}
                      className="flex-1"
                    >
                      {applyToAllMutation.isPending || bulkProgress.isRunning
                        ? "Applying..."
                        : "Apply to all pages"}
                    </Button>
                  </div>

                  <Button
                    onClick={handleRunOcr}
                    disabled={runOcrMutation.isPending}
                    loading={runOcrMutation.isPending}
                    className="w-full"
                  >
                    {runOcrMutation.isPending
                      ? "Starting OCR..."
                      : isRerun
                        ? "Re-run OCR on All Pages"
                        : "Run OCR on All Pages"}
                  </Button>

                  {runOcrMutation.isError && (
                    <ErrorState
                      title="OCR failed"
                      description={getErrorMessage(runOcrMutation.error)}
                    />
                  )}
                </div>
              </Stack>
            </Card>
          </div>
        </div>

        <ConfirmDialog
          open={confirmRerunOpen}
          onClose={() => setConfirmRerunOpen(false)}
          onConfirm={() => {
            setConfirmRerunOpen(false);
            runOcrMutation.mutate();
          }}
          title="Re-run OCR on all pages?"
          description={
            <ul className="list-disc pl-4 space-y-1">
              <li>
                Existing OCR text for {pages.length} page
                {pages.length === 1 ? "" : "s"} will be discarded.
              </li>
              <li>
                OCR review, LLM extraction, and metadata review will be reset.
              </li>
              <li>
                Extracted metadata text is kept but marked out of date until you
                re-run extraction.
              </li>
              <li>Your per-page preprocessing settings are kept.</li>
            </ul>
          }
          confirmLabel="Re-run OCR"
          variant="warning"
          loading={runOcrMutation.isPending}
        />
      </PageContainer>
    </WorkflowShell>
  );
}

function SliderControl({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  formatValue,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  formatValue?: (v: number) => string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[var(--text-sm)] font-medium text-[var(--text)]">
          {label}
        </label>
        <span className="text-[var(--text-sm)] text-[var(--text-muted)] tabular-nums">
          {formatValue ? formatValue(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
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
      <label className="text-[var(--text-sm)] font-medium text-[var(--text)]">
        {label}
      </label>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked
            ? "bg-[var(--accent)]"
            : "bg-[var(--surface-sunken)] border border-[var(--border)]",
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-[var(--surface)] shadow-[var(--shadow-xs)] transition-transform",
            checked ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}
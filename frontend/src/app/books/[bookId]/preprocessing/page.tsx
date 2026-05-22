"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBook,
  getBookPages,
  updatePreprocessing,
  getPageImageUrl,
  runOcr,
  DEFAULT_PREPROCESSING_CONFIG,
  type PreprocessingConfig,
} from "@/lib/api";
import { useJobPolling } from "@/hooks/use-job-polling";
import { getErrorMessage } from "@/lib/error-handler";

export default function PreprocessingPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
  });

  const { data: pages, isLoading: isLoadingPages } = useQuery({
    queryKey: ["book", bookId, "pages"],
    queryFn: () => getBookPages(bookId),
    enabled: !!bookId,
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
    },
  });

  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const runOcrMutation = useMutation({
    mutationFn: () => runOcr(bookId),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      setActiveJobId(job.id);
    },
  });

  const { isComplete, isFailed, progress, isPolling, errorLog } = useJobPolling({
    bookId,
    jobId: activeJobId ?? undefined,
    enabled: !!activeJobId,
  });

  useEffect(() => {
    if (activeJobId && isComplete) {
      router.push(`/books/${bookId}/ocr-review?jobId=${activeJobId}`);
    }
  }, [activeJobId, isComplete, bookId, router]);

  if (isLoadingBook || isLoadingPages) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!book || !pages || pages.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">No pages found. Please select pages first.</p>
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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Image Preprocessing
          </h1>
          <p className="text-gray-600">
            {book.title || book.filename} &bull; Language:{" "}
            {book.language === "tel" ? "Telugu" : "Hindi"} &bull;{" "}
            {pages.length} pages
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-2">
            <div className="bg-white shadow rounded-lg p-3">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Pages</h3>
              <div className="grid grid-cols-3 lg:grid-cols-2 gap-2 max-h-[600px] overflow-y-auto">
                {pages.map((page, idx) => (
                  <button
                    key={page.id}
                    onClick={() => {
                      setSelectedPageIndex(idx);
                      setPreviewKey((k) => k + 1);
                    }}
                    className={`aspect-[3/4] rounded border-2 overflow-hidden ${
                      idx === selectedPageIndex
                        ? "border-blue-500 ring-2 ring-blue-200"
                        : "border-gray-200 hover:border-gray-400"
                    }`}
                  >
                    <div className="w-full h-full bg-gray-100 flex items-center justify-center text-xs text-gray-600">
                      {page.page_number}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="bg-white shadow rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-700">
                  Page {currentPage.page_number} &mdash; Preview
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handlePrevPage}
                    disabled={selectedPageIndex === 0}
                    className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-500">
                    {selectedPageIndex + 1} / {pages.length}
                  </span>
                  <button
                    onClick={handleNextPage}
                    disabled={selectedPageIndex === pages.length - 1}
                    className="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>

              <div className="border rounded bg-gray-100 flex items-center justify-center min-h-[400px]">
                <img
                  key={previewKey}
                  src={getPageImageUrl(currentPage.id)}
                  alt={`Page ${currentPage.page_number}`}
                  className="max-w-full max-h-[600px] object-contain"
                />
              </div>

              {currentPage.preprocessing_config && (
                <p className="mt-2 text-xs text-green-600">
                  Custom preprocessing applied to this page
                </p>
              )}
            </div>
          </div>

          <div className="lg:col-span-4">
            <div className="bg-white shadow rounded-lg p-4 space-y-4">
              <h3 className="text-sm font-medium text-gray-700">
                Preprocessing Settings
              </h3>

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

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Binarization
                </label>
                <select
                  value={config.binarization || "none"}
                  onChange={(e) =>
                    handleConfigChange(
                      "binarization",
                      e.target.value === "none"
                        ? null
                        : (e.target.value as "otsu" | "adaptive")
                    )
                  }
                  className="w-full border rounded px-3 py-2 text-sm"
                >
                  <option value="none">None</option>
                  <option value="otsu">Otsu</option>
                  <option value="adaptive">Adaptive</option>
                </select>
              </div>

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

              <div className="pt-3 border-t space-y-3">
                <button
                  onClick={handlePreview}
                  disabled={preprocessingMutation.isPending}
                  className="w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {preprocessingMutation.isPending
                    ? "Processing..."
                    : "Preview Current Page"}
                </button>

                <button
                  onClick={() => applyToAllMutation.mutate()}
                  disabled={applyToAllMutation.isPending}
                  className="w-full px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {applyToAllMutation.isPending
                    ? "Applying..."
                    : "Apply to All Pages"}
                </button>

                <button
                  onClick={() => runOcrMutation.mutate()}
                  disabled={runOcrMutation.isPending || !!activeJobId}
                  className="w-full px-4 py-2 text-sm font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {runOcrMutation.isPending
                    ? "Starting OCR..."
                    : isPolling
                      ? `Running OCR... ${Math.round(progress)}%`
                      : "Run OCR on All Pages"}
                </button>

                {isPolling && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-green-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.round(progress)}%` }}
                    />
                  </div>
                )}

                {(runOcrMutation.isError || (isFailed && errorLog)) && (
                  <p className="text-sm text-red-600">
                    {runOcrMutation.isError
                      ? getErrorMessage(runOcrMutation.error)
                      : `OCR failed: ${errorLog}`}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
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
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm text-gray-500">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full"
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
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? "bg-blue-600" : "bg-gray-300"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

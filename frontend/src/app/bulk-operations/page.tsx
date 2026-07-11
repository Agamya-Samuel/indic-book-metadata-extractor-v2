"use client";

import { useState, useCallback, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getBulkStats,
  bulkExport,
  bulkImport,
  bulkExportWikibase,
  getFilterOptions,
  type BulkStatsResponse,
  type BulkImportResult,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";

export default function BulkOperationsPage() {
  const [exportLanguage, setExportLanguage] = useState<string>("");
  const [exportStatus, setExportStatus] = useState<string>("");
  const [importMode, setImportMode] = useState<"merge" | "overwrite">("merge");
  const [importResult, setImportResult] = useState<BulkImportResult | null>(null);
  const [wikibaseLanguage, setWikibaseLanguage] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["bulk-stats"],
    queryFn: getBulkStats,
    staleTime: 30 * 1000,
  });

  // Filter options
  const { data: filterOptions } = useQuery({
    queryKey: ["library-filters"],
    queryFn: getFilterOptions,
    staleTime: 2 * 60 * 1000,
  });

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: async () => {
      const blob = await bulkExport({
        language: exportLanguage || undefined,
        status: exportStatus || undefined,
      });
      return blob;
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `metadata_export_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Metadata exported successfully");
    },
    onError: (error: Error) => {
      toast.error(`Export failed: ${error.message}`);
    },
  });

  // Import mutation
  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      return await bulkImport(file, importMode);
    },
    onSuccess: (result) => {
      setImportResult(result);
      toast.success(
        `Imported: ${result.books_updated} books updated, ${result.fields_changed} fields changed`
      );
    },
    onError: (error: Error) => {
      toast.error(`Import failed: ${error.message}`);
    },
  });

  // Wikibase export mutation
  const wikibaseMutation = useMutation({
    mutationFn: async () => {
      const blob = await bulkExportWikibase({
        language: wikibaseLanguage || undefined,
      });
      return blob;
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `wikibase_quickstatements_${new Date().toISOString().slice(0, 10)}.tsv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("QuickStatements file downloaded");
    },
    onError: (error: Error) => {
      toast.error(`Wikibase export failed: ${error.message}`);
    },
  });

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        importMutation.mutate(file);
        // Reset input so the same file can be re-selected
        e.target.value = "";
      }
    },
    [importMutation]
  );

  const languages = filterOptions?.languages ?? ["tel", "hin", "eng"];
  const statuses = filterOptions?.statuses ?? [
    "uploaded",
    "pages_selected",
    "ocr_running",
    "ocr_complete",
    "llm_running",
    "complete",
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Bulk Operations
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Export metadata for bulk cleaning in OpenRefine, import cleaned
            data, or generate Wikibase QuickStatements.
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
        {/* External service links */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {process.env.NEXT_PUBLIC_OPENREFINE_URL && (
            <a
              href={process.env.NEXT_PUBLIC_OPENREFINE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 hover:border-green-500 dark:hover:border-green-500 transition-colors group"
            >
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 group-hover:text-green-600 dark:group-hover:text-green-400">
                  Open OpenRefine ↗
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Clean and standardize metadata in the browser
                </div>
              </div>
            </a>
          )}
          {process.env.NEXT_PUBLIC_WIKIBASE_URL && (
            <a
              href={process.env.NEXT_PUBLIC_WIKIBASE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 hover:border-purple-500 dark:hover:border-purple-500 transition-colors group"
            >
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 group-hover:text-purple-600 dark:group-hover:text-purple-400">
                  Open Wikibase ↗
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  View and edit structured bibliographic data
                </div>
              </div>
            </a>
          )}
        </div>

        {/* Stats card */}
        {stats && <StatsCard stats={stats} isLoading={statsLoading} />}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Export card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              Export to CSV
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Download all book metadata as CSV for cleaning in OpenRefine.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Language
                </label>
                <select
                  value={exportLanguage}
                  onChange={(e) => setExportLanguage(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                >
                  <option value="">All Languages</option>
                  {languages.map((l) => (
                    <option key={l} value={l}>
                      {getLanguageName(l)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Status
                </label>
                <select
                  value={exportStatus}
                  onChange={(e) => setExportStatus(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                >
                  <option value="">All Statuses</option>
                  {statuses.map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => exportMutation.mutate()}
                disabled={exportMutation.isPending}
                className="w-full px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exportMutation.isPending ? "Exporting..." : "Download CSV"}
              </button>
            </div>
          </div>

          {/* Import card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              Import from CSV
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Upload a cleaned CSV from OpenRefine to update metadata.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Import Mode
                </label>
                <select
                  value={importMode}
                  onChange={(e) =>
                    setImportMode(e.target.value as "merge" | "overwrite")
                  }
                  className="w-full px-3 py-1.5 border rounded text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                >
                  <option value="merge">
                    Merge — only update provided fields
                  </option>
                  <option value="overwrite">
                    Overwrite — replace all metadata fields
                  </option>
                </select>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={importMutation.isPending}
                className="w-full px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {importMutation.isPending ? "Importing..." : "Upload CSV"}
              </button>

              {importResult && (
                <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1 bg-gray-50 dark:bg-gray-700 rounded p-2">
                  <p>Rows: {importResult.total_rows}</p>
                  <p>Books updated: {importResult.books_updated}</p>
                  <p>Fields changed: {importResult.fields_changed}</p>
                  {importResult.books_not_found > 0 && (
                    <p className="text-amber-600">
                      Not found: {importResult.books_not_found}
                    </p>
                  )}
                  {importResult.errors.length > 0 && (
                    <p className="text-red-600">
                      {importResult.errors.length} error(s)
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Wikibase export card */}
          <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              Wikibase Export
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Generate QuickStatements TSV for uploading to Wikibase.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Language
                </label>
                <select
                  value={wikibaseLanguage}
                  onChange={(e) => setWikibaseLanguage(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                >
                  <option value="">All Languages</option>
                  {languages.map((l) => (
                    <option key={l} value={l}>
                      {getLanguageName(l)}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => wikibaseMutation.mutate()}
                disabled={wikibaseMutation.isPending}
                className="w-full px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {wikibaseMutation.isPending
                  ? "Generating..."
                  : "Download QuickStatements"}
              </button>
            </div>
          </div>
        </div>

        {/* Workflow guide */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Workflow Guide
          </h2>
          <ol className="text-sm text-gray-600 dark:text-gray-400 space-y-2 list-decimal list-inside">
            <li>
              <strong>Export</strong> — Download metadata as CSV with filters
              applied.
            </li>
            <li>
              <strong>Open in OpenRefine</strong> — Import the CSV into{" "}
              <a
                href={process.env.NEXT_PUBLIC_OPENREFINE_URL || "http://localhost:3333"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                OpenRefine
              </a>.
            </li>
            <li>
              <strong>Clean & standardize</strong> — Use clustering to fix
              publisher names, author spellings, place names, etc.
            </li>
            <li>
              <strong>Export from OpenRefine</strong> — Download cleaned data as
              CSV.
            </li>
            <li>
              <strong>Import</strong> — Upload the cleaned CSV back here to
              update metadata.
            </li>
            <li>
              <strong>Wikibase</strong> — Generate QuickStatements and upload to
              Wikibase via{" "}
              <a
                href="https://quickstatements.toolforge.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                QuickStatements
              </a>
              .
            </li>
          </ol>
        </div>
      </div>
    </div>
  );
}

function StatsCard({
  stats,
  isLoading,
}: {
  stats: BulkStatsResponse;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5 animate-pulse">
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-3" />
        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3" />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-5">
      <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
        Library Summary
      </h2>
      <div className="flex flex-wrap gap-6 text-sm">
        <div>
          <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {stats.total_books}
          </span>
          <span className="ml-1 text-gray-500 dark:text-gray-400">
            total books
          </span>
        </div>
        <div>
          <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {stats.books_with_metadata}
          </span>
          <span className="ml-1 text-gray-500 dark:text-gray-400">
            with metadata
          </span>
        </div>
        {Object.entries(stats.languages).map(([lang, count]) => (
          <div key={lang}>
            <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {count}
            </span>
            <span className="ml-1 text-gray-500 dark:text-gray-400">
              {getLanguageName(lang)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

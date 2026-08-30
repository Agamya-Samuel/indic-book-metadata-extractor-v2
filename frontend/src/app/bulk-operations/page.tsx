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
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function BulkOperationsPage() {
  useDocumentTitle("Bulk operations");
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
    <div className="min-h-screen bg-[var(--background)]">
      <PageContainer>
        <PageHeader
          title="Bulk Operations"
          description="Export metadata for bulk cleaning in OpenRefine, import cleaned data, or generate Wikibase QuickStatements."
        />

        <Stack gap={6}>
          {/* External service links */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {process.env.NEXT_PUBLIC_OPENREFINE_URL && (
              <a
                href={process.env.NEXT_PUBLIC_OPENREFINE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4 hover:border-[var(--success-500)] transition-colors group"
              >
                <div className="shrink-0 w-10 h-10 rounded-[var(--radius)] bg-[var(--success-50)] dark:bg-[var(--success-900)]/20 flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--success-700)] dark:text-[var(--success-100)]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                </div>
                <div>
                  <div className="text-[var(--text-sm)] font-semibold text-[var(--text)] group-hover:text-[var(--success-700)] dark:group-hover:text-[var(--success-100)]">
                    Open OpenRefine ↗
                  </div>
                  <div className="text-[var(--text-xs)] text-[var(--text-muted)]">
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
                className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4 hover:border-[var(--accent-soft-text)] transition-colors group"
              >
                <div className="shrink-0 w-10 h-10 rounded-[var(--radius)] bg-[var(--accent-soft)] flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--accent-soft-text)]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                  </svg>
                </div>
                <div>
                  <div className="text-[var(--text-sm)] font-semibold text-[var(--text)] group-hover:text-[var(--accent-soft-text)]">
                    Open Wikibase ↗
                  </div>
                  <div className="text-[var(--text-xs)] text-[var(--text-muted)]">
                    View and edit structured bibliographic data
                  </div>
                </div>
              </a>
            )}
          </div>

          {/* Stats card */}
          {stats && <StatsCard stats={stats} isLoading={statsLoading} />}

          {/* Bulk operations flow — three steps in a single row.
              The order is: Export CSV (down) → OpenRefine (offline) → Import CSV (up)
              → Export QuickStatements → upload to Wikibase. The cards in this row
              are the in-app steps; the flow header names the full pipeline. */}
          <div>
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-[var(--text-sm)] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Bulk cleaning pipeline
              </h2>
              <p className="text-[var(--text-xs)] text-[var(--text-subtle)]">
                Export · Clean in OpenRefine · Re-import
              </p>
            </div>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {/* Export card */}
              <Card
                title={
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-[10px] font-bold tabular-nums text-[var(--text-inverse)]"
                    >
                      1
                    </span>
                    <span>Export to CSV</span>
                  </span>
                }
                description="Download all book metadata as CSV for cleaning in OpenRefine."
              >
              <Stack gap={3}>
                <Field label="Language">
                  <Select
                    value={exportLanguage}
                    onChange={(e) => setExportLanguage(e.target.value)}
                    aria-label="Filter export by language"
                  >
                    <option value="">All Languages</option>
                    {languages.map((l) => (
                      <option key={l} value={l}>
                        {getLanguageName(l)}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Field label="Status">
                  <Select
                    value={exportStatus}
                    onChange={(e) => setExportStatus(e.target.value)}
                    aria-label="Filter export by status"
                  >
                    <option value="">All Statuses</option>
                    {statuses.map((s) => (
                      <option key={s} value={s}>
                        {s.replace(/_/g, " ")}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Button
                  onClick={() => exportMutation.mutate()}
                  loading={exportMutation.isPending}
                  className="w-full"
                >
                  {exportMutation.isPending ? "Exporting..." : "Download CSV"}
                </Button>
              </Stack>
            </Card>

            {/* Import card */}
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-[10px] font-bold tabular-nums text-[var(--text-inverse)]"
                  >
                    2
                  </span>
                  <span>Import from CSV</span>
                </span>
              }
              description="Upload a cleaned CSV from OpenRefine to update metadata."
            >
              <Stack gap={3}>
                <Field label="Import Mode">
                  <Select
                    value={importMode}
                    onChange={(e) =>
                      setImportMode(e.target.value as "merge" | "overwrite")
                    }
                    aria-label="Import mode"
                  >
                    <option value="merge">
                      Merge — only update provided fields
                    </option>
                    <option value="overwrite">
                      Overwrite — replace all metadata fields
                    </option>
                  </Select>
                </Field>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <Button
                  variant="secondary"
                  onClick={() => fileInputRef.current?.click()}
                  loading={importMutation.isPending}
                  className="w-full"
                >
                  {importMutation.isPending ? "Importing..." : "Upload CSV"}
                </Button>

                {importResult && (
                  <div className="text-[var(--text-xs)] text-[var(--text-muted)] space-y-1 bg-[var(--surface-sunken)] rounded-[var(--radius)] p-2">
                    <p>Rows: {importResult.total_rows}</p>
                    <p>Books updated: {importResult.books_updated}</p>
                    <p>Fields changed: {importResult.fields_changed}</p>
                    {importResult.books_not_found > 0 && (
                      <p className="text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                        Not found: {importResult.books_not_found}
                      </p>
                    )}
                    {importResult.errors.length > 0 && (
                      <p className="text-[var(--danger-700)] dark:text-[var(--danger-100)]">
                        {importResult.errors.length} error(s)
                      </p>
                    )}
                  </div>
                )}
              </Stack>
            </Card>

            {/* Wikibase export card */}
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-[10px] font-bold tabular-nums text-[var(--text-inverse)]"
                  >
                    3
                  </span>
                  <span>Wikibase export</span>
                </span>
              }
              description="Generate QuickStatements TSV for uploading to Wikibase."
            >
              <Stack gap={3}>
                <Field label="Language">
                  <Select
                    value={wikibaseLanguage}
                    onChange={(e) => setWikibaseLanguage(e.target.value)}
                    aria-label="Filter Wikibase export by language"
                  >
                    <option value="">All Languages</option>
                    {languages.map((l) => (
                      <option key={l} value={l}>
                        {getLanguageName(l)}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Button
                  variant="secondary"
                  onClick={() => wikibaseMutation.mutate()}
                  loading={wikibaseMutation.isPending}
                  className="w-full"
                >
                  {wikibaseMutation.isPending
                    ? "Generating..."
                    : "Download QuickStatements"}
                </Button>
              </Stack>
            </Card>
            </div>
          </div>

          {/* Workflow guide */}
          <Card title="Workflow Guide" description="The recommended bulk-cleaning flow.">
            <ol className="text-[var(--text-sm)] text-[var(--text-muted)] space-y-2 list-decimal list-inside">
              <li>
                <strong className="text-[var(--text)]">Export</strong> — Download metadata as CSV with filters applied.
              </li>
              <li>
                <strong className="text-[var(--text)]">Open in OpenRefine</strong> — Import the CSV into{" "}
                <a
                  href={process.env.NEXT_PUBLIC_OPENREFINE_URL || "http://localhost:3333"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--accent)] hover:underline"
                >
                  OpenRefine
                </a>.
              </li>
              <li>
                <strong className="text-[var(--text)]">Clean & standardize</strong> — Use clustering to fix publisher names, author spellings, place names, etc.
              </li>
              <li>
                <strong className="text-[var(--text)]">Export from OpenRefine</strong> — Download cleaned data as CSV.
              </li>
              <li>
                <strong className="text-[var(--text)]">Import</strong> — Upload the cleaned CSV back here to update metadata.
              </li>
              <li>
                <strong className="text-[var(--text)]">Wikibase</strong> — Generate QuickStatements and upload to Wikibase via{" "}
                <a
                  href="https://quickstatements.toolforge.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--accent)] hover:underline"
                >
                  QuickStatements
                </a>
                .
              </li>
            </ol>
          </Card>
        </Stack>
      </PageContainer>
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
      <Card>
        <div className="space-y-3 animate-pulse">
          <div className="h-4 bg-[var(--surface-sunken)] rounded-[var(--radius-sm)] w-1/3" />
          <div className="h-3 bg-[var(--surface-sunken)] rounded-[var(--radius-sm)] w-2/3" />
        </div>
      </Card>
    );
  }

  return (
    <Card title="Library Summary" description="Snapshot of book counts and language distribution.">
      <div className="flex flex-wrap gap-6 text-[var(--text-sm)]">
        <div>
          <span className="text-[var(--text-2xl)] font-bold text-[var(--text)]">
            {stats.total_books}
          </span>
          <span className="ml-1 text-[var(--text-muted)]">
            total books
          </span>
        </div>
        <div>
          <span className="text-[var(--text-2xl)] font-bold text-[var(--text)]">
            {stats.books_with_metadata}
          </span>
          <span className="ml-1 text-[var(--text-muted)]">
            with metadata
          </span>
        </div>
        {Object.entries(stats.languages).map(([lang, count]) => (
          <div key={lang}>
            <span className="text-[var(--text-lg)] font-semibold text-[var(--text)]">
              {count}
            </span>
            <span className="ml-1 text-[var(--text-muted)]">
              {getLanguageName(lang)}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

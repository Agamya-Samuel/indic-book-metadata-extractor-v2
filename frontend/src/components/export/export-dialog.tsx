"use client";

import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/shared/button";
import {
  exportMetadata,
  type ExportFormat,
  type ExportParams,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/error-handler";
import { downloadBlob, filenameFromDisposition } from "@/lib/download";
import { cn } from "@/lib/utils";

export interface ExportScope {
  bookIds?: string[];
  language?: string;
  status?: string;
  ownerId?: string;
}

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  scope: ExportScope;
  /** Number of eligible books the scope will export. */
  bookCount: number;
  title?: string;
  description?: React.ReactNode;
}

const FORMATS: Array<{
  value: ExportFormat;
  label: string;
  description: string;
}> = [
  {
    value: "csv",
    label: "CSV",
    description: "One row per book. Opens in any spreadsheet.",
  },
  {
    value: "xlsx",
    label: "Excel (XLSX)",
    description: "Readable headers, frozen header row, column filters.",
  },
  {
    value: "json",
    label: "JSON",
    description: "Array of records for integrations and scripts.",
  },
  {
    value: "jsonl",
    label: "JSONL",
    description: "One JSON object per line for datasets and evaluation.",
  },
  {
    value: "wikibase",
    label: "Wikibase JSON",
    description: "Entity claims keyed by the local property IDs.",
  },
  {
    value: "openrefine",
    label: "OpenRefine CSV",
    description: "Machine headers and book_id, ready to re-import.",
  },
];

const EXTENSIONS: Record<ExportFormat, string> = {
  csv: "csv",
  xlsx: "xlsx",
  json: "json",
  jsonl: "jsonl",
  wikibase: "wikibase.json",
  openrefine: "csv",
};

const FORMAT_LABELS: Record<ExportFormat, string> = {
  csv: "CSV",
  xlsx: "Excel",
  json: "JSON",
  jsonl: "JSONL",
  wikibase: "Wikibase JSON",
  openrefine: "OpenRefine CSV",
};

export function ExportDialog({
  open,
  onClose,
  scope,
  bookCount,
  title = "Export metadata",
  description,
}: ExportDialogProps) {
  const ref = React.useRef<HTMLDialogElement | null>(null);
  const titleId = React.useId();
  const descriptionId = React.useId();

  const [format, setFormat] = React.useState<ExportFormat>("csv");
  const [includeDetails, setIncludeDetails] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      if (typeof el.showModal === "function") el.showModal();
      else el.setAttribute("open", "");
    } else if (!open && el.open) {
      if (typeof el.close === "function") el.close();
      else el.removeAttribute("open");
    }
  }, [open]);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const isDark = document.documentElement.classList.contains("dark");
    el.style.backgroundColor = isDark ? "var(--neutral-900)" : "var(--surface)";
    el.style.color = isDark ? "var(--neutral-50)" : "var(--text)";
    el.style.borderColor = isDark ? "var(--neutral-800)" : "var(--border)";
    el.style.colorScheme = isDark ? "dark" : "light";
  }, [open]);

  const supportsDetails = format !== "wikibase" && format !== "openrefine";
  const canExport = bookCount > 0 && !loading;

  const handleExport = async () => {
    if (!canExport) return;
    setLoading(true);
    try {
      const params: ExportParams = {
        format,
        include_details: supportsDetails ? includeDetails : false,
        book_ids: scope.bookIds,
        language: scope.language,
        status: scope.status,
        owner_id: scope.ownerId,
      };
      const { blob, filename } = await exportMetadata(params);
      const fallback = `indic-books_${bookCount}-books.${EXTENSIONS[format]}`;
      downloadBlob(blob, filenameFromDisposition(filename, fallback));
      toast.success(
        `Exported ${bookCount} book${bookCount === 1 ? "" : "s"} as ${FORMAT_LABELS[format]}`,
      );
      onClose();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        event.preventDefault();
        if (!loading) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !loading) onClose();
      }}
      className="m-auto w-full max-w-xl rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/40 dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]"
    >
      <div className="px-6 pt-5 pb-2 text-left">
        <h2 id={titleId} className="text-md font-semibold text-[var(--text)]">
          {title}
        </h2>
        <p id={descriptionId} className="mt-1 text-sm text-[var(--text-muted)]">
          {description ??
            "Choose a format. Reviewed metadata is exported as-is, including empty fields."}
        </p>
      </div>

      <fieldset className="px-6 pt-3">
        <legend className="text-[12px] font-medium text-[var(--text-muted)] mb-2">
          Format
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {FORMATS.map((option) => {
            const checked = format === option.value;
            return (
              <label
                key={option.value}
                className={cn(
                  "flex min-h-11 cursor-pointer items-start gap-3 rounded-[var(--radius)] border px-3 py-2.5",
                  "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[var(--focus-ring)]",
                  checked
                    ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                    : "border-[var(--border)] hover:bg-[var(--surface-sunken)]",
                )}
              >
                <input
                  type="radio"
                  name="export-format"
                  value={option.value}
                  checked={checked}
                  onChange={() => setFormat(option.value)}
                  className="mt-0.5 size-4 accent-[var(--accent)]"
                />
                <span className="min-w-0">
                  <span className="block text-[length:var(--text-sm)] font-medium text-[var(--text)]">
                    {option.label}
                  </span>
                  <span className="block text-[length:var(--text-xs)] text-[var(--text-muted)]">
                    {option.description}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="px-6 pt-4">
        {supportsDetails ? (
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-[length:var(--text-sm)] text-[var(--text)]">
            <input
              type="checkbox"
              checked={includeDetails}
              onChange={(event) => setIncludeDetails(event.target.checked)}
              className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
            />
            Include book details (title, language, filename, status, dates)
          </label>
        ) : (
          <p className="py-3 text-[length:var(--text-xs)] text-[var(--text-muted)]">
            This format always includes the book identifier and metadata only.
          </p>
        )}

        {bookCount === 0 && (
          <p className="text-[length:var(--text-sm)] text-[var(--danger-700)] dark:text-[var(--danger-100)]">
            No selected book has reviewed metadata yet.
          </p>
        )}
      </div>

      <div className="flex justify-end gap-2 px-6 pt-4 pb-5">
        <Button variant="outline" onClick={onClose} disabled={loading}>
          Close
        </Button>
        <Button onClick={handleExport} disabled={!canExport} loading={loading}>
          {`Export ${bookCount} book${bookCount === 1 ? "" : "s"}`}
        </Button>
      </div>
    </dialog>
  );
}

export default ExportDialog;

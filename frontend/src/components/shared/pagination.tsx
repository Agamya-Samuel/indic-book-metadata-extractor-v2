"use client";

import { Button } from "@/components/shared/button";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Current page size. Only shown when `onPageSizeChange` is provided. */
  pageSize?: number;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  /** Disable controls while a page is loading. */
  disabled?: boolean;
  className?: string;
}

const DEFAULT_PAGE_SIZES = [20, 50, 100];

function pageItems(page: number, totalPages: number): Array<number | "left" | "right"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const items: Array<number | "left" | "right"> = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);

  if (start > 2) items.push("left");
  for (let p = start; p <= end; p += 1) items.push(p);
  if (end < totalPages - 1) items.push("right");
  items.push(totalPages);

  return items;
}

export default function Pagination({
  page,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZES,
  disabled = false,
  className,
}: PaginationProps) {
  const showSizeSelector =
    pageSize !== undefined && onPageSizeChange !== undefined;

  if (totalPages <= 1 && !showSizeSelector) return null;

  const safeTotal = Math.max(1, totalPages);

  return (
    <nav
      className={cn(
        "mt-6 flex flex-wrap items-center justify-center gap-2",
        className,
      )}
      aria-label="Pagination"
    >
      {showSizeSelector && (
        <label className="mr-2 flex items-center gap-1.5 text-[length:var(--text-sm)] text-[var(--text-muted)]">
          <span>Rows</span>
          <select
            value={pageSize}
            disabled={disabled}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="h-8 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-2 text-[length:var(--text-sm)] text-[var(--text)] disabled:opacity-50"
            aria-label="Rows per page"
          >
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(Math.max(1, page - 1))}
        disabled={disabled || page === 1}
      >
        Previous
      </Button>

      {pageItems(page, safeTotal).map((item, index) =>
        typeof item === "number" ? (
          <Button
            key={item}
            variant={item === page ? "primary" : "outline"}
            size="sm"
            className="min-w-8 px-2"
            aria-current={item === page ? "page" : undefined}
            aria-label={`Page ${item}`}
            disabled={disabled}
            onClick={() => onPageChange(item)}
          >
            {item}
          </Button>
        ) : (
          <span
            key={`${item}-${index}`}
            aria-hidden="true"
            className="px-1 text-[length:var(--text-sm)] text-[var(--text-subtle)]"
          >
            …
          </span>
        ),
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(Math.min(safeTotal, page + 1))}
        disabled={disabled || page === safeTotal}
      >
        Next
      </Button>

      <span
        className="px-2 text-[length:var(--text-sm)] text-[var(--text-muted)]"
        aria-live="polite"
      >
        Page {page} of {safeTotal}
      </span>
    </nav>
  );
}

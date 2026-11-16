"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import { SkeletonTable } from "./skeleton";

export type SortDirection = "asc" | "desc";

export interface DataTableColumn<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
  /** Hide the column below this breakpoint. */
  hideBelow?: "sm" | "md" | "lg" | "xl";
  /** Makes the header a sort control. Pair with `onSortChange`. */
  sortKey?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption?: string;
  className?: string;
  rowClassName?: (row: T) => string | undefined;
  /** Render a skeleton instead of the table (first load). */
  loading?: boolean;
  /** Render this when `rows` is empty. Omit to keep the empty table shell. */
  empty?: React.ReactNode;
  /** Pin the header while the body scrolls (pair with `maxHeight`). */
  stickyHeader?: boolean;
  /** Cap the scroll area, in pixels, so `stickyHeader` has an effect. */
  maxHeight?: number;
  /**
   * Drop the outer border, rounding and shadow so the table can sit flush
   * inside a Card instead of drawing a second box around itself.
   */
  bare?: boolean;
  /** Key of the row whose detail row is open, if the table has any. */
  expandedRowKey?: string | null;
  /** Detail content rendered full-width beneath the expanded row. */
  renderExpandedRow?: (row: T) => React.ReactNode;
  /** Currently sorted column key, if the table is server-sorted. */
  sortKey?: string | null;
  /** Current sort direction. Defaults to `desc` server-side. */
  sortDirection?: SortDirection;
  /** Called with a column's `sortKey` when its header is activated. */
  onSortChange?: (key: string) => void;
}

const HIDE_BELOW: Record<NonNullable<DataTableColumn<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

function SortArrow({ direction }: { direction: SortDirection | null }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 10 12"
      className={cn("size-2.5 shrink-0", direction ? "opacity-100" : "opacity-40")}
      fill="currentColor"
    >
      {direction === "asc" ? (
        <path d="M5 1.5 9 7H1z" />
      ) : direction === "desc" ? (
        <path d="M5 10.5 1 5h8z" />
      ) : (
        <>
          <path d="M5 1.5 8 4.5H2z" />
          <path d="M5 10.5 2 7.5h6z" />
        </>
      )}
    </svg>
  );
}

/**
 * Shared admin table shell: border/shadow surface, sticky-feeling header,
 * horizontal scroll on narrow screens, and responsive column hiding.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  className,
  rowClassName,
  loading = false,
  empty,
  stickyHeader = false,
  maxHeight,
  bare = false,
  expandedRowKey,
  renderExpandedRow,
  sortKey = null,
  sortDirection = "desc",
  onSortChange,
}: DataTableProps<T>) {
  if (loading) {
    return <SkeletonTable rows={5} />;
  }

  if (empty !== undefined && rows.length === 0) {
    return <>{empty}</>;
  }

  return (
    <div
      className={cn(
        !bare &&
          "overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-xs)]",
        className,
      )}
    >
      <div
        className="overflow-x-auto"
        style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}
      >
        <table className="w-full text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead
            className={cn(
              "bg-[var(--surface-sunken)]/60 text-[length:var(--text-xs)] uppercase tracking-wider text-[var(--text-muted)]",
              stickyHeader &&
                "sticky top-0 z-10 bg-[var(--surface)] backdrop-blur",
            )}
          >
            <tr>
              {columns.map((column) => {
                const isSorted = column.sortKey != null && sortKey === column.sortKey;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={
                      column.sortKey && onSortChange
                        ? isSorted
                          ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                        : undefined
                    }
                    className={cn(
                      "px-3 py-2.5 text-left font-medium whitespace-nowrap",
                      column.hideBelow && HIDE_BELOW[column.hideBelow],
                      column.headerClassName,
                    )}
                  >
                    {column.sortKey && onSortChange ? (
                      <button
                        type="button"
                        onClick={() => onSortChange(column.sortKey as string)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-[var(--radius-xs)] uppercase tracking-wider",
                          focusRing,
                        )}
                      >
                        {column.header}
                        <SortArrow direction={isSorted ? sortDirection : null} />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {rows.map((row) => (
              <React.Fragment key={rowKey(row)}>
                <tr
                  className={cn(
                    "hover:bg-[var(--surface-sunken)]/40",
                    rowClassName?.(row),
                  )}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-3 py-2.5 align-middle",
                        column.hideBelow && HIDE_BELOW[column.hideBelow],
                        column.className,
                      )}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
                {renderExpandedRow && expandedRowKey === rowKey(row) && (
                  <tr className="bg-[var(--surface-sunken)]/40">
                    <td colSpan={columns.length} className="px-3 py-3">
                      {renderExpandedRow(row)}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default DataTable;
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { SkeletonTable } from "./skeleton";

export interface DataTableColumn<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
  /** Hide the column below this breakpoint. */
  hideBelow?: "sm" | "md" | "lg" | "xl";
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
}

const HIDE_BELOW: Record<NonNullable<DataTableColumn<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

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
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={cn(
                    "px-3 py-2.5 text-left font-medium whitespace-nowrap",
                    column.hideBelow && HIDE_BELOW[column.hideBelow],
                    column.headerClassName,
                  )}
                >
                  {column.header}
                </th>
              ))}
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
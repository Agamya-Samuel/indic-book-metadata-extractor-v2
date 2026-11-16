"use client";

import type { JobSummaryResponse, UserJobCounts } from "@/lib/api";
import { Card } from "@/components/shared/card";
import StatCard from "@/components/shared/stat-card";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { EmptyState } from "@/components/shared/empty-state";
import { SkeletonTable } from "@/components/shared/skeleton";
import { cn } from "@/lib/utils";

const userColumns: DataTableColumn<UserJobCounts>[] = [
  {
    key: "user",
    header: "User",
    cell: (row) => (
      <div className="flex flex-col">
        <span className="truncate text-[length:var(--text-sm)] text-[var(--text)]">
          {row.display_name ?? "Unassigned"}
        </span>
        {row.email && (
          <span className="truncate text-[10px] text-[var(--text-muted)]" title={row.email}>
            {row.email}
          </span>
        )}
      </div>
    ),
  },
  {
    key: "total",
    header: "Total",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => row.total,
  },
  {
    key: "queued",
    header: "Queued",
    hideBelow: "sm",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => row.queued,
  },
  {
    key: "running",
    header: "Running",
    hideBelow: "sm",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => row.running,
  },
  {
    key: "completed",
    header: "Completed",
    hideBelow: "md",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => row.completed,
  },
  {
    key: "failed",
    header: "Failed",
    hideBelow: "md",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => (
      <span className={cn(row.failed > 0 && "font-medium text-[var(--danger-700)] dark:text-[var(--danger-300)]")}>
        {row.failed}
      </span>
    ),
  },
  {
    key: "cancelled",
    header: "Cancelled",
    hideBelow: "lg",
    className: "text-right tabular-nums",
    headerClassName: "text-right",
    cell: (row) => row.cancelled,
  },
];

export default function JobSummaryPanel({
  summary,
  loading = false,
}: {
  summary?: JobSummaryResponse;
  loading?: boolean;
}) {
  if (loading && !summary) {
    return <SkeletonTable rows={3} />;
  }
  if (!summary) return null;

  const metrics = [
    { label: "Total jobs", value: summary.total, tone: "neutral" as const },
    { label: "Queued", value: summary.queued, tone: "info" as const },
    { label: "Processing", value: summary.running, tone: "info" as const },
    { label: "Completed", value: summary.completed, tone: "success" as const },
    {
      label: "Failed",
      value: summary.failed,
      tone: summary.failed > 0 ? ("danger" as const) : ("neutral" as const),
    },
    { label: "Cancelled", value: summary.cancelled, tone: "warning" as const },
  ];

  return (
    <Card
      title="Queue overview"
      description="Every processing job across the application"
      className="mb-4"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {metrics.map((metric) => (
          <StatCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            tone={metric.tone}
            flush
            className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
          />
        ))}
      </div>

      <div className="mt-4">
        <CollapsibleSection
          title="By user"
          defaultOpen={false}
          meta="jobs submitted, by status"
        >
          {summary.by_user.length === 0 ? (
            <EmptyState
              title="No jobs yet"
              description="Jobs submitted by any user will appear here."
            />
          ) : (
            <DataTable
              bare
              columns={userColumns}
              rows={summary.by_user}
              rowKey={(row) => row.user_id ?? "unassigned"}
              caption="Job counts by user"
            />
          )}
        </CollapsibleSection>
      </div>
    </Card>
  );
}

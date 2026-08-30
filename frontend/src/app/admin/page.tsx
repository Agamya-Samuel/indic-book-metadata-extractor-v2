"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getAdminStats, getAdminJobs } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import AdminStatsCard from "@/components/admin/admin-stats-card";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { SkeletonPageHeader, SkeletonTable } from "@/components/shared/skeleton";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

function formatMb(mb: number) {
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export default function AdminDashboardPage() {
  useDocumentTitle("Admin · Dashboard");

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: getAdminStats,
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
  });

  const { data: recentJobs } = useQuery({
    queryKey: ["admin-jobs", { page_size: 10 }],
    queryFn: () => getAdminJobs({ page_size: 10 }),
    staleTime: 10 * 1000,
    refetchInterval: 10 * 1000,
  });

  const completionRate = useMemo(() => {
    if (!stats) return null;
    const total =
      stats.jobs.completed_recent + stats.jobs.failed_recent;
    if (total === 0) return null;
    return Math.round((stats.jobs.completed_recent / total) * 100);
  }, [stats]);

  return (
    <PageContainer>
      {statsLoading ? (
        <SkeletonPageHeader />
      ) : (
        <PageHeader
          eyebrow="Admin"
          title="Library dashboard"
          description={
            stats
              ? `${stats.total_books} book${stats.total_books !== 1 ? "s" : ""} in the library · ${stats.books_with_metadata} with metadata extracted`
              : "Loading…"
          }
        />
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-3 lg:grid-cols-4 mb-6 sm:mb-8">
        <AdminStatsCard
          label="Total books"
          value={stats?.total_books ?? "—"}
          tone="info"
        />
        <AdminStatsCard
          label="With metadata"
          value={stats?.books_with_metadata ?? "—"}
          sublabel={
            stats
              ? `${stats.total_books ? Math.round((stats.books_with_metadata / stats.total_books) * 100) : 0}% of library`
              : undefined
          }
          tone="success"
        />
        <AdminStatsCard
          label="Running jobs"
          value={stats?.jobs.running ?? "—"}
          sublabel={`${stats?.jobs.queued ?? 0} queued`}
          tone={stats && stats.jobs.running > 0 ? "info" : "neutral"}
        />
        <AdminStatsCard
          label="Failed (7d)"
          value={stats?.jobs.failed_recent ?? "—"}
          sublabel={
            completionRate !== null
              ? `${completionRate}% success rate (7d)`
              : "no activity"
          }
          tone={
            stats && stats.jobs.failed_recent > 0 ? "warning" : "neutral"
          }
        />
        <AdminStatsCard
          label="Disk usage"
          value={stats ? formatMb(stats.disk_usage_mb) : "—"}
          sublabel="uploaded PDFs"
        />
        <AdminStatsCard
          label="Completed (7d)"
          value={stats?.jobs.completed_recent ?? "—"}
          tone="success"
        />
        <AdminStatsCard
          label="Books in 'complete'"
          value={stats?.statuses?.complete ?? 0}
          sublabel={
            stats?.statuses
              ? `${Object.entries(stats.statuses).filter(([k]) => k !== "complete").reduce((a, [, v]) => a + v, 0)} in earlier states`
              : undefined
          }
          tone="success"
        />
        <AdminStatsCard
          label="Languages"
          value={stats ? Object.keys(stats.languages).length : "—"}
          sublabel={
            stats
              ? Object.entries(stats.languages)
                  .map(([k, v]) => `${k.toUpperCase()} ${v}`)
                  .join(" · ")
              : undefined
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card
          title="Recent jobs"
          description="Last 10 jobs across the library"
          className="lg:col-span-2"
          headerAction={
            <Link
              href="/admin/jobs"
              className="text-[var(--text-sm)] font-medium text-[var(--accent)] hover:underline"
            >
              View all →
            </Link>
          }
        >
          {!recentJobs ? (
            <SkeletonTable rows={4} />
          ) : recentJobs.items.length === 0 ? (
            <p className="text-[var(--text-sm)] text-[var(--text-muted)] py-4">
              No jobs yet.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {recentJobs.items.map((job) => (
                <li
                  key={job.id}
                  className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <StatusBadge status={job.status} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[var(--text-sm)] font-medium text-[var(--text)]">
                      <span className="uppercase tracking-wide text-[var(--text-xs)] text-[var(--text-muted)] mr-2">
                        {job.job_type}
                      </span>
                      {job.book_title || job.book_filename}
                    </p>
                    <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                      {job.error_log
                        ? job.error_log.slice(0, 100)
                        : job.completed_at
                        ? `Completed ${new Date(job.completed_at).toLocaleString()}`
                        : job.started_at
                        ? `Started ${new Date(job.started_at).toLocaleString()}`
                        : `Queued ${new Date(job.created_at ?? "").toLocaleString()}`}
                    </p>
                  </div>
                  {job.status === "running" && (
                    <span
                      className={cn(
                        "inline-flex h-1.5 w-24 overflow-hidden rounded-full",
                        "bg-[var(--surface-sunken)] border border-[var(--border)]",
                      )}
                      aria-label={`${Math.round(job.progress * 100)}% complete`}
                    >
                      <span
                        className="h-full bg-[var(--info-500)] transition-[width]"
                        style={{ width: `${Math.round(job.progress * 100)}%` }}
                      />
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Quick links">
          <Stack gap={2}>
            <Link
              href="/admin/books"
              className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-4 py-3 transition-colors hover:bg-[var(--surface-sunken)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)]"
            >
              <p className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
                Manage books →
              </p>
              <p className="text-[var(--text-xs)] text-[var(--text-muted)] mt-0.5">
                Delete, reset, or re-run processing for any book
              </p>
            </Link>
            <Link
              href="/admin/jobs"
              className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-4 py-3 transition-colors hover:bg-[var(--surface-sunken)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)]"
            >
              <p className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
                All jobs →
              </p>
              <p className="text-[var(--text-xs)] text-[var(--text-muted)] mt-0.5">
                Inspect and cancel running or queued jobs
              </p>
            </Link>
            <Link
              href="/bulk-operations"
              className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-4 py-3 transition-colors hover:bg-[var(--surface-sunken)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)]"
            >
              <p className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
                Bulk operations →
              </p>
              <p className="text-[var(--text-xs)] text-[var(--text-muted)] mt-0.5">
                Export and import metadata as CSV
              </p>
            </Link>
          </Stack>
        </Card>
      </div>
    </PageContainer>
  );
}
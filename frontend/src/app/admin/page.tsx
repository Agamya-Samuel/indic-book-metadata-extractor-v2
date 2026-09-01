"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getAdminStats, getAdminJobs } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import AdminStatsCard from "@/components/admin/admin-stats-card";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
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

      {/*
        The 8 signals are grouped into three purposeful collections so the
        eye can rest on one subject at a time: Library (what the collection
        holds), Pipeline (what's happening now), System (footprint and
        language coverage). Each cluster sits on a Card so the grouping is
        structural, not just spacing.
      */}
      <div className="space-y-4 sm:space-y-5 mb-6 sm:mb-8">
        <Card>
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <AdminStatsCard
              label="Total books"
              value={stats?.total_books ?? "—"}
              tone="info"
              flush
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
              flush
            />
            <AdminStatsCard
              label="In 'complete' state"
              value={stats?.statuses?.complete ?? 0}
              sublabel={
                stats?.statuses
                  ? `${Object.entries(stats.statuses).filter(([k]) => k !== "complete").reduce((a, [, v]) => a + v, 0)} in earlier states`
                  : undefined
              }
              tone="success"
              flush
            />
          </div>
        </Card>

        <Card>
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <AdminStatsCard
              label="Running jobs"
              value={stats?.jobs.running ?? "—"}
              sublabel={`${stats?.jobs.queued ?? 0} queued`}
              tone={stats && stats.jobs.running > 0 ? "info" : "neutral"}
              flush
            />
            <AdminStatsCard
              label="Completed (7d)"
              value={stats?.jobs.completed_recent ?? "—"}
              tone="success"
              flush
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
              flush
            />
          </div>
        </Card>

        <Card>
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <AdminStatsCard
              label="Disk usage"
              value={stats ? formatMb(stats.disk_usage_mb) : "—"}
              sublabel="uploaded PDFs"
              flush
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
              flush
            />
          </div>
        </Card>
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
                  className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
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
          <ul className="-mx-5 -my-4 divide-y divide-[var(--border)]">
            {[
              {
                href: "/admin/books",
                title: "Manage books",
                description: "Delete, reset, or re-run processing for any book",
              },
              {
                href: "/admin/jobs",
                title: "All jobs",
                description: "Inspect and cancel running or queued jobs",
              },
              {
                href: "/bulk-operations",
                title: "Bulk operations",
                description: "Export and import metadata as CSV",
              },
            ].map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="group flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[var(--surface-sunken)]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-inset"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
                      {link.title}
                    </p>
                    <p className="mt-0.5 text-[var(--text-xs)] text-[var(--text-muted)]">
                      {link.description}
                    </p>
                  </div>
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="size-4 shrink-0 text-[var(--text-subtle)] transition-transform duration-[var(--duration-fast)] group-hover:translate-x-0.5 group-hover:text-[var(--text-muted)]"
                  >
                    <path
                      fillRule="evenodd"
                      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </PageContainer>
  );
}
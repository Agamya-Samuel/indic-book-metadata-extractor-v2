"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminJobs,
  cancelAdminJob,
  type AdminJobRow,
} from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import { Button } from "@/components/shared/button";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { SkeletonPageHeader } from "@/components/shared/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

const STATUSES = ["queued", "running", "completed", "failed", "cancelled"];
const JOB_TYPES = ["ocr", "llm", "preprocessing"];

export default function AdminJobsPage() {
  useDocumentTitle("Admin · Jobs");

  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [page, setPage] = React.useState(1);

  const handleStatusChange = (v: string) => {
    setStatusFilter(v);
    setPage(1);
  };
  const handleTypeChange = (v: string) => {
    setTypeFilter(v);
    setPage(1);
  };

  const params = {
    status: statusFilter || undefined,
    job_type: (typeFilter || undefined) as "ocr" | "llm" | "preprocessing" | undefined,
    page,
    page_size: 50,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["admin-jobs", params],
    queryFn: () => getAdminJobs(params),
    staleTime: 3 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const jobs = q.state.data?.items;
      const hasActive =
        jobs?.some((j) => j.status === "queued" || j.status === "running") ?? false;
      return hasActive ? 3_000 : 30_000;
    },
  });

  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 0;
  const total = data?.total ?? 0;

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-jobs"] });
    qc.invalidateQueries({ queryKey: ["admin-stats"] });
  };

  const cancel = useMutation({
    mutationFn: (id: string) => cancelAdminJob(id),
    onSuccess: () => {
      toast.success("Job cancelled");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const [confirmCancel, setConfirmCancel] = React.useState<AdminJobRow | null>(null);

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Admin"
        title="Jobs"
        description={`${total} job${total !== 1 ? "s" : ""}`}
      />

      <Card className="mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="w-40">
            <Field label="Status" htmlFor="admin-job-status">
              <Select
                id="admin-job-status"
                value={statusFilter}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                <option value="">All</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <div className="w-40">
            <Field label="Type" htmlFor="admin-job-type">
              <Select
                id="admin-job-type"
                value={typeFilter}
                onChange={(e) => handleTypeChange(e.target.value)}
              >
                <option value="">All</option>
                {JOB_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <>
          <SkeletonPageHeader />
          <div className="mt-6 space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)] animate-pulse"
              />
            ))}
          </div>
        </>
      ) : items.length === 0 ? (
        <EmptyState
          title="No jobs match your filters"
          description="Try clearing the filters or check back later."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-xs)]">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--surface-sunken)]/60 text-[var(--text-xs)] uppercase tracking-wider text-[var(--text-muted)]">
                  <tr>
                    <th className="px-3 py-2.5 text-left font-medium">Type</th>
                    <th className="px-3 py-2.5 text-left font-medium">Status</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden md:table-cell">Book</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden lg:table-cell">Progress</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden lg:table-cell">Started</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden lg:table-cell">Completed</th>
                    <th className="px-3 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {items.map((job) => (
                    <tr key={job.id} className="hover:bg-[var(--surface-sunken)]/40">
                      <td className="px-3 py-2.5 align-middle uppercase tracking-wide text-[var(--text-xs)] font-semibold text-[var(--text-muted)]">
                        {job.job_type}
                      </td>
                      <td className="px-3 py-2.5 align-middle">
                        <div className="flex flex-col gap-1">
                          <StatusBadge status={job.status} />
                          {job.error_log && (
                            <span className="text-[10px] text-[var(--danger-700)] dark:text-[var(--danger-300)] truncate max-w-xs" title={job.error_log}>
                              {job.error_log}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 align-middle hidden md:table-cell">
                        {job.book_id ? (
                          <Link
                            href={`/library/${job.book_id}`}
                            className="text-[var(--text-sm)] text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] rounded-[var(--radius-xs)]"
                          >
                            {job.book_title || job.book_filename}
                          </Link>
                        ) : (
                          <span className="text-[var(--text-muted)] text-[var(--text-sm)]">
                            {job.book_filename}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle hidden lg:table-cell min-w-[140px]">
                        {job.status === "running" || job.status === "completed" ? (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-[var(--surface-sunken)] border border-[var(--border)]">
                              <div
                                className={cn(
                                  "h-full transition-[width]",
                                  job.status === "completed"
                                    ? "bg-[var(--success-500)]"
                                    : "bg-[var(--info-500)]",
                                )}
                                style={{ width: `${Math.round(job.progress * 100)}%` }}
                              />
                            </div>
                            <span className="text-[var(--text-xs)] tabular-nums text-[var(--text-muted)] w-9 text-right">
                              {Math.round(job.progress * 100)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-[var(--text-muted)] text-[var(--text-xs)]">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle hidden lg:table-cell text-[var(--text-xs)] text-[var(--text-muted)] tabular-nums">
                        {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-3 py-2.5 align-middle hidden lg:table-cell text-[var(--text-xs)] text-[var(--text-muted)] tabular-nums">
                        {job.completed_at ? new Date(job.completed_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-3 py-2.5 align-middle text-right">
                        <Stack gap={1} className="items-end">
                          {job.book_id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                window.location.href = `/library/${job.book_id}`;
                              }}
                            >
                              Open book
                            </Button>
                          )}
                          {(job.status === "queued" || job.status === "running") && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setConfirmCancel(job)}
                              disabled={cancel.isPending}
                            >
                              Cancel
                            </Button>
                          )}
                        </Stack>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {totalPages > 1 && (
            <nav
              className="mt-6 flex flex-wrap items-center justify-center gap-2"
              aria-label="Pagination"
            >
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="px-3 text-[var(--text-sm)] text-[var(--text-muted)]">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </nav>
          )}
        </>
      )}

      <ConfirmDialog
        open={!!confirmCancel}
        onClose={() => setConfirmCancel(null)}
        onConfirm={async () => {
          if (confirmCancel) await cancel.mutateAsync(confirmCancel.id);
          setConfirmCancel(null);
        }}
        title="Cancel this job?"
        description={
          confirmCancel ? (
            <span>
              The {confirmCancel.job_type.toUpperCase()} job for{" "}
              <strong className="font-semibold text-[var(--text)]">
                {confirmCancel.book_title || confirmCancel.book_filename}
              </strong>{" "}
              will be marked cancelled. Worker processes may take a moment to stop.
            </span>
          ) : null
        }
        confirmLabel="Cancel job"
        variant="warning"
        loading={cancel.isPending}
      />
    </PageContainer>
  );
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const r = (err as { response?: { data?: { detail?: unknown } } }).response;
    if (r?.data?.detail) {
      return typeof r.data.detail === "string" ? r.data.detail : JSON.stringify(r.data.detail);
    }
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
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
import { Button, LinkButton } from "@/components/shared/button";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import OwnerFilter, { type OwnerSelection } from "@/components/admin/owner-filter";
import Pagination from "@/components/shared/pagination";
import { PageContainer, Card, PageHeader } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";
import { cn } from "@/lib/utils";

const STATUSES = ["queued", "running", "completed", "failed", "cancelled"];
const JOB_TYPES = ["page_extraction", "ocr", "llm", "preprocessing"];

export default function AdminJobsPage() {
  useDocumentTitle("Admin · Jobs");

  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [owner, setOwner] = React.useState<OwnerSelection | null>(null);
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
    job_type: (typeFilter || undefined) as
      | "page_extraction"
      | "ocr"
      | "llm"
      | "preprocessing"
      | undefined,
    owner_id: owner?.id,
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
  const cancellingId = cancel.isPending ? cancel.variables : null;

  const columns: DataTableColumn<AdminJobRow>[] = [
    {
      key: "type",
      header: "Type",
      cell: (job) => (
        <span className="uppercase tracking-wide text-[var(--text-xs)] font-semibold text-[var(--text-muted)]">
          {job.job_type}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (job) => (
        <div className="flex flex-col gap-1">
          <StatusBadge status={job.status} />
          {job.error_log && (
            <span
              className="text-[10px] text-[var(--danger-700)] dark:text-[var(--danger-300)] truncate max-w-xs"
              title={job.error_log}
            >
              {job.error_log}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "book",
      header: "Book",
      hideBelow: "md",
      cell: (job) =>
        job.book_id ? (
          <Link
            href={`/library/${job.book_id}`}
            className="text-[var(--text-sm)] text-[var(--text)] hover:underline"
          >
            {job.book_title || job.book_filename}
          </Link>
        ) : (
          <span className="text-[var(--text-muted)] text-[var(--text-sm)]">
            {job.book_filename}
          </span>
        ),
    },
    {
      key: "owner",
      header: "Owner",
      hideBelow: "xl",
      cell: (job) => (
        <div className="flex flex-col">
          <span
            className="text-[var(--text-sm)] text-[var(--text)] truncate max-w-[10rem]"
            title={job.owner_display_name ?? undefined}
          >
            {job.owner_display_name ?? "—"}
          </span>
          {job.owner_email && (
            <span
              className="text-[10px] text-[var(--text-muted)] truncate max-w-[10rem]"
              title={job.owner_email}
            >
              {job.owner_email}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "progress",
      header: "Progress",
      hideBelow: "lg",
      className: "min-w-[140px]",
      cell: (job) =>
        job.status === "running" || job.status === "completed" ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-[var(--surface-sunken)] border border-[var(--border)]">
              <div
                className={cn(
                  "h-full transition-[width]",
                  job.status === "completed"
                    ? "bg-[var(--success-500)]"
                    : "bg-[var(--info-500)]",
                )}
                style={{ width: `${Math.round(job.progress)}%` }}
              />
            </div>
            <span className="text-[var(--text-xs)] tabular-nums text-[var(--text-muted)] w-9 text-right">
              {Math.round(job.progress)}%
            </span>
          </div>
        ) : (
          <span className="text-[var(--text-muted)] text-[var(--text-xs)]">—</span>
        ),
    },
    {
      key: "started",
      header: "Started",
      hideBelow: "lg",
      className: "text-[var(--text-xs)] text-[var(--text-muted)] tabular-nums",
      cell: (job) =>
        job.started_at ? new Date(job.started_at).toLocaleString() : "—",
    },
    {
      key: "completed",
      header: "Completed",
      hideBelow: "lg",
      className: "text-[var(--text-xs)] text-[var(--text-muted)] tabular-nums",
      cell: (job) =>
        job.completed_at ? new Date(job.completed_at).toLocaleString() : "—",
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (job) => (
        <div className="flex flex-col items-end gap-1.5">
          {job.book_id && (
            <LinkButton
              href={`/library/${job.book_id}`}
              variant="ghost"
              size="sm"
            >
              Open book
            </LinkButton>
          )}
          {(job.status === "queued" || job.status === "running") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmCancel(job)}
              disabled={cancellingId === job.id}
            >
              {cancellingId === job.id ? "Cancelling…" : "Cancel"}
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Admin"
        title="Jobs"
        description={`${total} job${total !== 1 ? "s" : ""}`}
      />
      <Card className="mb-4" title="Filters">
        <div>
          <p className="text-[var(--text-xs)] font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
            Filters
          </p>
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
            <OwnerFilter
              value={owner}
              onChange={(v) => {
                setOwner(v);
                setPage(1);
              }}
              id="admin-job-owner"
            />
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="mt-6 space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)] animate-pulse"
              />
            ))}
          </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No jobs match your filters"
          description="Try clearing the filters or check back later."
        />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={items}
            rowKey={(job) => job.id}
            caption="Background jobs"
          />

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
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
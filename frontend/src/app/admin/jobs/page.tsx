"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminJobs,
  getAdminJobSummary,
  cancelAdminJob,
  cancelAdminJobsBulk,
  retryAdminJob,
  type AdminJobRow,
} from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import { Progress } from "@/components/shared/progress";
import { Button, LinkButton } from "@/components/shared/button";
import DataTable, {
  type DataTableColumn,
  type SortDirection,
} from "@/components/shared/data-table";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import OwnerFilter, { type OwnerSelection } from "@/components/admin/owner-filter";
import JobSummaryPanel from "@/components/admin/job-summary-panel";
import Pagination from "@/components/shared/pagination";
import { PageContainer, Card, PageHeader } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { EmptyState } from "@/components/shared/empty-state";
import { Chip, type ChipTone } from "@/components/shared/chip";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import { formatElapsed } from "@/lib/utils";

const STATUSES = ["queued", "running", "completed", "failed", "cancelled"];
const JOB_TYPES = ["page_extraction", "ocr", "llm", "preprocessing"];

const STAGE_TONE: Record<string, ChipTone> = {
  initiated: "neutral",
  processing: "info",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

function queueLabel(job: AdminJobRow): string {
  if (job.status === "running") return "Running now";
  if (job.status === "queued") {
    if (job.queue_ahead === 0) return "Next up";
    if (job.queue_ahead != null) return `${job.queue_ahead} ahead`;
    return "Queued";
  }
  return "—";
}

function durationLabel(job: AdminJobRow): string {
  if (job.duration_seconds == null) return "—";
  return formatElapsed(job.duration_seconds * 1000);
}

function SelectAllCheckbox({
  checked,
  indeterminate,
  onChange,
  label,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
  label: string;
}) {
  const ref = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={label}
      className="size-4 accent-[var(--accent)]"
    />
  );
}

export default function AdminJobsPage() {
  useDocumentTitle("Admin · Jobs");

  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [owner, setOwner] = React.useState<OwnerSelection | null>(null);
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(DEFAULT_PAGE_SIZE);
  const [sortKey, setSortKey] = React.useState("created_at");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc");
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const resetSelection = () => setSelected(new Set());

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
    resetSelection();
  };
  const handleTypeChange = (value: string) => {
    setTypeFilter(value);
    setPage(1);
    resetSelection();
  };
  const handlePageSizeChange = (value: number) => {
    setPageSize(value);
    setPage(1);
    resetSelection();
  };
  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
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
    sort: sortKey,
    order: sortDirection,
    page,
    page_size: pageSize,
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

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["admin-job-summary"],
    queryFn: getAdminJobSummary,
    staleTime: 10 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const active = (q.state.data?.queued ?? 0) + (q.state.data?.running ?? 0) > 0;
      return active ? 5_000 : 30_000;
    },
  });

  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 0;
  const total = data?.total ?? 0;

  const pageIds = items.map((job) => job.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const someSelected = pageIds.some((id) => selected.has(id));

  const toggleSelected = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleSelectAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-jobs"] });
    qc.invalidateQueries({ queryKey: ["admin-job-summary"] });
    qc.invalidateQueries({ queryKey: ["admin-stats"] });
  };

  const cancel = useMutation({
    mutationFn: (id: string) => cancelAdminJob(id),
    onSuccess: () => {
      toast.success("Job cancelled");
      resetSelection();
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const bulkCancel = useMutation({
    mutationFn: (ids: string[]) => cancelAdminJobsBulk(ids),
    onSuccess: (result) => {
      const cancelled = result.results.filter((row) => row.ok).length;
      const skipped = result.results.length - cancelled;
      toast.success(
        `${cancelled} job${cancelled === 1 ? "" : "s"} cancelled${
          skipped > 0 ? `, ${skipped} skipped` : ""
        }`,
      );
      resetSelection();
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const retry = useMutation({
    mutationFn: (id: string) => retryAdminJob(id),
    onSuccess: (result) => {
      toast.success(`Retry queued as job ${result.job_id.slice(0, 8)}`);
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const [confirmCancel, setConfirmCancel] = React.useState<AdminJobRow | null>(null);
  const [confirmBulk, setConfirmBulk] = React.useState(false);
  const cancellingId = cancel.isPending ? cancel.variables : null;

  const columns: DataTableColumn<AdminJobRow>[] = [
    {
      key: "select",
      header: (
        <SelectAllCheckbox
          checked={allSelected}
          indeterminate={someSelected && !allSelected}
          onChange={toggleSelectAll}
          label="Select all jobs on this page"
        />
      ),
      cell: (job) => (
        <input
          type="checkbox"
          checked={selected.has(job.id)}
          onChange={() => toggleSelected(job.id)}
          aria-label={`Select ${job.job_type} job for ${
            job.book_title || job.book_filename
          }`}
          className="size-4 accent-[var(--accent)]"
        />
      ),
    },
    {
      key: "type",
      header: "Type",
      sortKey: "job_type",
      cell: (job) => (
        <span className="uppercase tracking-wide text-[length:var(--text-xs)] font-semibold text-[var(--text-muted)]">
          {job.job_type}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortKey: "status",
      cell: (job) => (
        <div className="flex flex-col gap-1">
          <StatusBadge status={job.status} />
          {job.error_log && (
            <span
              className="max-w-xs truncate text-[10px] text-[var(--danger-700)] dark:text-[var(--danger-300)]"
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
            href={`/books/${job.book_id}`}
            className="text-[length:var(--text-sm)] text-[var(--text)] hover:underline"
          >
            {job.book_title || job.book_filename}
          </Link>
        ) : (
          <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
            {job.book_filename}
          </span>
        ),
    },
    {
      key: "owner",
      header: "Owner",
      sortKey: "owner",
      hideBelow: "xl",
      cell: (job) => (
        <div className="flex flex-col">
          <span
            className="max-w-[10rem] truncate text-[length:var(--text-sm)] text-[var(--text)]"
            title={job.owner_display_name ?? undefined}
          >
            {job.owner_display_name ?? "—"}
          </span>
          {job.owner_email && (
            <span
              className="max-w-[10rem] truncate text-[10px] text-[var(--text-muted)]"
              title={job.owner_email}
            >
              {job.owner_email}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "stage",
      header: "Stage",
      hideBelow: "lg",
      cell: (job) =>
        job.stage_name ? (
          <div className="flex flex-col items-start gap-1">
            <span className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
              {job.stage_name.replaceAll("_", " ")}
            </span>
            {job.stage_status && (
              <Chip tone={STAGE_TONE[job.stage_status] ?? "neutral"} dot>
                {job.stage_status}
              </Chip>
            )}
          </div>
        ) : (
          <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">—</span>
        ),
    },
    {
      key: "progress",
      header: "Progress",
      hideBelow: "lg",
      className: "min-w-[140px]",
      cell: (job) =>
        job.status === "running" || job.status === "completed" ? (
          <Progress
            value={job.progress}
            tone={job.status === "completed" ? "success" : "accent"}
            showValue
          />
        ) : (
          <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">—</span>
        ),
    },
    {
      key: "queue",
      header: "Queue",
      hideBelow: "md",
      className: "text-[length:var(--text-xs)] text-[var(--text-muted)] whitespace-nowrap",
      cell: (job) => queueLabel(job),
    },
    {
      key: "duration",
      header: "Duration",
      sortKey: "duration",
      hideBelow: "lg",
      className: "text-[length:var(--text-xs)] text-[var(--text-muted)] tabular-nums whitespace-nowrap",
      cell: (job) => durationLabel(job),
    },
    {
      key: "started",
      header: "Started",
      sortKey: "started_at",
      hideBelow: "xl",
      className: "text-[length:var(--text-xs)] text-[var(--text-muted)] tabular-nums",
      cell: (job) =>
        job.started_at ? new Date(job.started_at).toLocaleString() : "—",
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (job) => (
        <div className="flex flex-col items-end gap-1.5">
          <div className="flex flex-wrap justify-end gap-1.5">
            {job.book_id && (
              <LinkButton href={`/books/${job.book_id}`} variant="ghost" size="sm">
                Open book
              </LinkButton>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setExpandedId((current) => (current === job.id ? null : job.id))
              }
              aria-expanded={expandedId === job.id}
            >
              Details
            </Button>
          </div>
          {job.status === "failed" &&
            (job.job_type === "ocr" || job.job_type === "llm") && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => retry.mutate(job.id)}
                disabled={retry.isPending && retry.variables === job.id}
              >
                {retry.isPending && retry.variables === job.id
                  ? "Retrying…"
                  : "Retry"}
              </Button>
            )}
          {(job.status === "queued" || job.status === "running") && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmCancel(job)}
              disabled={cancellingId === job.id}
            >
              {cancellingId === job.id ? "Cancelling…" : "Cancel job"}
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
        description={`${total} job${total !== 1 ? "s" : ""} matching the current filters`}
      />

      <JobSummaryPanel summary={summary} loading={summaryLoading} />

      <Card className="mb-4" title="Filters">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-40">
            <Field label="Status" htmlFor="admin-job-status">
              <Select
                id="admin-job-status"
                value={statusFilter}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                <option value="">All</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
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
                {JOB_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <OwnerFilter
            value={owner}
            onChange={(value) => {
              setOwner(value);
              setPage(1);
              resetSelection();
            }}
            id="admin-job-owner"
          />
        </div>
      </Card>

      {selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)] px-4 py-3">
          <span className="text-[length:var(--text-sm)] text-[var(--text)]">
            {selected.size} job{selected.size === 1 ? "" : "s"} selected
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={resetSelection}>
              Clear selection
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmBulk(true)}
              loading={bulkCancel.isPending}
            >
              Cancel selected jobs
            </Button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-16 animate-pulse rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)]"
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
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSortChange={handleSort}
            expandedRowKey={expandedId}
            renderExpandedRow={(job) => (
              <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-[length:var(--text-xs)] sm:grid-cols-2">
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Job ID</dt>
                  <dd className="font-mono break-all text-[var(--text)]">{job.id}</dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Celery task ID</dt>
                  <dd className="font-mono break-all text-[var(--text)]">
                    {job.celery_task_id ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Stage</dt>
                  <dd className="text-[var(--text)]">
                    {job.stage_name
                      ? `${job.stage_name.replaceAll("_", " ")} · ${job.stage_status ?? "unknown"}`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Queue position</dt>
                  <dd className="text-[var(--text)]">{queueLabel(job)}</dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Created</dt>
                  <dd className="tabular-nums text-[var(--text)]">
                    {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Started</dt>
                  <dd className="tabular-nums text-[var(--text)]">
                    {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Last progress</dt>
                  <dd className="tabular-nums text-[var(--text)]">
                    {job.last_progress_at
                      ? new Date(job.last_progress_at).toLocaleString()
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Completed</dt>
                  <dd className="tabular-nums text-[var(--text)]">
                    {job.completed_at
                      ? new Date(job.completed_at).toLocaleString()
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-[var(--text-muted)]">Duration</dt>
                  <dd className="tabular-nums text-[var(--text)]">{durationLabel(job)}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="font-medium text-[var(--text-muted)]">Error</dt>
                  <dd className="whitespace-pre-wrap break-words text-[var(--danger-700)] dark:text-[var(--danger-300)]">
                    {job.error_log || "—"}
                  </dd>
                </div>
              </dl>
            )}
          />

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={(next) => {
              setPage(next);
              resetSelection();
            }}
            pageSize={pageSize}
            onPageSizeChange={handlePageSizeChange}
            disabled={isLoading}
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
              will be marked cancelled. A running job stops at the next safe
              checkpoint; a queued job never starts.
            </span>
          ) : null
        }
        confirmLabel="Cancel job"
        cancelLabel="Keep job"
        variant="warning"
        loading={cancel.isPending}
      />

      <ConfirmDialog
        open={confirmBulk}
        onClose={() => setConfirmBulk(false)}
        onConfirm={async () => {
          await bulkCancel.mutateAsync(Array.from(selected));
          setConfirmBulk(false);
        }}
        title={`Cancel ${selected.size} job${selected.size === 1 ? "" : "s"}?`}
        description={
          <span>
            Each selected job is cancelled independently. Running jobs stop at the
            next safe checkpoint; queued jobs never start. Jobs that are already
            completed or failed are skipped.
          </span>
        }
        confirmLabel="Cancel selected jobs"
        cancelLabel="Keep selected"
        variant="warning"
        loading={bulkCancel.isPending}
      />
    </PageContainer>
  );
}

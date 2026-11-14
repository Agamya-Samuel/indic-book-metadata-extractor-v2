"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getDashboardSummary,
  getDashboardBooks,
  getDashboardJobs,
  cancelJob,
  deleteBook,
  resetBook,
  rerunOcr,
  rerunExtraction,
  getThumbnailUrl,
  type BookSearchResult,
  type DashboardJobRow,
} from "@/lib/api";
import StatCard from "@/components/shared/stat-card";
import StatusBadge from "@/components/shared/status-badge";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { Progress } from "@/components/shared/progress";
import {
  ActionMenu,
  MenuButton,
  MenuLink,
  MenuSeparator,
} from "@/components/shared/action-menu";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import Pagination from "@/components/shared/pagination";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Select } from "@/components/shared/input";
import { LinkButton } from "@/components/shared/button";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";
import { Skeleton } from "@/components/shared/skeleton";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";

const JOB_STATUSES = ["queued", "running", "completed", "failed", "cancelled"];
const JOB_TYPES = ["page_extraction", "ocr", "llm", "preprocessing"];

const PAGE_SIZE = DEFAULT_PAGE_SIZE;

function workflowHref(book: BookSearchResult): string {
  switch (book.status) {
    case "uploaded":
      return `/books/${book.id}/select-pages`;
    case "pages_selected":
      return `/books/${book.id}/preprocessing`;
    case "ocr_running":
    case "ocr_complete":
      return `/books/${book.id}/ocr-review`;
    case "llm_running":
      return `/books/${book.id}/llm-config`;
    case "awaiting_review":
    case "complete":
      return `/books/${book.id}/metadata-review`;
    default:
      return `/books/${book.id}`;
  }
}

function workflowLabel(status: string): string {
  switch (status) {
    case "uploaded":
      return "Select pages";
    case "pages_selected":
      return "Preprocessing";
    case "ocr_running":
      return "OCR running";
    case "ocr_complete":
      return "OCR review";
    case "llm_running":
      return "LLM config";
    case "awaiting_review":
    case "complete":
      return "Metadata review";
    default:
      return "Open workflow";
  }
}

export default function DashboardPage() {
  useDocumentTitle("Dashboard");

  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [bookPage, setBookPage] = React.useState(1);
  const [jobPage, setJobPage] = React.useState(1);
  const [confirmAction, setConfirmAction] = React.useState<
    | { type: "delete"; book: BookSearchResult }
    | { type: "reset"; book: BookSearchResult }
    | null
  >(null);

  // ── Queries ──────────────────────────────────────────────────────────────
  const { data: summary } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    staleTime: 5 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const jobs = q.state.data?.jobs;
      const active = (jobs?.queued ?? 0) + (jobs?.running ?? 0);
      return active > 0 ? 5_000 : 30_000;
    },
  });

  const { data: booksData, isLoading: booksLoading } = useQuery({
    queryKey: ["dashboard-books", bookPage],
    queryFn: () => getDashboardBooks({ page: bookPage, page_size: PAGE_SIZE }),
    staleTime: 5 * 1000,
  });

  const jobsParams = {
    status: statusFilter || undefined,
    job_type: (typeFilter || undefined) as
      | "page_extraction"
      | "ocr"
      | "llm"
      | "preprocessing"
      | undefined,
    page: jobPage,
    page_size: PAGE_SIZE,
  };

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["dashboard-jobs", jobsParams],
    queryFn: () => getDashboardJobs(jobsParams),
    staleTime: 3 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      const jobs = q.state.data?.items;
      const hasActive =
        jobs?.some((j) => j.status === "queued" || j.status === "running") ??
        false;
      return hasActive ? 5_000 : 30_000;
    },
  });

  // ── Mutations ────────────────────────────────────────────────────────────
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    qc.invalidateQueries({ queryKey: ["dashboard-books"] });
    qc.invalidateQueries({ queryKey: ["dashboard-jobs"] });
    qc.invalidateQueries({ queryKey: ["library"] });
  };

  const deleteOne = useMutation({
    mutationFn: (id: string) => deleteBook(id),
    onSuccess: () => {
      toast.success("Book deleted");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const resetOne = useMutation({
    mutationFn: (id: string) => resetBook(id),
    onSuccess: () => {
      toast.success("Book reset to 'uploaded'");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const rerunOcrOne = useMutation({
    mutationFn: (id: string) => rerunOcr(id),
    onSuccess: () => {
      toast.success("OCR re-run queued");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const rerunExtOne = useMutation({
    mutationFn: (id: string) => rerunExtraction(id),
    onSuccess: () => {
      toast.success("Extraction re-run queued");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const cancelOne = useMutation({
    mutationFn: (id: string) => cancelJob(id),
    onSuccess: () => {
      toast.success("Job cancelled");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const pending =
    deleteOne.isPending ||
    resetOne.isPending ||
    rerunOcrOne.isPending ||
    rerunExtOne.isPending ||
    cancelOne.isPending;

  const books = booksData?.items ?? [];
  const jobs = jobsData?.items ?? [];

  const summaryJobs = summary?.jobs;
  const activeJobs = (summaryJobs?.queued ?? 0) + (summaryJobs?.running ?? 0);
  const busy = summaryJobs ? activeJobs > 0 : undefined;
  const bookCount = summary?.books.total;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Dashboard"
        title="Your workspace"
        description={
          busy === undefined
            ? "Loading your books and jobs..."
            : busy
              ? "Jobs are processing — this page refreshes automatically."
              : bookCount
                ? `${bookCount} book${bookCount !== 1 ? "s" : ""} in your library. Everything is up to date.`
                : "Upload a book to get started."
        }
        actions={<LinkButton href="/upload">Upload book</LinkButton>}
      />

      {/* ── Summary ──────────────────────────────────────────────────────── */}
      <div className="space-y-4 sm:space-y-5 mb-6 sm:mb-8">
        <Card title="Library summary" description="Books you have uploaded">
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <StatCard
              label="Total books"
              value={summary?.books.total ?? "—"}
              tone="info"
              flush
            />
            <StatCard
              label="Complete"
              value={summary?.books.by_status?.complete ?? 0}
              sublabel="fully processed"
              tone="success"
              flush
            />
            <StatCard
              label="Awaiting review"
              value={summary?.books.by_status?.awaiting_review ?? 0}
              sublabel="extraction finished — needs your check"
              tone={
                summary && (summary.books.by_status?.awaiting_review ?? 0) > 0
                  ? "warning"
                  : "neutral"
              }
              flush
            />
          </div>
        </Card>

        <Card title="Job activity" description="OCR and extraction activity on your books">
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <StatCard
              label="Active jobs"
              value={busy === undefined ? "—" : activeJobs}
              sublabel={`${summaryJobs?.queued ?? 0} queued · ${summaryJobs?.running ?? 0} running`}
              tone={busy ? "info" : "neutral"}
              flush
            />
            <StatCard
              label="Completed"
              value={summaryJobs?.completed ?? "—"}
              tone="success"
              flush
            />
            <StatCard
              label="Failed"
              value={summaryJobs?.failed ?? "—"}
              tone={
                summaryJobs && summaryJobs.failed > 0 ? "danger" : "neutral"
              }
              flush
            />
          </div>
        </Card>

        <Card
          title="Queue"
          description="Queued jobs in each worker queue — how many jobs are ahead of yours"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border)] -my-4">
            <StatCard
              label="OCR queue"
              value={summary?.queue.ocr ?? "—"}
              sublabel="preprocessing + OCR jobs waiting"
              flush
            />
            <StatCard
              label="LLM queue"
              value={summary?.queue.llm ?? "—"}
              sublabel="metadata extraction jobs waiting"
              flush
            />
          </div>
        </Card>
      </div>

      {/* ── Your books ───────────────────────────────────────────────────── */}
      <Card
        className="mb-6"
        title="Your books"
        description={
          booksData
            ? `${booksData.total} book${booksData.total !== 1 ? "s" : ""}`
            : "Loading…"
        }
        headerAction={<LinkButton href="/upload" size="sm">Upload book</LinkButton>}
      >
        {booksLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : books.length === 0 ? (
          <EmptyState
            title="No books yet"
            description="Upload a scanned book to run OCR and extract metadata. Your books and their jobs appear here."
            action={
              <LinkButton href="/upload">Upload your first book</LinkButton>
            }
          />
        ) : (
          <Stack gap={4}>
            <BookTable
              books={books}
              busy={pending}
              onReset={(book) => setConfirmAction({ type: "reset", book })}
              onDelete={(book) => setConfirmAction({ type: "delete", book })}
              onRerunOcr={(book) => rerunOcrOne.mutate(book.id)}
              onRerunExtraction={(book) => rerunExtOne.mutate(book.id)}
            />
            <Pagination
              page={bookPage}
              totalPages={booksData?.total_pages ?? 0}
              onPageChange={setBookPage}
            />
          </Stack>
        )}
      </Card>

      {/* ── Your jobs ────────────────────────────────────────────────────── */}
      <Card
        title="Your jobs"
        description={
          jobsData
            ? `${jobsData.total} job${jobsData.total !== 1 ? "s" : ""}`
            : "Loading…"
        }
      >
        <Stack gap={3}>
          <div className="flex flex-wrap gap-3 items-end">
            <div className="w-40">
              <Field label="Status" htmlFor="dashboard-job-status">
                <Select
                  id="dashboard-job-status"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setJobPage(1);
                  }}
                >
                  <option value="">All</option>
                  {JOB_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="w-40">
              <Field label="Type" htmlFor="dashboard-job-type">
                <Select
                  id="dashboard-job-type"
                  value={typeFilter}
                  onChange={(e) => {
                    setTypeFilter(e.target.value);
                    setJobPage(1);
                  }}
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

          {jobsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-14" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <EmptyState
              title="No jobs match your filters"
              description="Jobs appear here once you run OCR or extraction on your books."
            />
          ) : (
            <>
              <JobTable
                jobs={jobs}
                onCancel={(job) => cancelOne.mutate(job.id)}
                cancelPending={cancelOne.isPending}
              />
              <Pagination
                page={jobPage}
                totalPages={jobsData?.total_pages ?? 0}
                onPageChange={setJobPage}
              />
            </>
          )}
        </Stack>
      </Card>

      {/* ── Confirmations ────────────────────────────────────────────────── */}
      <ConfirmDialog
        open={confirmAction?.type === "delete"}
        onClose={() => setConfirmAction(null)}
        onConfirm={async () => {
          if (confirmAction?.type === "delete") {
            await deleteOne.mutateAsync(confirmAction.book.id);
          }
          setConfirmAction(null);
        }}
        title="Delete this book?"
        description={
          confirmAction?.type === "delete" ? (
            <span>
              This permanently deletes{" "}
              <strong className="font-semibold text-[var(--text)]">
                {bookTitle(confirmAction.book)}
              </strong>{" "}
              and all of its pages, OCR results, metadata, and jobs. This cannot
              be undone.
            </span>
          ) : null
        }
        confirmLabel="Delete book"
        requireTyped="delete"
        loading={deleteOne.isPending}
      />
      <ConfirmDialog
        open={confirmAction?.type === "reset"}
        onClose={() => setConfirmAction(null)}
        onConfirm={async () => {
          if (confirmAction?.type === "reset") {
            await resetOne.mutateAsync(confirmAction.book.id);
          }
          setConfirmAction(null);
        }}
        title="Reset this book?"
        description={
          confirmAction?.type === "reset" ? (
            <span>
              Removes pages, OCR results, metadata, and jobs for{" "}
              <strong className="font-semibold text-[var(--text)]">
                {bookTitle(confirmAction.book)}
              </strong>
              . The original PDF is kept — you can re-select pages and re-run
              processing.
            </span>
          ) : null
        }
        confirmLabel="Reset"
        variant="warning"
        loading={resetOne.isPending}
      />
    </PageContainer>
  );
}

function bookTitle(book: BookSearchResult): string {
  return (
    book.title || book.filename.replace(/\.pdf$/i, "")
  );
}

// ---------------------------------------------------------------------------
// Book row
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Job table
// ---------------------------------------------------------------------------

function queueLabel(job: DashboardJobRow): React.ReactNode {
  if (job.status === "running") return "Running now";
  if (job.status === "queued") {
    if (job.queue_ahead === 0) return "Next up";
    if (job.queue_ahead != null) return `${job.queue_ahead} ahead`;
    return "Queued";
  }
  return "—";
}

function BookTable({
  books,
  busy,
  onReset,
  onDelete,
  onRerunOcr,
  onRerunExtraction,
}: {
  books: BookSearchResult[];
  busy: boolean;
  onReset: (book: BookSearchResult) => void;
  onDelete: (book: BookSearchResult) => void;
  onRerunOcr: (book: BookSearchResult) => void;
  onRerunExtraction: (book: BookSearchResult) => void;
}) {
  const columns: DataTableColumn<BookSearchResult>[] = [
    {
      key: "book",
      header: "Book",
      cell: (book) => (
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href={`/books/${book.id}`}
            className="relative h-14 w-11 shrink-0 overflow-hidden rounded-[var(--radius-xs)] border border-[var(--border)] bg-[var(--surface-sunken)]"
            aria-hidden="true"
            tabIndex={-1}
          >
            {book.total_pages ? (
              <Image
                src={getThumbnailUrl(book.id, 1)}
                alt=""
                fill
                sizes="44px"
                className="object-cover"
                unoptimized
              />
            ) : null}
          </Link>
          <div className="min-w-0">
            <Link
              href={`/books/${book.id}`}
              className="block truncate font-medium text-[var(--text)] hover:underline"
              title={bookTitle(book)}
            >
              {bookTitle(book)}
            </Link>
            <p
              className="truncate text-[length:var(--text-xs)] text-[var(--text-muted)]"
              title={book.filename}
            >
              {book.filename}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (book) => <StatusBadge status={book.status} />,
    },
    {
      key: "pages",
      header: "Pages",
      hideBelow: "sm",
      cell: (book) => (
        <span className="text-[length:var(--text-xs)] tabular-nums text-[var(--text-muted)]">
          {book.total_pages ?? "-"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (book) => {
        const active =
          book.status === "ocr_running" || book.status === "llm_running";
        // The pipeline has pages from pages_selected onward, so re-running OCR
        // is meaningless before that.
        const canRerunOcr = book.status !== "uploaded";
        const canRerunExt =
          book.status === "ocr_complete" ||
          book.status === "awaiting_review" ||
          book.status === "complete";
        return (
          <div className="flex justify-end">
            <ActionMenu
              disabled={busy}
              ariaLabel={`Actions for ${bookTitle(book)}`}
            >
              <MenuLink href={`/books/${book.id}`}>Open book detail</MenuLink>
              <MenuLink href={workflowHref(book)}>
                {workflowLabel(book.status)}
              </MenuLink>
              <MenuSeparator />
              {canRerunOcr && !active && (
                <MenuButton onClick={() => onRerunOcr(book)}>
                  Re-run OCR
                </MenuButton>
              )}
              {canRerunExt && !active && (
                <MenuButton onClick={() => onRerunExtraction(book)}>
                  Re-run extraction
                </MenuButton>
              )}
              {!active && (
                <MenuButton onClick={() => onReset(book)}>
                  Reset to uploaded…
                </MenuButton>
              )}
              <MenuButton danger onClick={() => onDelete(book)}>
                Delete…
              </MenuButton>
            </ActionMenu>
          </div>
        );
      },
    },
  ];

  return (
    <DataTable
      caption="Your books"
      columns={columns}
      rows={books}
      rowKey={(book) => book.id}
    />
  );
}

function JobTable({
  jobs,
  onCancel,
  cancelPending,
}: {
  jobs: DashboardJobRow[];
  onCancel: (job: DashboardJobRow) => void;
  cancelPending: boolean;
}) {
  const columns: DataTableColumn<DashboardJobRow>[] = [
    {
      key: "type",
      header: "Type",
      cell: (job) => (
        <span className="text-[length:var(--text-xs)] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
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
              className="max-w-xs truncate text-[10px] text-[var(--danger-700)] dark:text-[var(--danger-100)]"
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
      key: "queue",
      header: "Queue",
      cell: (job) => {
        const active = job.status === "queued" || job.status === "running";
        if (!active) {
          return (
            <span aria-hidden="true" className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
              -
            </span>
          );
        }
        return (
          <span
            className="whitespace-nowrap text-[length:var(--text-xs)] text-[var(--text-muted)]"
            title={
              job.queue_ahead === 0
                ? "This job runs next"
                : `${job.queue_ahead} job(s) will run before this one`
            }
          >
            {queueLabel(job)}
          </span>
        );
      },
    },
    {
      key: "progress",
      header: "Progress",
      hideBelow: "lg",
      cell: (job) =>
        job.status === "running" || job.status === "completed" ? (
          <div className="min-w-[140px]">
            <Progress
              value={job.progress}
              tone={job.status === "completed" ? "success" : "accent"}
              showValue
            />
          </div>
        ) : (
          <span aria-hidden="true" className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
            -
          </span>
        ),
    },
    {
      key: "created",
      header: "Created",
      hideBelow: "lg",
      cell: (job) => (
        <span className="whitespace-nowrap text-[length:var(--text-xs)] tabular-nums text-[var(--text-muted)]">
          {job.created_at ? new Date(job.created_at).toLocaleString() : "-"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (job) => {
        const active = job.status === "queued" || job.status === "running";
        return (
          <div className="flex items-center justify-end gap-3">
            {job.book_id && (
              <Link
                href={`/books/${job.book_id}`}
                className="text-[length:var(--text-sm)] text-[var(--accent-text)] hover:underline"
              >
                Open
              </Link>
            )}
            {active && (
              <button
                type="button"
                onClick={() => onCancel(job)}
                disabled={cancelPending}
                className="text-[length:var(--text-sm)] text-[var(--danger-700)] hover:underline disabled:opacity-50 dark:text-[var(--danger-100)]"
              >
                Cancel
              </button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <DataTable
      caption="Your jobs"
      columns={columns}
      rows={jobs}
      rowKey={(job) => job.id}
    />
  );
}

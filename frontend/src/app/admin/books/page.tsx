"use client";

import * as React from "react";
import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminBooks,
  deleteAdminBook,
  resetAdminBook,
  rerunAdminOcr,
  rerunAdminExtraction,
  getThumbnailUrl,
  type BookSearchResult,
} from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Button } from "@/components/shared/button";
import {
  ActionMenu,
  MenuButton,
  MenuLink,
  MenuSeparator,
} from "@/components/shared/action-menu";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import OwnerFilter, { type OwnerSelection } from "@/components/admin/owner-filter";
import Pagination from "@/components/shared/pagination";
import { PageContainer, Card, PageHeader, Stack } from "@/components/shared/card";
import { Field, Input, Select } from "@/components/shared/input";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";

const LANGUAGE_LABELS: Record<string, string> = {
  tel: "Telugu",
  hin: "Hindi",
};

const STATUSES = [
  "uploaded",
  "pages_selected",
  "ocr_running",
  "ocr_complete",
  "llm_running",
  "complete",
];

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
    case "complete":
      return "Metadata review";
    default:
      return "Open workflow";
  }
}

export default function AdminBooksPage() {
  useDocumentTitle("Admin · Books");

  const qc = useQueryClient();

  const [search, setSearch] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [language, setLanguage] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [hasMetadataOnly, setHasMetadataOnly] = React.useState(false);
  const [owner, setOwner] = React.useState<OwnerSelection | null>(null);
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [confirmAction, setConfirmAction] = React.useState<null | {
    type: "reset" | "delete";
    book: BookSearchResult;
  }>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const [pageSize, setPageSize] = React.useState(DEFAULT_PAGE_SIZE);

  const resetPagination = React.useCallback(() => {
    setPage(1);
    setSelected(new Set());
  }, []);

  const handleLanguageChange = (v: string) => {
    setLanguage(v);
    resetPagination();
  };
  const handleStatusChange = (v: string) => {
    setStatusFilter(v);
    resetPagination();
  };
  const handleHasMetadataChange = (v: boolean) => {
    setHasMetadataOnly(v);
    resetPagination();
  };
  const handleOwnerChange = (v: OwnerSelection | null) => {
    setOwner(v);
    resetPagination();
  };

  const params = {
    query: debouncedSearch || undefined,
    language: language || undefined,
    status: statusFilter || undefined,
    has_metadata: hasMetadataOnly || undefined,
    owner_id: owner?.id,
    page,
    page_size: pageSize,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["admin-books", params],
    queryFn: () => getAdminBooks(params),
    staleTime: 15 * 1000,
  });

  const items = data?.items ?? [];
  const bookLabel = (book: BookSearchResult) =>
    book.title || book.filename.replace(/\.pdf$/i, "");
  const totalPages = data?.total_pages ?? 0;
  const total = data?.total ?? 0;

  const allChecked = items.length > 0 && items.every((b) => selected.has(b.id));
  const someChecked = items.some((b) => selected.has(b.id));

  const toggleAll = () => {
    if (allChecked) {
      setSelected((prev) => {
        const next = new Set(prev);
        items.forEach((b) => next.delete(b.id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        items.forEach((b) => next.add(b.id));
        return next;
      });
    }
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-books"] });
    qc.invalidateQueries({ queryKey: ["admin-stats"] });
    setSelected(new Set());
  };

  const deleteOne = useMutation({
    mutationFn: (id: string) => deleteAdminBook(id),
    onSuccess: () => {
      toast.success("Book deleted");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const resetOne = useMutation({
    mutationFn: (id: string) => resetAdminBook(id),
    onSuccess: () => {
      toast.success("Book reset to 'uploaded'");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const rerunOcr = useMutation({
    mutationFn: (id: string) => rerunAdminOcr(id),
    onSuccess: () => {
      toast.success("OCR re-run queued");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const rerunExt = useMutation({
    mutationFn: (id: string) => rerunAdminExtraction(id),
    onSuccess: () => {
      toast.success("Extraction re-run queued");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  // Only the row whose action is in flight shows a pending state.
  const pendingId: string | null = deleteOne.isPending
    ? deleteOne.variables ?? null
    : resetOne.isPending
      ? resetOne.variables ?? null
      : rerunOcr.isPending
        ? rerunOcr.variables ?? null
        : rerunExt.isPending
          ? rerunExt.variables ?? null
          : null;

  const columns: DataTableColumn<BookSearchResult>[] = [
    {
      key: "select",
      header: (
        <input
          type="checkbox"
          aria-label="Select all on this page"
          checked={allChecked}
          ref={(el) => {
            if (el) el.indeterminate = !allChecked && someChecked;
          }}
          onChange={toggleAll}
          className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
        />
      ),
      className: "w-10",
      cell: (book) => (
        <input
          type="checkbox"
          aria-label={`Select ${bookLabel(book)}`}
          checked={selected.has(book.id)}
          onChange={() => toggleOne(book.id)}
          className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
        />
      ),
    },
    {
      key: "book",
      header: "Book",
      cell: (book) => (
        <div className="flex min-w-0 items-center gap-3">
          <div className="relative h-10 w-8 shrink-0 overflow-hidden rounded-[var(--radius-xs)] border border-[var(--border)] bg-[var(--surface-sunken)]">
            {book.total_pages ? (
              <Image
                src={book.thumbnail_url || getThumbnailUrl(book.id, 1)}
                alt=""
                fill
                sizes="32px"
                className="object-cover"
                unoptimized
              />
            ) : null}
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium text-[var(--text)]" title={bookLabel(book)}>
              {bookLabel(book)}
            </p>
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
      key: "owner",
      header: "Owner",
      hideBelow: "xl",
      cell: (book) => (
        <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
          {book.owner_display_name ?? "—"}
        </span>
      ),
    },
    {
      key: "language",
      header: "Language",
      hideBelow: "md",
      cell: (book) => (
        <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
          {LANGUAGE_LABELS[book.language] || book.language}
        </span>
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
        <span className="tabular-nums text-[length:var(--text-sm)] text-[var(--text-muted)]">
          {book.total_pages ?? "—"}
        </span>
      ),
    },
    {
      key: "metadata",
      header: "Metadata",
      hideBelow: "lg",
      cell: (book) =>
        book.metadata_fields ? (
          <span className="inline-flex items-center gap-1 text-[length:var(--text-sm)] text-[var(--success-700)] dark:text-[var(--success-100)]">
            <svg
              viewBox="0 0 20 20"
              className="size-3.5 fill-current"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 011.42-1.42L8.5 12.08l6.79-6.79a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            Yes
          </span>
        ) : (
          <span className="text-[length:var(--text-sm)] text-[var(--text-muted)]">—</span>
        ),
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (book) => {
        const canRerunOcr =
          book.status === "pages_selected" ||
          book.status === "ocr_running" ||
          book.status === "ocr_complete" ||
          book.status === "llm_running" ||
          book.status === "complete";
        const canRerunExt =
          book.status === "ocr_complete" || book.status === "complete";
        return (
          <div className="flex justify-end">
            <ActionMenu
              disabled={pendingId === book.id}
              ariaLabel={`Actions for ${bookLabel(book)}`}
            >
              <MenuLink href={`/books/${book.id}`}>Open book detail</MenuLink>
              <MenuLink href={workflowHref(book)}>
                {workflowLabel(book.status)}
              </MenuLink>
              <MenuSeparator />
              {canRerunOcr && (
                <MenuButton onClick={() => rerunOcr.mutate(book.id)}>
                  Re-run OCR
                </MenuButton>
              )}
              {canRerunExt && (
                <MenuButton onClick={() => rerunExt.mutate(book.id)}>
                  Re-run extraction
                </MenuButton>
              )}
              <MenuButton
                onClick={() => setConfirmAction({ type: "reset", book })}
              >
                Reset to uploaded…
              </MenuButton>
              <MenuButton
                danger
                onClick={() => setConfirmAction({ type: "delete", book })}
              >
                Delete…
              </MenuButton>
            </ActionMenu>
          </div>
        );
      },
    },
  ];

  const bulkDelete = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) {
        await deleteAdminBook(id);
      }
    },
    onSuccess: (_, ids) => {
      toast.success(`${ids.length} book${ids.length !== 1 ? "s" : ""} deleted`);
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const bulkReset = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) {
        await resetAdminBook(id);
      }
    },
    onSuccess: (_, ids) => {
      toast.success(`${ids.length} book${ids.length !== 1 ? "s" : ""} reset`);
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Admin"
        title="Books"
        description={
          <>
            {total} book{total !== 1 ? "s" : ""} in the library
            {selected.size > 0 && ` · ${selected.size} selected`}
          </>
        }
      />
      <Card className="mb-4" title="Filters">
        <Stack gap={3}>
          <div>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="flex-1 min-w-[220px]">
                <Field label="Search" htmlFor="admin-book-search">
                  <Input
                    id="admin-book-search"
                    type="text"
                    placeholder="Title or filename…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </Field>
              </div>
              <div className="w-40">
                <Field label="Language" htmlFor="admin-book-language">
                  <Select
                    id="admin-book-language"
                    value={language}
                    onChange={(e) => handleLanguageChange(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="tel">Telugu</option>
                    <option value="hin">Hindi</option>
                  </Select>
                </Field>
              </div>
              <div className="w-48">
                <Field label="Status" htmlFor="admin-book-status">
                  <Select
                    id="admin-book-status"
                    value={statusFilter}
                    onChange={(e) => handleStatusChange(e.target.value)}
                  >
                    <option value="">All statuses</option>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.replace(/_/g, " ")}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <label className="inline-flex items-center gap-2 self-end h-10 px-1 text-[length:var(--text-sm)] text-[var(--text)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasMetadataOnly}
                  onChange={(e) => handleHasMetadataChange(e.target.checked)}
                  className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
                />
                Has metadata only
              </label>
              <OwnerFilter value={owner} onChange={handleOwnerChange} id="admin-book-owner" />
            </div>
          </div>

          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-2 text-[length:var(--text-sm)]">
              <span className="font-medium text-[var(--accent-soft-text)]">
                {selected.size} selected
              </span>
              <div className="ml-auto flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => bulkReset.mutate(Array.from(selected))}
                  disabled={bulkReset.isPending}
                  loading={bulkReset.isPending}
                >
                  Reset selected
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => bulkDelete.mutate(Array.from(selected))}
                  disabled={bulkDelete.isPending}
                  loading={bulkDelete.isPending}
                >
                  Delete selected
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelected(new Set())}
                >
                  Clear
                </Button>
              </div>
            </div>
          )}
        </Stack>
      </Card>

      {isLoading ? (
        <div className="mt-6 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)] animate-pulse"
              />
            ))}
          </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No books match your filters"
          description="Try adjusting the search or clearing filters."
        />
      ) : (
        <>
          <DataTable
            caption="Books"
            columns={columns}
            rows={items}
            rowKey={(book) => book.id}
            rowClassName={(book) =>
              selected.has(book.id) ? "bg-[var(--accent-soft)]/40" : undefined
            }
          />

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            pageSize={pageSize}
            onPageSizeChange={(v) => {
              setPageSize(v);
              setPage(1);
            }}
            disabled={isLoading}
          />
        </>
      )}
    <ConfirmDialog
        open={confirmAction?.type === "delete"}
        onClose={() => setConfirmAction(null)}
        onConfirm={async () => {
          if (!confirmAction) return;
          try {
            await deleteOne.mutateAsync(confirmAction.book.id);
          } finally {
            setConfirmAction(null);
          }
        }}
        title="Delete this book?"
        description={
          confirmAction ? (
            <span>
              This permanently deletes{" "}
              <strong className="font-semibold text-[var(--text)]">
                {bookLabel(confirmAction.book)}
              </strong>{" "}
              and all of its pages, OCR results, metadata, and jobs. This cannot
              be undone.
            </span>
          ) : null
        }
        confirmLabel="Delete book"
        requireTyped="delete"
      />
      <ConfirmDialog
        open={confirmAction?.type === "reset"}
        onClose={() => setConfirmAction(null)}
        onConfirm={async () => {
          if (!confirmAction) return;
          try {
            await resetOne.mutateAsync(confirmAction.book.id);
          } finally {
            setConfirmAction(null);
          }
        }}
        title="Reset this book?"
        description={
          confirmAction ? (
            <span>
              Removes pages, OCR results, metadata, and jobs for{" "}
              <strong className="font-semibold text-[var(--text)]">
                {bookLabel(confirmAction.book)}
              </strong>
              . The original PDF is kept — you can re-select pages and re-run
              processing.
            </span>
          ) : null
        }
        confirmLabel="Reset"
        variant="warning"
      />
    </PageContainer>
  );
}


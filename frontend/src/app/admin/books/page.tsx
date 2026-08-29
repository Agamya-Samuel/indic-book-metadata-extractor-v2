"use client";

import * as React from "react";
import Link from "next/link";
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
import { Button } from "@/components/shared/button";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Input, Select } from "@/components/shared/input";
import { SkeletonPageHeader } from "@/components/shared/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

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
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

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

  const params = {
    query: debouncedSearch || undefined,
    language: language || undefined,
    status: statusFilter || undefined,
    has_metadata: hasMetadataOnly || undefined,
    page,
    page_size: 50,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["admin-books", params],
    queryFn: () => getAdminBooks(params),
    staleTime: 15 * 1000,
  });

  const items = data?.items ?? [];
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
        description={`${total} book${total !== 1 ? "s" : ""} in the library`}
      />

      <Card className="mb-4">
        <Stack gap={3}>
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
            <label className="inline-flex items-center gap-2 self-center h-10 px-1 text-[var(--text-sm)] text-[var(--text)] cursor-pointer">
              <input
                type="checkbox"
                checked={hasMetadataOnly}
                onChange={(e) => handleHasMetadataChange(e.target.checked)}
                className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
              />
              Has metadata only
            </label>
          </div>

          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-3 py-2 text-[var(--text-sm)]">
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
        <>
          <SkeletonPageHeader />
          <div className="mt-6 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)] animate-pulse"
              />
            ))}
          </div>
        </>
      ) : items.length === 0 ? (
        <EmptyState
          title="No books match your filters"
          description="Try adjusting the search or clearing filters."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-xs)]">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--surface-sunken)]/60 text-[var(--text-xs)] uppercase tracking-wider text-[var(--text-muted)]">
                  <tr>
                    <th className="px-3 py-2.5 w-10">
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
                    </th>
                    <th className="px-3 py-2.5 text-left font-medium">Book</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden md:table-cell">Language</th>
                    <th className="px-3 py-2.5 text-left font-medium">Status</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden sm:table-cell">Pages</th>
                    <th className="px-3 py-2.5 text-left font-medium hidden lg:table-cell">Metadata</th>
                    <th className="px-3 py-2.5 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {items.map((book) => (
                    <BookRow
                      key={book.id}
                      book={book}
                      isSelected={selected.has(book.id)}
                      onToggleSelect={() => toggleOne(book.id)}
                      onReset={() => resetOne.mutate(book.id)}
                      onDelete={() => deleteOne.mutate(book.id)}
                      onRerunOcr={() => rerunOcr.mutate(book.id)}
                      onRerunExtraction={() => rerunExt.mutate(book.id)}
                      pending={
                        deleteOne.isPending ||
                        resetOne.isPending ||
                        rerunOcr.isPending ||
                        rerunExt.isPending
                      }
                    />
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
    </PageContainer>
  );
}

function BookRow({
  book,
  isSelected,
  onToggleSelect,
  onReset,
  onDelete,
  onRerunOcr,
  onRerunExtraction,
  pending,
}: {
  book: BookSearchResult;
  isSelected: boolean;
  onToggleSelect: () => void;
  onReset: () => void;
  onDelete: () => void;
  onRerunOcr: () => void;
  onRerunExtraction: () => void;
  pending: boolean;
}) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [confirm, setConfirm] = React.useState<null | "reset" | "delete">(null);
  const menuRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [menuOpen]);

  const title = book.title || book.filename.replace(/\.pdf$/i, "");

  const canRerunOcr =
    book.status === "pages_selected" ||
    book.status === "ocr_running" ||
    book.status === "ocr_complete" ||
    book.status === "llm_running" ||
    book.status === "complete";

  const canRerunExt =
    book.status === "ocr_complete" || book.status === "complete";

  return (
    <tr className={cn("hover:bg-[var(--surface-sunken)]/40", isSelected && "bg-[var(--accent-soft)]/40")}>
      <td className="px-3 py-2.5 align-middle">
        <input
          type="checkbox"
          aria-label={`Select ${title}`}
          checked={isSelected}
          onChange={onToggleSelect}
          className="size-4 rounded border-[var(--border)] accent-[var(--accent)]"
        />
      </td>
      <td className="px-3 py-2.5 align-middle">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative h-10 w-8 shrink-0 overflow-hidden rounded-[var(--radius-xs)] bg-[var(--surface-sunken)] border border-[var(--border)]">
            {book.total_pages ? (
              <Image
                src={getThumbnailUrl(book.id, 1)}
                alt=""
                fill
                sizes="32px"
                className="object-cover"
                unoptimized
              />
            ) : null}
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium text-[var(--text)]" title={title}>
              {title}
            </p>
            <p className="truncate text-[var(--text-xs)] text-[var(--text-muted)]" title={book.filename}>
              {book.filename}
            </p>
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5 align-middle hidden md:table-cell text-[var(--text-sm)] text-[var(--text-muted)]">
        {LANGUAGE_LABELS[book.language] || book.language}
      </td>
      <td className="px-3 py-2.5 align-middle">
        <StatusBadge status={book.status} />
      </td>
      <td className="px-3 py-2.5 align-middle hidden sm:table-cell tabular-nums text-[var(--text-sm)] text-[var(--text-muted)]">
        {book.total_pages ?? "—"}
      </td>
      <td className="px-3 py-2.5 align-middle hidden lg:table-cell">
        {book.metadata_fields ? (
          <span className="inline-flex items-center gap-1 text-[var(--success-700)] dark:text-[var(--success-100)] text-[var(--text-sm)]">
            <svg viewBox="0 0 20 20" className="size-3.5 fill-current" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M16.704 5.29a1 1 0 010 1.42l-7.5 7.5a1 1 0 01-1.42 0l-3.5-3.5a1 1 0 011.42-1.42L8.5 12.08l6.79-6.79a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            Yes
          </span>
        ) : (
          <span className="text-[var(--text-muted)] text-[var(--text-sm)]">—</span>
        )}
      </td>
      <td className="px-3 py-2.5 align-middle text-right">
        <div className="relative inline-block" ref={menuRef}>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            disabled={pending}
          >
            Actions
            <svg viewBox="0 0 20 20" fill="currentColor" className="size-3.5" aria-hidden="true">
              <path d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" />
            </svg>
          </Button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-1 w-56 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)] py-1 z-20 text-left"
            >
              <MenuLink href={`/library/${book.id}`}>Open in library</MenuLink>
              <MenuLink href={workflowHref(book)}>{workflowLabel(book.status)}</MenuLink>
              <div className="my-1 border-t border-[var(--border)]" />
              {canRerunOcr && (
                <MenuButton
                  onClick={() => {
                    setMenuOpen(false);
                    onRerunOcr();
                  }}
                >
                  Re-run OCR
                </MenuButton>
              )}
              {canRerunExt && (
                <MenuButton
                  onClick={() => {
                    setMenuOpen(false);
                    onRerunExtraction();
                  }}
                >
                  Re-run extraction
                </MenuButton>
              )}
              <MenuButton
                onClick={() => {
                  setMenuOpen(false);
                  setConfirm("reset");
                }}
              >
                Reset to uploaded…
              </MenuButton>
              <MenuButton
                danger
                onClick={() => {
                  setMenuOpen(false);
                  setConfirm("delete");
                }}
              >
                Delete…
              </MenuButton>
            </div>
          )}
        </div>
      </td>

      <ConfirmDialog
        open={confirm === "delete"}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          await onDelete();
          setConfirm(null);
        }}
        title="Delete this book?"
        description={
          <span>
            This permanently deletes{" "}
            <strong className="font-semibold text-[var(--text)]">{title}</strong>{" "}
            and all of its pages, OCR results, metadata, and jobs. This cannot
            be undone.
          </span>
        }
        confirmLabel="Delete book"
        requireTyped="delete"
      />
      <ConfirmDialog
        open={confirm === "reset"}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          await onReset();
          setConfirm(null);
        }}
        title="Reset this book?"
        description={
          <span>
            Removes pages, OCR results, metadata, and jobs for{" "}
            <strong className="font-semibold text-[var(--text)]">{title}</strong>.
            The original PDF is kept — you can re-select pages and re-run
            processing.
          </span>
        }
        confirmLabel="Reset"
        variant="warning"
      />
    </tr>
  );
}

function MenuLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      role="menuitem"
      className="block px-3 py-2 text-[var(--text-sm)] text-[var(--text)] hover:bg-[var(--surface-sunken)] focus-visible:bg-[var(--surface-sunken)] focus:outline-none"
    >
      {children}
    </Link>
  );
}

function MenuButton({
  onClick,
  children,
  danger,
}: {
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cn(
        "block w-full text-left px-3 py-2 text-[var(--text-sm)] hover:bg-[var(--surface-sunken)] focus-visible:bg-[var(--surface-sunken)] focus:outline-none",
        danger
          ? "text-[var(--danger-700)] dark:text-[var(--danger-300)]"
          : "text-[var(--text)]",
      )}
    >
      {children}
    </button>
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
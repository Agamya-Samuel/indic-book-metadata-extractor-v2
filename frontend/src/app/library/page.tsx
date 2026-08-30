"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getLibraryBooks,
  getFilterOptions,
  type LibrarySearchParams,
} from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { createBookFuse, fuseSearch } from "@/lib/fuse-config";
import BookCard from "@/components/library/book-card";
import { LibrarySkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Field, Input, Select } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { EmptyState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function LibraryPage() {
  useDocumentTitle("Library");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [useServerSearch, setUseServerSearch] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState<{
    language: string;
    status: string;
    genre: string;
    publisher: string;
  }>({ language: "", status: "", genre: "", publisher: "" });
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pageSize = 20;

  const apiParams: LibrarySearchParams = useMemo(
    () => ({
      query: useServerSearch ? debouncedQuery : undefined,
      language: filters.language || undefined,
      status: filters.status || undefined,
      genre: filters.genre || undefined,
      publisher: filters.publisher || undefined,
      page: currentPage,
      page_size: pageSize,
    }),
    [useServerSearch, debouncedQuery, filters, currentPage]
  );

  const { data: booksData, isLoading } = useQuery({
    queryKey: ["library", apiParams],
    queryFn: () => getLibraryBooks(apiParams),
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: filterOptions } = useQuery({
    queryKey: ["library-filters"],
    queryFn: getFilterOptions,
    staleTime: 2 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const allBooks = useMemo(
    () => booksData?.items ?? [],
    [booksData?.items]
  );
  const fuse = useMemo(() => createBookFuse(allBooks), [allBooks]);

  const fuseResults = useMemo(() => {
    if (useServerSearch || !debouncedQuery) return null;
    return fuseSearch(fuse, debouncedQuery);
  }, [fuse, debouncedQuery, useServerSearch]);

  const displayBooks = useMemo(() => {
    if (fuseResults) return fuseResults;
    return allBooks;
  }, [fuseResults, allBooks]);

  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [searchQuery]);

  const handleSearchSubmit = useCallback(() => {
    setDebouncedQuery(searchQuery);
    setUseServerSearch(true);
    setCurrentPage(1);
  }, [searchQuery]);

  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleSearchSubmit();
      }
    },
    [handleSearchSubmit]
  );

  const handleClearSearch = useCallback(() => {
    setSearchQuery("");
    setDebouncedQuery("");
    setUseServerSearch(false);
    setCurrentPage(1);
  }, []);

  const handleFilterChange = useCallback(
    (key: string, value: string) => {
      setFilters((prev) => ({ ...prev, [key]: value }));
      setCurrentPage(1);
    },
    []
  );

  const totalPages = booksData?.total_pages ?? 0;
  const total = booksData?.total ?? 0;

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <PageContainer>
        <PageHeader
          title="Library"
          description={
            <>
              {total} book{total !== 1 ? "s" : ""}{" "}
              {useServerSearch && debouncedQuery
                ? `matching "${debouncedQuery}"`
                : "total"}
            </>
          }
          actions={<LinkButton href="/upload">Upload New Book</LinkButton>}
        />

        <Card className="mb-6">
          <Stack gap={3}>
            <div className="relative">
              <Input
                type="text"
                placeholder="Search by title, author, publisher..."
                className="pr-24"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (useServerSearch) setUseServerSearch(false);
                }}
                onKeyDown={handleSearchKeyDown}
                aria-label="Search library"
              />
              <div className="absolute inset-y-1 right-1 flex items-center gap-1">
                {searchQuery && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleClearSearch}
                  >
                    Clear
                  </Button>
                )}
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSearchSubmit}
                >
                  Search
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <Field label="Language">
                <Select
                  value={filters.language}
                  onChange={(e) => handleFilterChange("language", e.target.value)}
                  aria-label="Filter by language"
                >
                  <option value="">All Languages</option>
                  {(filterOptions?.languages ?? ["tel", "hin"]).map((l) => (
                    <option key={l} value={l}>
                      {getLanguageName(l)}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label="Status">
                <Select
                  value={filters.status}
                  onChange={(e) => handleFilterChange("status", e.target.value)}
                  aria-label="Filter by status"
                >
                  <option value="">All Statuses</option>
                  {(filterOptions?.statuses ?? [
                    "uploaded",
                    "pages_selected",
                    "ocr_running",
                    "ocr_complete",
                    "llm_running",
                    "awaiting_review",
                    "complete",
                  ]).map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </option>
                  ))}
                </Select>
              </Field>

              {filterOptions && filterOptions.genres.length > 0 && (
                <Field label="Genre">
                  <Select
                    value={filters.genre}
                    onChange={(e) => handleFilterChange("genre", e.target.value)}
                    aria-label="Filter by genre"
                  >
                    <option value="">All Genres</option>
                    {filterOptions.genres.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}

              {filterOptions && filterOptions.publishers.length > 0 && (
                <Field label="Publisher">
                  <Select
                    value={filters.publisher}
                    onChange={(e) =>
                      handleFilterChange("publisher", e.target.value)
                    }
                    aria-label="Filter by publisher"
                  >
                    <option value="">All Publishers</option>
                    {filterOptions.publishers.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
            </div>
          </Stack>
        </Card>

        {isLoading ? (
          <LibrarySkeleton />
        ) : displayBooks.length === 0 ? (
          debouncedQuery ? (
            <EmptyState
              title="No matches"
              description={`No books found matching "${debouncedQuery}". Try a different search term, or clear the filters above.`}
            />
          ) : (
            <EmptyState
              title="Your library is empty"
              description="Upload a scanned book to extract structured metadata. The system runs OCR, identifies bibliographic fields with a fine-tuned language model, and prepares the records for review."
              action={
                <div className="flex flex-col items-center gap-4">
                  <LinkButton href="/upload" size="lg">
                    Upload a book
                  </LinkButton>
                  <ol className="grid grid-cols-1 gap-2 text-left text-[var(--text-xs)] text-[var(--text-muted)] sm:grid-cols-3 sm:gap-6">
                    {[
                      { n: 1, t: "Upload a PDF" },
                      { n: 2, t: "Run OCR + LLM" },
                      { n: 3, t: "Review and export" },
                    ].map((s) => (
                      <li
                        key={s.n}
                        className="flex items-center gap-2"
                      >
                        <span
                          aria-hidden="true"
                          className="flex size-5 shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-[10px] font-semibold tabular-nums text-[var(--text-muted)]"
                        >
                          {s.n}
                        </span>
                        <span>{s.t}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              }
            />
          )
        ) : (
          <Stack gap={4}>
            {fuseResults && (
              <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                Showing {fuseResults.length} instant result
                {fuseResults.length !== 1 ? "s" : ""} from local index. Press
                Enter for full server search.
              </p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {displayBooks.map((book) => (
                <BookCard key={book.id} book={book} />
              ))}
            </div>

            {!fuseResults && totalPages > 1 && (
              <nav
                className="mt-6 flex flex-wrap items-center justify-center gap-2"
                aria-label="Pagination"
              >
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setCurrentPage((p) => Math.max(1, p - 1))
                  }
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(
                    (p) =>
                      p === 1 ||
                      p === totalPages ||
                      Math.abs(p - currentPage) <= 2
                  )
                  .map((p, i, arr) => (
                    <span key={p} className="flex items-center">
                      {i > 0 && arr[i - 1] !== p - 1 && (
                        <span className="px-1 text-[var(--text-muted)]">
                          ...
                        </span>
                      )}
                      <Button
                        variant={p === currentPage ? "primary" : "outline"}
                        size="sm"
                        onClick={() => setCurrentPage(p)}
                        aria-label={`Page ${p}`}
                        aria-current={p === currentPage ? "page" : undefined}
                      >
                        {p}
                      </Button>
                    </span>
                  ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setCurrentPage((p) => Math.min(totalPages, p + 1))
                  }
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </nav>
            )}
          </Stack>
        )}
      </PageContainer>
    </div>
  );
}

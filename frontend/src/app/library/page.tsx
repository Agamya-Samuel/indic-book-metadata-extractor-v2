"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";import { useQuery } from "@tanstack/react-query";
import {
  getLibraryBooks,
  getFilterOptions,
  type LibrarySearchParams,
} from "@/lib/api";
import { createBookFuse, fuseSearch } from "@/lib/fuse-config";
import BookCard from "@/components/library/book-card";

export default function LibraryPage() {
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
  });

  const { data: filterOptions } = useQuery({
    queryKey: ["library-filters"],
    queryFn: getFilterOptions,
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
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Library</h1>
              <p className="text-sm text-gray-500">
                {total} book{total !== 1 ? "s" : ""}{" "}
                {useServerSearch && debouncedQuery
                  ? `matching "${debouncedQuery}"`
                  : "total"}
              </p>
            </div>
            <a
              href="/upload"
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Upload New Book
            </a>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <div className="flex-1 min-w-[240px] relative">
              <input
                type="text"
                placeholder="Search by title, author, publisher..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (useServerSearch) setUseServerSearch(false);
                }}
                onKeyDown={handleSearchKeyDown}
                className="w-full px-4 py-2 pr-16 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="absolute right-1 top-1 flex gap-1">
                {searchQuery && (
                  <button
                    onClick={handleClearSearch}
                    className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
                  >
                    Clear
                  </button>
                )}
                <button
                  onClick={handleSearchSubmit}
                  className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Search
                </button>
              </div>
            </div>

            <select
              value={filters.language}
              onChange={(e) => handleFilterChange("language", e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm bg-white"
            >
              <option value="">All Languages</option>
              {(filterOptions?.languages ?? ["tel", "hin"]).map((l) => (
                <option key={l} value={l}>
                  {l === "tel" ? "Telugu" : l === "hin" ? "Hindi" : l}
                </option>
              ))}
            </select>

            <select
              value={filters.status}
              onChange={(e) => handleFilterChange("status", e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm bg-white"
            >
              <option value="">All Statuses</option>
              {(filterOptions?.statuses ?? [
                "uploaded",
                "pages_selected",
                "ocr_running",
                "ocr_complete",
                "llm_running",
                "complete",
              ]).map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </select>

            {filterOptions && filterOptions.genres.length > 0 && (
              <select
                value={filters.genre}
                onChange={(e) => handleFilterChange("genre", e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm bg-white"
              >
                <option value="">All Genres</option>
                {filterOptions.genres.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            )}

            {filterOptions && filterOptions.publishers.length > 0 && (
              <select
                value={filters.publisher}
                onChange={(e) =>
                  handleFilterChange("publisher", e.target.value)
                }
                className="px-3 py-2 border rounded-lg text-sm bg-white"
              >
                <option value="">All Publishers</option>
                {filterOptions.publishers.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
          </div>
        ) : displayBooks.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500">
              {debouncedQuery
                ? `No books found matching "${debouncedQuery}"`
                : "No books in the library yet."}
            </p>
            {!debouncedQuery && (
              <a
                href="/upload"
                className="mt-4 inline-block text-blue-600 hover:underline text-sm"
              >
                Upload your first book
              </a>
            )}
          </div>
        ) : (
          <>
            {fuseResults && (
              <p className="text-xs text-gray-400 mb-3">
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
              <div className="mt-8 flex items-center justify-center gap-2">
                <button
                  onClick={() =>
                    setCurrentPage((p) => Math.max(1, p - 1))
                  }
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(
                    (p) =>
                      p === 1 ||
                      p === totalPages ||
                      Math.abs(p - currentPage) <= 2
                  )
                  .map((p, i, arr) => (
                    <span key={p}>
                      {i > 0 && arr[i - 1] !== p - 1 && (
                        <span className="px-1 text-gray-400">...</span>
                      )}
                      <button
                        onClick={() => setCurrentPage(p)}
                        className={`px-3 py-1.5 text-sm border rounded ${
                          p === currentPage
                            ? "bg-blue-600 text-white border-blue-600"
                            : "hover:bg-gray-50"
                        }`}
                      >
                        {p}
                      </button>
                    </span>
                  ))}
                <button
                  onClick={() =>
                    setCurrentPage((p) => Math.min(totalPages, p + 1))
                  }
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

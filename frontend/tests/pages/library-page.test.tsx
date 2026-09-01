import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import LibraryPage from "@/app/library/page";
import type { BookSearchResult, BookListResponse } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    getLibraryBooks: vi.fn(),
    getFilterOptions: vi.fn(),
  };
});

import { getLibraryBooks, getFilterOptions } from "@/lib/api";
const mockGetLibraryBooks = vi.mocked(getLibraryBooks);
const mockGetFilterOptions = vi.mocked(getFilterOptions);

const mockBooks: BookSearchResult[] = [
  {
    id: "1",
    title: "Telugu Book One",
    filename: "book1.pdf",
    language: "tel",
    status: "complete",
    total_pages: 100,
    created_at: "2024-01-01",
    metadata_fields: { author: "Author One" },
    thumbnail_url: null,
  },
  {
    id: "2",
    title: "Hindi Book Two",
    filename: "book2.pdf",
    language: "hin",
    status: "complete",
    total_pages: 200,
    created_at: "2024-02-01",
    metadata_fields: { author: "Author Two" },
    thumbnail_url: null,
  },
];

const mockBooksResponse: BookListResponse = {
  items: mockBooks,
  total: 2,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetLibraryBooks.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
    });
    mockGetFilterOptions.mockResolvedValue({
      languages: [],
      statuses: [],
      genres: [],
      publishers: [],
    });
  });

  it("renders Library heading", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Library")).toBeDefined();
  });

  it("renders empty library message", async () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Your library is empty/)).toBeDefined();
    });
  });

  it("renders upload link in empty state", async () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Upload a book/)).toBeDefined();
    });
  });

  it("renders book cards when books exist", async () => {
    mockGetLibraryBooks.mockResolvedValue(mockBooksResponse);
    render(<LibraryPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Telugu Book One")).toBeDefined();
      expect(screen.getByText("Hindi Book Two")).toBeDefined();
    });
  });

  it("renders search input", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(
      screen.getByPlaceholderText("Search by title, author, publisher...")
    ).toBeDefined();
  });

  it("renders language filter dropdown", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("All Languages")).toBeDefined();
  });

  it("renders status filter dropdown", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("All Statuses")).toBeDefined();
  });

  it("renders Upload New Book button", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Upload New Book")).toBeDefined();
  });

  it("renders Search button", () => {
    render(<LibraryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Search")).toBeDefined();
  });

  it("displays total book count", async () => {
    mockGetLibraryBooks.mockResolvedValue(mockBooksResponse);
    render(<LibraryPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/2 books total/)).toBeDefined();
    });
  });
});

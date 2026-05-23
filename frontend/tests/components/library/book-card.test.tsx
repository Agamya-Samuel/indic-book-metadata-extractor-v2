import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import BookCard from "@/components/library/book-card";
import type { BookSearchResult } from "@/lib/api";

const baseBook: BookSearchResult = {
  id: "book-1",
  title: "Test Book Title",
  filename: "test_book.pdf",
  language: "tel",
  status: "complete",
  total_pages: 100,
  created_at: "2024-01-01",
  metadata_fields: {
    author: "Test Author",
    publication_date: "2024",
  },
  thumbnail_url: null,
};

describe("BookCard", () => {
  it("renders book title", () => {
    const { container } = render(<BookCard book={baseBook} />);
    expect(container.textContent).toContain("Test Book Title");
  });

  it("renders author from metadata", () => {
    const { container } = render(<BookCard book={baseBook} />);
    expect(container.textContent).toContain("Test Author");
  });

  it("renders language badge as Telugu", () => {
    const { container } = render(<BookCard book={baseBook} />);
    expect(container.textContent).toContain("Telugu");
  });

  it("renders Hindi language badge", () => {
    const hindiBook = { ...baseBook, language: "hin" };
    const { container } = render(<BookCard book={hindiBook} />);
    expect(container.textContent).toContain("Hindi");
  });

  it("renders publication date", () => {
    const { container } = render(<BookCard book={baseBook} />);
    expect(container.textContent).toContain("2024");
  });

  it("links to book detail page", () => {
    const { container } = render(<BookCard book={baseBook} />);
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/library/book-1");
  });

  it("renders placeholder when no thumbnail", () => {
    const { container } = render(
      <BookCard book={{ ...baseBook, thumbnail_url: null }} />
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeDefined();
  });

  it("uses filename as title when title and metadata title are null", () => {
    const noTitleBook: BookSearchResult = {
      ...baseBook,
      title: null,
      metadata_fields: null,
    };
    const { container } = render(<BookCard book={noTitleBook} />);
    expect(container.textContent).toContain("test_book");
  });

  it("uses metadata title when book title is null", () => {
    const book: BookSearchResult = {
      ...baseBook,
      title: null,
      metadata_fields: { title: "Metadata Title" },
    };
    const { container } = render(<BookCard book={book} />);
    expect(container.textContent).toContain("Metadata Title");
  });

  it("renders without author when not in metadata", () => {
    const noAuthorBook: BookSearchResult = {
      ...baseBook,
      metadata_fields: {},
    };
    const { container } = render(<BookCard book={noAuthorBook} />);
    expect(container.textContent).not.toContain("Test Author");
  });
});

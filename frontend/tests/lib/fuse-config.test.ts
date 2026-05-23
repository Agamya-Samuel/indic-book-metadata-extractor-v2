import { describe, it, expect } from "vitest";
import { createBookFuse, fuseSearch } from "@/lib/fuse-config";
import type { BookSearchResult } from "@/lib/api";

const mockBooks: BookSearchResult[] = [
  {
    id: "1",
    title: "Telugu Sahityam",
    filename: "telugu_sahityam.pdf",
    language: "tel",
    status: "complete",
    total_pages: 200,
    created_at: "2024-01-01",
    metadata_fields: {
      author: "Sri Sri",
      publisher: "Andhra Pradesh Book House",
      genre: "Poetry",
      subject: "Telugu Literature",
    },
    thumbnail_url: null,
  },
  {
    id: "2",
    title: "Hindi Vyakaran",
    filename: "hindi_vyakaran.pdf",
    language: "hin",
    status: "complete",
    total_pages: 150,
    created_at: "2024-02-01",
    metadata_fields: {
      author: "Premchand",
      publisher: "Hindi Granth Academy",
      genre: "Grammar",
      subject: "Hindi Grammar",
    },
    thumbnail_url: null,
  },
  {
    id: "3",
    title: "Bharatiya Itihas",
    filename: "itihas.pdf",
    language: "hin",
    status: "complete",
    total_pages: 300,
    created_at: "2024-03-01",
    metadata_fields: {
      author: "Nehru",
      publisher: "Penguin India",
      genre: "History",
      subject: "Indian History",
    },
    thumbnail_url: null,
  },
];

describe("createBookFuse", () => {
  it("returns a Fuse instance", () => {
    const fuse = createBookFuse(mockBooks);
    expect(fuse).toBeDefined();
  });

  it("searches by title", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "Telugu");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].title).toBe("Telugu Sahityam");
  });

  it("searches by author", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "Premchand");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].metadata_fields?.author).toBe("Premchand");
  });

  it("respects limit parameter", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "a", 1);
    expect(results.length).toBeLessThanOrEqual(1);
  });

  it("returns empty for no match", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "xyznonexistent");
    expect(results).toEqual([]);
  });

  it("returns empty for query shorter than 2 chars", () => {
    const fuse = createBookFuse(mockBooks);
    expect(fuseSearch(fuse, "")).toEqual([]);
    expect(fuseSearch(fuse, "x")).toEqual([]);
  });

  it("returns empty for whitespace-only query", () => {
    const fuse = createBookFuse(mockBooks);
    expect(fuseSearch(fuse, "   ")).toEqual([]);
  });

  it("searches by publisher", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "Penguin");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].metadata_fields?.publisher).toBe("Penguin India");
  });

  it("searches by genre", () => {
    const fuse = createBookFuse(mockBooks);
    const results = fuseSearch(fuse, "Poetry");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].metadata_fields?.genre).toBe("Poetry");
  });
});

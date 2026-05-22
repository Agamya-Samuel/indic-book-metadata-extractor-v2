import Fuse, { type IFuseOptions } from "fuse.js";
import type { BookSearchResult } from "./api";

const FUSE_OPTIONS: IFuseOptions<BookSearchResult> = {
  keys: [
    { name: "title", weight: 0.3 },
    { name: "metadata_fields.author", weight: 0.25 },
    { name: "metadata_fields.publisher", weight: 0.15 },
    { name: "metadata_fields.genre", weight: 0.1 },
    { name: "metadata_fields.subject", weight: 0.1 },
    { name: "filename", weight: 0.1 },
  ],
  threshold: 0.4,
  includeScore: true,
  minMatchCharLength: 2,
};

export const createBookFuse = (
  books: BookSearchResult[]
): Fuse<BookSearchResult> => {
  return new Fuse(books, FUSE_OPTIONS);
};

export const fuseSearch = (
  fuse: Fuse<BookSearchResult>,
  query: string,
  limit: number = 20
): BookSearchResult[] => {
  if (!query || query.trim().length < 2) return [];
  return fuse.search(query.trim(), { limit }).map((r) => r.item);
};

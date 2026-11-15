import type { PageResponse } from "@/lib/api";

/** A page's OCR text, flattened into the shape the reference pane browses. */
export interface OcrCorpusPage {
  id: string;
  pageNumber: number;
  text: string;
  confidence: number | null;
  imageUrl: string | null;
}

export interface TextMatch {
  start: number;
  end: number;
}

export interface CorpusSearchPage {
  pageId: string;
  pageNumber: number;
  matches: TextMatch[];
}

export interface CorpusSearch {
  results: CorpusSearchPage[];
  totalPages: number;
  totalMatches: number;
  truncated: boolean;
}

export interface TextSegment {
  text: string;
  match: boolean;
}

export const SEARCH_PAGE_LIMIT = 50;
export const VALUE_HINT_LIMIT = 5;

/** Flattens a book's pages into the corpus. Pages without OCR keep an empty text. */
export function buildCorpus(pages: PageResponse[]): OcrCorpusPage[] {
  return pages
    .map((page) => ({
      id: page.id,
      pageNumber: page.page_number,
      text: page.ocr_text ?? "",
      confidence: page.ocr_confidence ?? null,
      imageUrl: page.image_url ?? null,
    }))
    .sort((a, b) => a.pageNumber - b.pageNumber);
}

/** Case-insensitive literal matches, with offsets into the original text. */
export function findMatches(text: string, query: string): TextMatch[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];

  const haystack = text.toLowerCase();
  const matches: TextMatch[] = [];
  let from = 0;

  while (from <= haystack.length - needle.length) {
    const start = haystack.indexOf(needle, from);
    if (start === -1) break;
    matches.push({ start, end: start + needle.length });
    from = start + Math.max(1, needle.length);
  }

  return matches;
}

/** Groups matches by page, capped at `pageLimit` pages. */
export function searchCorpus(
  corpus: OcrCorpusPage[],
  query: string,
  pageLimit: number = SEARCH_PAGE_LIMIT,
): CorpusSearch {
  if (!query.trim()) {
    return { results: [], totalPages: 0, totalMatches: 0, truncated: false };
  }

  const results: CorpusSearchPage[] = [];
  let totalPages = 0;
  let totalMatches = 0;

  for (const page of corpus) {
    const matches = findMatches(page.text, query);
    if (matches.length === 0) continue;
    totalPages += 1;
    totalMatches += matches.length;
    if (results.length < pageLimit) {
      results.push({
        pageId: page.id,
        pageNumber: page.pageNumber,
        matches,
      });
    }
  }

  return {
    results,
    totalPages,
    totalMatches,
    truncated: totalPages > results.length,
  };
}

/** Splits text into alternating plain/matched segments for <mark> rendering. */
export function segmentText(text: string, matches: TextMatch[]): TextSegment[] {
  if (!text) return [];

  const ordered = [...matches]
    .filter((match) => match.end > match.start)
    .sort((a, b) => a.start - b.start);

  const segments: TextSegment[] = [];
  let cursor = 0;

  for (const match of ordered) {
    if (match.start < cursor) continue;
    const start = Math.min(match.start, text.length);
    const end = Math.min(match.end, text.length);
    if (end <= cursor) continue;
    if (start > cursor) {
      segments.push({ text: text.slice(cursor, start), match: false });
    }
    segments.push({ text: text.slice(start, end), match: true });
    cursor = end;
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), match: false });
  }

  return segments;
}

/** Pages where a free-text value appears, used only as a browsing hint. */
export function findValueHints(
  corpus: OcrCorpusPage[],
  value: string,
  limit: number = VALUE_HINT_LIMIT,
): number[] {
  const needle = value.trim();
  if (needle.length < 3) return [];

  const pages: number[] = [];
  for (const page of corpus) {
    if (findMatches(page.text, needle).length === 0) continue;
    pages.push(page.pageNumber);
    if (pages.length >= limit) break;
  }
  return pages;
}

/** Clamps a 1-based page number to a book with `pageCount` pages. */
export function clampPageNumber(value: number, pageCount: number): number {
  const max = Math.max(1, Math.trunc(pageCount));
  if (!Number.isFinite(value)) return 1;
  return Math.min(max, Math.max(1, Math.trunc(value)));
}

/** Reads a `?page=` param into a clamped page number, or null when absent. */
export function pageNumberFromParam(
  param: string | null,
  pageCount: number,
): number | null {
  if (!param) return null;
  const parsed = Number.parseInt(param, 10);
  if (Number.isNaN(parsed)) return null;
  return clampPageNumber(parsed, pageCount);
}

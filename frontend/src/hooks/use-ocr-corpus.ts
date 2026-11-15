"use client";

import { useQuery } from "@tanstack/react-query";
import { getAllBookPages } from "@/lib/api";
import { buildCorpus } from "@/lib/ocr-corpus";

const CORPUS_STALE_TIME = 10 * 60 * 1000;
const CORPUS_GC_TIME = 30 * 60 * 1000;

/**
 * Whole-book OCR text for the metadata review reference pane. The corpus is
 * one cached request (`include_ocr=true`) and is only fetched when `enabled`.
 */
export function useOcrCorpus(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["book", bookId, "pages", "ocr-corpus"],
    queryFn: () => getAllBookPages(bookId, { include_ocr: true }),
    enabled: !!bookId && enabled,
    staleTime: CORPUS_STALE_TIME,
    gcTime: CORPUS_GC_TIME,
    select: buildCorpus,
  });
}

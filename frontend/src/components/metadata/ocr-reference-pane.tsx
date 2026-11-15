"use client";

import * as React from "react";
import Image from "next/image";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { getPageImageUrl } from "@/lib/api";
import {
  findMatches,
  findValueHints,
  searchCorpus,
  segmentText,
  type OcrCorpusPage,
} from "@/lib/ocr-corpus";
import { Button, LinkButton } from "@/components/shared/button";
import { Chip } from "@/components/shared/chip";
import { ErrorState, EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/shared/skeleton";
import { getErrorMessage } from "@/lib/error-handler";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { focusRing, focusRingInset } from "@/lib/focus-ring";

export interface PaneEvidence {
  confidence: number | null;
  extraction_method: string;
  source_page_number: number | null;
  source_text_snippet: string | null;
}

interface OcrReferencePaneProps {
  bookId: string;
  pages: OcrCorpusPage[] | undefined;
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  focusedField?: string;
  focusedFieldLabel?: string;
  focusedValue?: string;
  evidence?: PaneEvidence;
  /** Selected page, owned by the page so focus jumps and the sheet stay in sync. */
  pageNumber?: number | null;
  onPageNumberChange?: (pageNumber: number) => void;
  canAppend?: boolean;
  onAppend?: (text: string) => void;
  onCollapse?: () => void;
  onRequestCloseSheet?: () => void;
  className?: string;
}

type PaneTab = "text" | "image";

const TAB_ORDER: PaneTab[] = ["text", "image"];

function confidenceTone(
  confidence: number | null,
): "success" | "warning" | "danger" | "neutral" {
  if (confidence == null) return "neutral";
  if (confidence >= 80) return "success";
  if (confidence >= 60) return "warning";
  return "danger";
}

function confidenceLabel(confidence: number | null): string {
  return confidence == null
    ? "No score"
    : `${Math.round(confidence)}% confidence`;
}

export function OcrReferencePane({
  bookId,
  pages,
  isLoading = false,
  error,
  onRetry,
  focusedField,
  focusedFieldLabel,
  focusedValue,
  evidence,
  pageNumber: selectedPageNumber,
  onPageNumberChange,
  canAppend = false,
  onAppend,
  onCollapse,
  onRequestCloseSheet,
  className,
}: OcrReferencePaneProps) {
  const id = useId();
  const [tab, setTab] = useState<PaneTab>("text");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectionText, setSelectionText] = useState("");
  const textRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentPage = useMemo(() => {
    if (!pages || pages.length === 0) return undefined;
    return (
      pages.find((page) => page.pageNumber === selectedPageNumber) ?? pages[0]
    );
  }, [pages, selectedPageNumber]);

  const currentIndex = currentPage
    ? pages?.findIndex((page) => page.pageNumber === currentPage.pageNumber) ??
      -1
    : -1;
  const pageNumber = currentPage?.pageNumber ?? 1;
  const pageCount = pages?.length ?? 0;
  const currentText = currentPage?.text ?? "";
  const hasAnyText = pages?.some((page) => page.text.trim().length > 0) ?? false;

  const search = useMemo(
    () => searchCorpus(pages ?? [], debouncedQuery),
    [pages, debouncedQuery],
  );
  const currentMatches = useMemo(
    () => findMatches(currentText, debouncedQuery),
    [currentText, debouncedQuery],
  );
  const segments = useMemo(
    () => segmentText(currentText, currentMatches),
    [currentText, currentMatches],
  );
  const valueHints = useMemo(() => {
    if (evidence?.source_page_number != null) return [];
    return findValueHints(pages ?? [], focusedValue ?? "");
  }, [pages, focusedValue, evidence?.source_page_number]);

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    },
    [],
  );

  const goToPage = useCallback(
    (nextPageNumber: number, currentPageCount: number) => {
      const clamped = Math.min(
        Math.max(1, Math.trunc(nextPageNumber)),
        Math.max(1, currentPageCount),
      );
      onPageNumberChange?.(clamped);
      setSelectionText("");
    },
    [onPageNumberChange],
  );

  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => setDebouncedQuery(value), 150);
    },
    [],
  );

  const captureSelection = useCallback(() => {
    const selection = window.getSelection();
    const container = textRef.current;
    if (!selection || !container || selection.isCollapsed) {
      setSelectionText("");
      return;
    }
    const anchor = selection.anchorNode;
    const focus = selection.focusNode;
    if (!anchor || !focus) return;
    if (!container.contains(anchor) || !container.contains(focus)) return;
    setSelectionText(selection.toString());
  }, []);

  const handleCopy = useCallback(async () => {
    const text = selectionText.trim() || currentText;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied OCR text");
    } catch {
      toast.error("Could not copy OCR text");
    }
  }, [selectionText, currentText]);

  const appendable = selectionText.trim();
  const canAppendNow = Boolean(canAppend && appendable);

  const handleAppend = useCallback(() => {
    if (!canAppendNow) return;
    onAppend?.(appendable);
    setSelectionText("");
    onRequestCloseSheet?.();
  }, [canAppendNow, appendable, onAppend, onRequestCloseSheet]);

  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const index = TAB_ORDER.indexOf(tab);
      const next =
        event.key === "ArrowRight"
          ? TAB_ORDER[(index + 1) % TAB_ORDER.length]
          : TAB_ORDER[(index - 1 + TAB_ORDER.length) % TAB_ORDER.length];
      setTab(next);
      document.getElementById(`${id}-${next}-tab`)?.focus();
    },
    [tab, id],
  );

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="space-y-2.5 p-3" aria-label="Loading OCR text">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-9/12" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      );
    }

    if (error) {
      return (
        <ErrorState
          title="Could not load OCR text"
          description={getErrorMessage(error)}
          action={
            onRetry ? (
              <Button variant="outline" size="sm" onClick={onRetry}>
                Try again
              </Button>
            ) : undefined
          }
        />
      );
    }

    if (!pages || pages.length === 0) {
      return (
        <EmptyState
          title="No pages in this book"
          description="Select pages before reviewing metadata."
        />
      );
    }

    if (!hasAnyText) {
      return (
        <EmptyState
          title="No OCR text yet"
          description="Run OCR from the OCR review step to make the book searchable here."
          action={
            <LinkButton
              href={`/books/${bookId}/ocr-review`}
              variant="outline"
              size="sm"
            >
              Go to OCR review
            </LinkButton>
          }
        />
      );
    }

    if (tab === "image") {
      return (
        <div className="p-3">
          {currentPage && (
            <Image
              src={currentPage.imageUrl ?? getPageImageUrl(currentPage.id)}
              alt={`Page ${pageNumber}`}
              width={900}
              height={1200}
              sizes="(min-width: 1024px) 420px, 100vw"
              className="h-auto w-full rounded-[var(--radius)] border border-[var(--border)]"
              unoptimized
            />
          )}
        </div>
      );
    }

    if (!currentPage || !currentText) {
      return (
        <div className="p-3 text-[length:var(--text-sm)] text-[var(--text-muted)]">
          No OCR text was recorded for page {pageNumber}. The page image may
          still show the passage.
        </div>
      );
    }

    return (
      <div
        ref={textRef}
        onMouseUp={captureSelection}
        onKeyUp={captureSelection}
        onTouchEnd={captureSelection}
        className={cn(
          "px-3 py-3 pb-24 text-[length:var(--text-sm)] leading-relaxed text-[var(--text)]",
          "whitespace-pre-wrap break-words",
        )}
        dir="auto"
        data-testid="ocr-pane-text"
      >
        {segments.map((segment, index) =>
          segment.match ? (
            <mark
              key={index}
              className={cn(
                "rounded-[2px] px-0.5",
                "bg-[var(--warning-100)] text-[var(--text)]",
                "border border-[var(--warning-500)] dark:bg-[var(--warning-900)]/40",
              )}
            >
              {segment.text}
            </mark>
          ) : (
            <React.Fragment key={index}>{segment.text}</React.Fragment>
          ),
        )}
      </div>
    );
  };

  return (
    <aside
      aria-label="OCR reference"
      className={cn(
        "flex h-full min-h-0 flex-col overflow-hidden",
        "bg-[var(--surface)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => goToPage(pageNumber - 1, pageCount)}
            disabled={!pages || currentIndex <= 0}
            aria-label="Previous page"
          >
            Prev
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => goToPage(pageNumber + 1, pageCount)}
            disabled={!pages || currentIndex < 0 || currentIndex >= pageCount - 1}
            aria-label="Next page"
          >
            Next
          </Button>
        </div>

        <div className="flex items-center gap-1.5 text-[length:var(--text-sm)] text-[var(--text-muted)]">
          <label htmlFor={`${id}-jump`} className="sr-only">
            Jump to page
          </label>
          <span>Page</span>
          <input
            id={`${id}-jump`}
            key={currentPage?.pageNumber ?? 0}
            type="number"
            min={1}
            max={Math.max(1, pageCount)}
            defaultValue={pageNumber}
            aria-label="Page number"
            className={cn(
              "h-8 w-16 rounded-[var(--radius)] border border-[var(--border)]",
              "bg-[var(--surface)] px-2 text-center text-[length:var(--text-sm)]",
              "text-[var(--text)] tabular-nums",
              "focus:border-[var(--accent-ring)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]/30",
            )}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              const parsed = Number.parseInt(
                (event.target as HTMLInputElement).value,
                10,
              );
              if (!Number.isNaN(parsed)) goToPage(parsed, pageCount);
            }}
            onBlur={(event) => {
              const parsed = Number.parseInt(event.target.value, 10);
              if (!Number.isNaN(parsed)) goToPage(parsed, pageCount);
            }}
          />
          <span>of {pageCount}</span>
        </div>

        {currentPage && (
          <Chip tone={confidenceTone(currentPage.confidence)} dot>
            {confidenceLabel(currentPage.confidence)}
          </Chip>
        )}

        <div className="ml-auto flex items-center gap-1">
          <LinkButton
            href={`/books/${bookId}/ocr-review?page=${pageNumber}`}
            variant="ghost"
            size="sm"
          >
            Open in OCR review
          </LinkButton>
          {onCollapse && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onCollapse}
              aria-label="Collapse OCR reference"
            >
              Collapse
            </Button>
          )}
        </div>
      </div>

      <div
        role="tablist"
        aria-label="OCR reference view"
        className="flex shrink-0 gap-1 border-b border-[var(--border)] px-3 py-1.5"
        onKeyDown={handleTabKeyDown}
      >
        {TAB_ORDER.map((value) => (
          <button
            key={value}
            id={`${id}-${value}-tab`}
            role="tab"
            type="button"
            aria-selected={tab === value}
            aria-controls={`${id}-${value}-panel`}
            tabIndex={tab === value ? 0 : -1}
            onClick={() => setTab(value)}
            className={cn(
              "rounded-[var(--radius)] px-2.5 py-1 text-[length:var(--text-xs)] font-medium",
              "transition-colors duration-[var(--duration-fast)]",
              focusRingInset,
              tab === value
                ? "bg-[var(--surface-sunken)] text-[var(--text)]"
                : "text-[var(--text-muted)] hover:text-[var(--text)]",
            )}
          >
            {value === "text" ? "Text" : "Page image"}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {focusedField && (
          <div className="space-y-2 border-b border-[var(--border)] px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[length:var(--text-xs)] font-semibold text-[var(--text)]">
                {focusedFieldLabel ?? focusedField}
              </span>
              {evidence ? (
                <>
                  <Chip
                    dot
                    tone={
                      evidence.confidence == null
                        ? "neutral"
                        : evidence.confidence >= 0.85
                          ? "success"
                          : evidence.confidence >= 0.5
                            ? "warning"
                            : "danger"
                    }
                  >
                    {evidence.confidence == null
                      ? "no score"
                      : `${Math.round(evidence.confidence * 100)}% confidence`}
                  </Chip>
                  <Chip mono>{evidence.extraction_method}</Chip>
                  {evidence.source_page_number != null && (
                    <Chip>page {evidence.source_page_number}</Chip>
                  )}
                </>
              ) : (
                <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                  No evidence recorded
                </span>
              )}
            </div>

            {evidence?.source_text_snippet && (
              <blockquote className="rounded-[var(--radius)] bg-[var(--surface-sunken)] px-2.5 py-2 text-[length:var(--text-xs)] leading-relaxed text-[var(--text)]">
                …{evidence.source_text_snippet}…
              </blockquote>
            )}

            {evidence?.source_page_number == null && (
              <div className="space-y-1.5">
                <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                  No source page was recorded for this field. Search the OCR
                  text below.
                </p>
                {valueHints.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                      The value may appear on
                    </span>
                    {valueHints.map((hintPage) => (
                      <button
                        key={hintPage}
                        type="button"
                        onClick={() => goToPage(hintPage, pageCount)}
                        className={cn(
                          "rounded-full border border-[var(--border)] px-2 py-0.5",
                          "text-[11px] text-[var(--text-muted)] hover:text-[var(--text)]",
                          focusRing,
                        )}
                      >
                        page {hintPage}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="space-y-2 border-b border-[var(--border)] px-3 py-2.5">
          <label htmlFor={`${id}-search`} className="sr-only">
            Search OCR text
          </label>
          <input
            id={`${id}-search`}
            type="search"
            value={query}
            onChange={(event) => handleQueryChange(event.target.value)}
            placeholder="Search this book’s OCR text"
            className={cn(
              "h-9 w-full rounded-[var(--radius)] border border-[var(--border)]",
              "bg-[var(--surface)] px-2.5 text-[length:var(--text-sm)] text-[var(--text)]",
              "placeholder:text-[var(--text-subtle)]",
              "focus:border-[var(--accent-ring)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]/30",
            )}
          />
          <p
            aria-live="polite"
            className="text-[length:var(--text-xs)] text-[var(--text-muted)]"
          >
            {debouncedQuery
              ? search.totalPages === 0
                ? "No matches"
                : `${search.totalMatches} match${search.totalMatches === 1 ? "" : "es"} on ${search.totalPages} page${search.totalPages === 1 ? "" : "s"}`
              : ""}
          </p>

          {debouncedQuery && search.results.length > 0 && (
            <ul className="max-h-44 space-y-0.5 overflow-y-auto">
              {search.results.map((result) => (
                <li key={result.pageId}>
                  <button
                    type="button"
                    onClick={() => goToPage(result.pageNumber, pageCount)}
                    aria-current={
                      result.pageNumber === pageNumber ? "true" : undefined
                    }
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-[var(--radius)] px-2 py-1 text-left",
                      "text-[length:var(--text-xs)] text-[var(--text-muted)]",
                      "hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]",
                      focusRing,
                      result.pageNumber === pageNumber &&
                        "bg-[var(--surface-sunken)] text-[var(--text)]",
                    )}
                  >
                    <span>page {result.pageNumber}</span>
                    <span className="tabular-nums">
                      {result.matches.length} match
                      {result.matches.length === 1 ? "" : "es"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {search.truncated && (
            <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
              Showing the first {search.results.length} pages.
            </p>
          )}
        </div>

        {TAB_ORDER.map((value) => (
          <div
            key={value}
            role="tabpanel"
            id={`${id}-${value}-panel`}
            aria-labelledby={`${id}-${value}-tab`}
            hidden={tab !== value}
          >
            {tab === value ? renderContent() : null}
          </div>
        ))}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-[var(--border)] px-3 py-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleCopy()}
          disabled={!selectionText && !currentText}
        >
          Copy
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleAppend}
          disabled={!canAppendNow}
          title={
            canAppend
              ? "Select text in the pane to append it"
              : "Focus a metadata field first"
          }
        >
          {focusedFieldLabel ? `Append to ${focusedFieldLabel}` : "Append"}
        </Button>
        <span className="ml-auto text-[length:var(--text-xs)] text-[var(--text-muted)]">
          {selectionText
            ? `${selectionText.trim().length} selected`
            : "Select text to copy or append"}
        </span>
      </div>
    </aside>
  );
}

export default OcrReferencePane;

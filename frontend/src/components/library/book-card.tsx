"use client";

import Link from "next/link";
import Image from "next/image";
import { getThumbnailUrl, type BookSearchResult } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import { cn } from "@/lib/utils";

const LANGUAGE_LABELS: Record<string, string> = {
  tel: "Telugu",
  hin: "Hindi",
};

interface BookCardProps {
  book: BookSearchResult;
}

export default function BookCard({ book }: BookCardProps) {
  const displayTitle =
    book.title ||
    book.metadata_fields?.title ||
    book.metadata_fields?.label ||
    book.filename.replace(/\.pdf$/i, "");
  const author = book.metadata_fields?.author;
  const pubDate = book.metadata_fields?.publication_date;
  const language = LANGUAGE_LABELS[book.language] || book.language;

  return (
    <Link
      href={`/library/${book.id}`}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-[var(--radius-lg)]",
        "border border-[var(--border)] bg-[var(--surface)]",
        "shadow-[var(--shadow-xs)] hover:shadow-[var(--shadow)]",
        "hover:border-[var(--border-strong)]",
        "transition-[box-shadow,transform,border-color] duration-[var(--duration-fast)] ease-[var(--ease-out)]",
        "hover:-translate-y-0.5",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
      )}
    >
      <div className="relative aspect-[3/4] bg-[var(--surface-sunken)]">
        {book.total_pages ? (
          <Image
            src={getThumbnailUrl(book.id, 1)}
            alt={displayTitle}
            fill
            sizes="(min-width: 1024px) 20vw, (min-width: 640px) 25vw, 50vw"
            className="object-cover transition-transform duration-[var(--duration)] ease-[var(--ease-out)] group-hover:scale-[1.02]"
            unoptimized
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-[var(--text-subtle)] paper-grid">
            <svg
              className="size-10"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
              strokeWidth={1.25}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
          </div>
        )}

        <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
          <StatusBadge status={book.status} />
          {book.status === "awaiting_review" && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5",
                "text-[11px] font-medium uppercase tracking-wide",
                "bg-[var(--warning-50)] text-[var(--warning-700)] ring-1 ring-inset ring-[var(--warning-500)]/30",
                "dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]",
              )}
              aria-label="Awaiting review"
            >
              <svg
                aria-hidden="true"
                className="size-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
              Review
            </span>
          )}
        </div>

        {/* Subtle bottom gradient for legibility on light thumbnails */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-black/40 to-transparent"
        />
      </div>

      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h3
          className="text-[var(--text-sm)] font-semibold leading-snug text-[var(--text)] line-clamp-2"
          title={displayTitle}
        >
          {displayTitle}
        </h3>
        {author && (
          <p className="text-[var(--text-xs)] text-[var(--text-muted)] line-clamp-1">
            {author}
          </p>
        )}
        <div className="mt-auto flex items-center gap-1.5 pt-1">
          <span
            className={cn(
              "inline-flex items-center rounded-[var(--radius-xs)] px-1.5 py-0.5",
              "text-[10px] font-medium uppercase tracking-wider",
              "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]",
            )}
          >
            {language}
          </span>
          {pubDate && (
            <span className="font-mono text-[11px] tabular-nums text-[var(--text-subtle)]">
              {pubDate}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

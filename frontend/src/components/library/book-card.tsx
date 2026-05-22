"use client";

import Link from "next/link";
import type { BookSearchResult } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";

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
      className="block bg-white border rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="aspect-[3/4] bg-gray-100 relative">
        {book.thumbnail_url ? (
          <img
            src={book.thumbnail_url}
            alt={displayTitle}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400">
            <svg
              className="w-12 h-12"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
          </div>
        )}
        <div className="absolute top-2 right-2">
          <StatusBadge status={book.status} />
        </div>
      </div>
      <div className="p-3">
        <h3 className="text-sm font-medium text-gray-900 truncate">
          {displayTitle}
        </h3>
        {author && (
          <p className="text-xs text-gray-600 truncate mt-0.5">{author}</p>
        )}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">
            {language}
          </span>
          {pubDate && (
            <span className="text-xs text-gray-500">{pubDate}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

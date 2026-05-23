"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getBookDetail } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { BookDetailSkeleton } from "@/components/shared/skeleton";

const LANGUAGE_LABELS: Record<string, string> = {
  tel: "Telugu",
  hin: "Hindi",
};

const FIELD_DISPLAY_NAMES: Record<string, string> = {
  label: "Label",
  author: "Author",
  title: "Title",
  subtitle: "Subtitle",
  description_work: "Description (Work)",
  description_edition: "Description (Edition)",
  translator: "Translator",
  editor: "Editor",
  compiler: "Compiler",
  inception: "Inception",
  form_of_creative_work: "Form of Creative Work",
  genre: "Genre",
  subject: "Subject",
  original_language: "Original Language",
  edition_or_translation_of: "Edition/Translation Of",
  based_on: "Based On",
  inspired_by: "Inspired By",
  volume: "Volume",
  edition_number: "Edition Number",
  publication_date: "Publication Date",
  publisher: "Publisher",
  publisher_telugu: "Publisher (Telugu)",
  place_of_publication: "Place of Publication",
  printer: "Printer",
  place_of_printing: "Place of Printing",
  language: "Language",
  cover_artist: "Cover Artist",
  cover_page_designer: "Cover Page Designer",
  typesetting_by: "Typesetting",
  typing_by: "Typing",
  book_designer: "Book Designer",
  distributors: "Distributors",
  sponsor: "Sponsor",
  pages: "Pages",
  dedication: "Dedication",
  dedication_verbatim: "Dedication (Verbatim)",
  part_of_series: "Part of Series",
  serial_number_in_series: "Serial # in Series",
  part_of_the_set: "Part of Set",
  illustrators: "Illustrators",
  isbn: "ISBN",
  awards: "Awards",
  context: "Context",
  first_published_in: "First Published In",
  forewords: "Forewords",
  abbreviations: "Abbreviations",
  authors_in_compilation: "Authors in Compilation",
  opinions_messages: "Opinions/Messages",
  scribes: "Scribes",
};

const FIELD_GROUPS: Record<string, string[]> = {
  "Core Identity": [
    "label",
    "title",
    "subtitle",
    "author",
    "description_work",
    "description_edition",
    "language",
    "original_language",
    "isbn",
  ],
  Contributors: [
    "translator",
    "editor",
    "compiler",
    "cover_artist",
    "cover_page_designer",
    "typesetting_by",
    "typing_by",
    "book_designer",
  ],
  Publication: [
    "publication_date",
    "publisher",
    "publisher_telugu",
    "place_of_publication",
    "printer",
    "place_of_printing",
    "distributors",
    "sponsor",
  ],
  "Content Classification": [
    "form_of_creative_work",
    "genre",
    "subject",
    "inception",
    "context",
    "awards",
  ],
  "Edition & Series": [
    "volume",
    "edition_number",
    "edition_or_translation_of",
    "part_of_series",
    "serial_number_in_series",
    "part_of_the_set",
  ],
  Relationships: ["based_on", "inspired_by", "first_published_in"],
  "Ancillary Content": [
    "dedication",
    "dedication_verbatim",
    "forewords",
    "abbreviations",
    "authors_in_compilation",
    "opinions_messages",
    "scribes",
  ],
  Physical: ["pages", "illustrators"],
};

export default function BookDetailPage() {
  const params = useParams();
  const bookId = params.bookId as string;
  const [expandedPage, setExpandedPage] = useState<number | null>(null);

  const { data: detail, isLoading } = useQuery({
    queryKey: ["book-detail", bookId],
    queryFn: () => getBookDetail(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return <BookDetailSkeleton />;
  }

  if (!detail) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600 dark:text-gray-400">Book not found.</p>
      </div>
    );
  }

  const { book, metadata, pages, llm_runs, jobs } = detail;
  const language = LANGUAGE_LABELS[book.language] || book.language;
  const metadataFields = metadata ?? {};
  const nonEmptyFieldCount = Object.values(metadataFields).filter(
    (v) => v != null && v !== ""
  ).length;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {book.title || metadataFields.label || book.filename}
            </h1>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-gray-500 dark:text-gray-400">
              <span>{language}</span>
              <span>&bull;</span>
              <StatusBadge status={book.status} />
              {book.total_pages && (
                <>
                  <span>&bull;</span>
                  <span>{book.total_pages} pages</span>
                </>
              )}
              <span>&bull;</span>
              <span>{nonEmptyFieldCount} metadata fields</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {book.status === "complete" && (
              <a
                href={`/books/${bookId}/metadata-review`}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700 dark:text-gray-300"
              >
                Edit Metadata
              </a>
            )}
            <Link
              href="/library"
              className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700 dark:text-gray-300"
            >
              Back to Library
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
        {Object.keys(metadataFields).length > 0 && (
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 dark:bg-gray-750 dark:border-gray-700">
              <h2 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Metadata ({nonEmptyFieldCount} fields)
              </h2>
            </div>
            <div className="p-4">
              {Object.entries(FIELD_GROUPS).map(([groupName, fieldNames]) => {
                const groupFields = fieldNames.filter(
                  (fn) =>
                    metadataFields[fn] != null &&
                    metadataFields[fn] !== ""
                );
                if (groupFields.length === 0) return null;
                return (
                  <CollapsibleSection
                    key={groupName}
                    title={groupName}
                    count={groupFields.length}
                    defaultOpen={true}
                  >
                    <div className="space-y-2">
                      {groupFields.map((fn) => (
                        <div key={fn} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-sm">
                          <span className="text-gray-500 dark:text-gray-400 sm:min-w-[200px]">
                            {FIELD_DISPLAY_NAMES[fn] || fn}
                          </span>
                          <span className="text-gray-900 dark:text-gray-100">
                            {String(metadataFields[fn])}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                );
              })}
              {metadataFields.custom_fields &&
                typeof metadataFields.custom_fields === "object" &&
                Object.keys(metadataFields.custom_fields).length > 0 && (
                  <CollapsibleSection
                    title="Custom Fields"
                    count={Object.keys(metadataFields.custom_fields).length}
                    defaultOpen={true}
                  >
                    <div className="space-y-2">
                      {Object.entries(metadataFields.custom_fields).map(
                        ([k, v]) => (
                          <div key={k} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-sm">
                            <span className="text-gray-500 dark:text-gray-400 sm:min-w-[200px]">
                              {k}
                            </span>
                            <span className="text-gray-900 dark:text-gray-100">{String(v)}</span>
                          </div>
                        )
                      )}
                    </div>
                  </CollapsibleSection>
                )}
            </div>
          </div>
        )}

        {pages.length > 0 && (
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 dark:border-gray-700">
              <h2 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Pages ({pages.length})
              </h2>
            </div>
            <div className="divide-y dark:divide-gray-700">
              {pages.map((page, idx) => (
                <div key={page.id}>
                  <button
                    onClick={() =>
                      setExpandedPage(expandedPage === idx ? null : idx)
                    }
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 text-left"
                    aria-expanded={expandedPage === idx}
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Page {page.page_number}
                      </span>
                      {page.ocr_confidence != null && (
                        <span
                          className={`text-xs px-1.5 py-0.5 rounded ${
                            page.ocr_confidence >= 80
                              ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                              : page.ocr_confidence >= 60
                                ? "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                                : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                          }`}
                        >
                          {Math.round(page.ocr_confidence)}% confidence
                        </span>
                      )}
                      {page.ocr_text && (
                        <span className="text-xs text-gray-400 dark:text-gray-500 truncate max-w-[200px] sm:max-w-[300px]">
                          {page.ocr_text.substring(0, 80)}...
                        </span>
                      )}
                    </div>
                    <svg
                      className={`w-4 h-4 text-gray-400 dark:text-gray-500 transition-transform ${
                        expandedPage === idx ? "rotate-180" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </button>
                  {expandedPage === idx && (
                    <div className="px-4 pb-4 flex flex-col md:flex-row gap-4">
                      <div className="md:w-1/2">
                        <img
                          src={`/api${page.image_url}`}
                          alt={`Page ${page.page_number}`}
                          className="max-h-[500px] w-auto border rounded dark:border-gray-600"
                          loading="lazy"
                          decoding="async"
                        />
                      </div>
                      <div className="md:w-1/2">
                        <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                          OCR Text
                        </h4>
                        <pre className="text-xs bg-gray-50 dark:bg-gray-700 p-3 rounded overflow-auto max-h-[500px] whitespace-pre-wrap dark:text-gray-300">
                          {page.ocr_text || "(No OCR text available)"}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {jobs.length > 0 && (
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 dark:border-gray-700">
              <h2 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Processing History ({jobs.length})
              </h2>
            </div>
            <div className="divide-y dark:divide-gray-700">
              {jobs.map((job) => (
                <div key={job.id} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {job.job_type === "ocr"
                          ? "OCR"
                          : job.job_type === "llm"
                            ? "LLM Extraction"
                            : job.job_type}
                      </span>
                      <StatusBadge status={job.status} />
                    </div>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {job.created_at
                        ? new Date(job.created_at).toLocaleString()
                        : ""}
                    </span>
                  </div>
                  {job.error_log && (
                    <p className="mt-1 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded">
                      {job.error_log}
                    </p>
                  )}
                  {job.progress != null && job.status === "running" && (
                    <div className="mt-2 w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full"
                        style={{ width: `${Math.round(job.progress)}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {llm_runs.length > 0 && (
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 dark:border-gray-700">
              <h2 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                LLM Run History ({llm_runs.length})
              </h2>
            </div>
            <div className="divide-y dark:divide-gray-700">
              {llm_runs.map((run) => (
                <div key={run.id} className="px-4 py-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {run.model}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {run.created_at
                        ? new Date(run.created_at).toLocaleString()
                        : ""}
                    </span>
                  </div>
                  {run.prompt_template && (
                    <details className="mt-1">
                      <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                        View prompt
                      </summary>
                      <pre className="mt-1 text-xs bg-gray-50 dark:bg-gray-700 p-2 rounded overflow-x-auto whitespace-pre-wrap dark:text-gray-300">
                        {run.prompt_template}
                      </pre>
                    </details>
                  )}
                  {run.parsed_fields && (
                    <details className="mt-1">
                      <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                        View extracted fields (
                        {Object.keys(run.parsed_fields).length})
                      </summary>
                      <div className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-1">
                        {Object.entries(run.parsed_fields).map(([k, v]) => (
                          <div key={k} className="text-xs">
                            <span className="text-gray-500 dark:text-gray-400">{k}:</span>{" "}
                            <span className="text-gray-700 dark:text-gray-300">
                              {v ?? "null"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

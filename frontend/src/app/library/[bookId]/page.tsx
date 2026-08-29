"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getBookDetail } from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { BookDetailSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { LinkButton } from "@/components/shared/button";
import Image from "next/image";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

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

  const bookTitle = detail?.book.title;
  useDocumentTitle(bookTitle ? `${bookTitle} · Library` : "Book");

  if (isLoading) {
    return <BookDetailSkeleton />;
  }

  if (!detail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState title="Book not found" />
      </div>
    );
  }

  const { book, metadata, pages, llm_runs, jobs } = detail;
  const language = LANGUAGE_LABELS[book.language] || book.language;
  const metadataFields = metadata ?? {};
  const nonEmptyFieldCount = Object.values(metadataFields).filter(
    (v) => v != null && v !== ""
  ).length;

  // Derived per-section state — surfaces the relative health of each area
  // at a glance in the card title, so the four cards stop looking identical.
  const ocrDoneCount = pages.filter((p) => p.ocr_text != null).length;
  const lowConfidenceCount = pages.filter(
    (p) => p.ocr_confidence != null && p.ocr_confidence < 60,
  ).length;
  const runningJobs = jobs.filter((j) => j.status === "running").length;
  const failedJobs = jobs.filter((j) => j.status === "failed").length;
  const completedJobs = jobs.filter((j) => j.status === "completed").length;
  const ocrJobsTotal = jobs.filter((j) => j.job_type === "ocr").length;
  // OCR state machine: not-started → in-progress → partial | complete | all-failed
  // The distinction between "not started" and "all failed" matters because
  // a researcher who's never run OCR needs a different call-to-action than
  // a researcher whose OCR attempts have all errored. Without a backend
  // field that records "OCR attempted, no pages succeeded", we infer it
  // from the relationship between OCR jobs and OCR'd pages.
  const ocrState: "not-started" | "in-progress" | "complete" | "all-failed" | "partial" =
    ocrJobsTotal === 0 && ocrDoneCount === 0
      ? "not-started"
      : runningJobs > 0
        ? "in-progress"
        : ocrDoneCount === 0
          ? "all-failed"
          : ocrDoneCount === pages.length
            ? "complete"
            : "partial";
  const latestLlmRun = llm_runs[0]; // runs are returned newest-first by the API

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <PageContainer>
        <PageHeader
          back={
            <LinkButton href="/library" variant="ghost" size="sm">
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
                className="size-3.5"
              >
                <path
                  fillRule="evenodd"
                  d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06-.02z"
                  clipRule="evenodd"
                />
              </svg>
              Library
            </LinkButton>
          }
          eyebrow={language ? `Library · ${language}` : "Library"}
          title={book.title || metadataFields.label || book.filename}
          description={
            <span className="flex flex-wrap items-center gap-2 text-[var(--text-sm)] text-[var(--text-muted)]">
              <StatusBadge status={book.status} />
              {book.total_pages && (
                <>
                  <span aria-hidden="true">&bull;</span>
                  <span>{book.total_pages} pages</span>
                </>
              )}
              <span aria-hidden="true">&bull;</span>
              <span>{nonEmptyFieldCount} metadata fields</span>
            </span>
          }
          actions={
            <div className="flex items-center gap-2">
              {book.status === "complete" && (
                <LinkButton
                  href={`/books/${bookId}/metadata-review`}
                  variant="outline"
                  size="md"
                >
                  Edit Metadata
                </LinkButton>
              )}
              <LinkButton href="/library" variant="outline" size="md">
                Back to Library
              </LinkButton>
            </div>
          }
        />

        <Stack gap={6}>
          {Object.keys(metadataFields).length > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Metadata</span>
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-sunken)] border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium tabular-nums text-[var(--text-muted)]"
                    title={`${nonEmptyFieldCount} fields with values`}
                  >
                    <span
                      aria-hidden="true"
                      className="size-1.5 rounded-full bg-[var(--success-500)]"
                    />
                    {nonEmptyFieldCount} of {Object.keys(metadataFields).length}
                  </span>
                </span>
              }
              description="Fields extracted from the book, grouped by category."
            >
              <Stack gap={3}>
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
                          <div key={fn} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-[var(--text-sm)]">
                            <span className="text-[var(--text-muted)] sm:min-w-[200px]">
                              {FIELD_DISPLAY_NAMES[fn] || fn}
                            </span>
                            <span className="text-[var(--text)]">
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
                            <div key={k} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-[var(--text-sm)]">
                              <span className="text-[var(--text-muted)] sm:min-w-[200px]">
                                {k}
                              </span>
                              <span className="text-[var(--text)]">{String(v)}</span>
                            </div>
                          )
                        )}
                      </div>
                    </CollapsibleSection>
                  )}
              </Stack>
            </Card>
          )}

          {pages.length > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Pages</span>
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-sunken)] border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium tabular-nums text-[var(--text-muted)]"
                    title={
                      ocrState === "not-started"
                        ? "No OCR has been run on this book yet"
                        : ocrState === "all-failed"
                          ? `OCR was attempted but no pages succeeded (${failedJobs} failed job${failedJobs === 1 ? "" : "s"})`
                          : `${ocrDoneCount} of ${pages.length} pages have OCR text`
                    }
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "size-1.5 rounded-full",
                        ocrState === "complete"
                          ? "bg-[var(--success-500)]"
                          : ocrState === "all-failed"
                            ? "bg-[var(--danger-500)]"
                            : ocrState === "not-started"
                              ? "bg-[var(--text-subtle)]"
                              : "bg-[var(--warning-500)]",
                      )}
                    />
                    {ocrState === "not-started" ? (
                      <span>Not started</span>
                    ) : ocrState === "all-failed" ? (
                      <span>All failed</span>
                    ) : (
                      <>
                        {ocrDoneCount} of {pages.length} OCR&apos;d
                        {lowConfidenceCount > 0 && (
                          <span className="ml-0.5 text-[var(--warning-700)] dark:text-[var(--warning-100)]">
                            · {lowConfidenceCount} low conf
                          </span>
                        )}
                      </>
                    )}
                  </span>
                </span>
              }
              description="Click a row to view the page image and OCR text."
            >
              <div className="divide-y divide-[var(--border)] -mx-5">
                {pages.map((page, idx) => (
                  <div key={page.id}>
                    <button
                      onClick={() =>
                        setExpandedPage(expandedPage === idx ? null : idx)
                      }
                      className="w-full px-5 py-3 flex items-center justify-between hover:bg-[var(--surface-sunken)] text-left transition-colors"
                      aria-expanded={expandedPage === idx}
                    >
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                          Page {page.page_number}
                        </span>
                        {page.ocr_confidence != null && (
                          <span
                            className={`text-[11px] px-1.5 py-0.5 rounded-[var(--radius-xs)] font-medium ${
                              page.ocr_confidence >= 80
                                ? "bg-[var(--success-50)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]"
                                : page.ocr_confidence >= 60
                                  ? "bg-[var(--warning-50)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]"
                                  : "bg-[var(--danger-50)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]"
                            }`}
                          >
                            {Math.round(page.ocr_confidence)}% confidence
                          </span>
                        )}
                        {page.ocr_text && (
                          <span className="text-[var(--text-xs)] text-[var(--text-subtle)] truncate max-w-[200px] sm:max-w-[300px]">
                            {page.ocr_text.substring(0, 80)}...
                          </span>
                        )}
                      </div>
                      <svg
                        className={`w-4 h-4 text-[var(--text-muted)] transition-transform ${
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
                      <div className="px-5 pb-4 flex flex-col md:flex-row gap-4">
                        <div className="md:w-1/2">
                          <Image
                            src={`/api${page.image_url}`}
                            alt={`Page ${page.page_number}`}
                            width={800}
                            height={1100}
                            sizes="(min-width: 768px) 50vw, 100vw"
                            className="max-h-[500px] w-auto h-auto border border-[var(--border)] rounded-[var(--radius)]"
                            unoptimized
                          />
                        </div>
                        <div className="md:w-1/2">
                          <h4 className="text-[var(--text-xs)] font-medium text-[var(--text-muted)] mb-2">
                            OCR Text
                          </h4>
                          <pre className="text-[var(--text-xs)] bg-[var(--surface-sunken)] p-3 rounded-[var(--radius)] overflow-auto max-h-[500px] whitespace-pre-wrap text-[var(--text)]">
                            {page.ocr_text || "(No OCR text available)"}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {jobs.length > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Processing history</span>
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-sunken)] border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium tabular-nums text-[var(--text-muted)]"
                    title={`${completedJobs} of ${jobs.length} jobs completed`}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "size-1.5 rounded-full",
                        runningJobs > 0
                          ? "bg-[var(--info-500)]"
                          : failedJobs > 0
                            ? "bg-[var(--danger-500)]"
                            : completedJobs === jobs.length
                              ? "bg-[var(--success-500)]"
                              : "bg-[var(--text-subtle)]",
                      )}
                    />
                    {runningJobs > 0
                      ? `${runningJobs} running`
                      : `${completedJobs} of ${jobs.length} done`}
                    {failedJobs > 0 && (
                      <span className="ml-0.5 text-[var(--danger-700)] dark:text-[var(--danger-100)]">
                        · {failedJobs} failed
                      </span>
                    )}
                  </span>
                </span>
              }
              description="Past and current jobs for this book."
            >
              <div className="divide-y divide-[var(--border)] -mx-5">
                {jobs.map((job) => (
                  <div key={job.id} className="px-5 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                          {job.job_type === "ocr"
                            ? "OCR"
                            : job.job_type === "llm"
                              ? "LLM Extraction"
                              : job.job_type}
                        </span>
                        <StatusBadge status={job.status} />
                      </div>
                      <span className="text-[var(--text-xs)] text-[var(--text-subtle)]">
                        {job.created_at
                          ? new Date(job.created_at).toLocaleString()
                          : ""}
                      </span>
                    </div>
                    {job.error_log && (
                      <ErrorState
                        className="mt-2"
                        title="Job error"
                        description={job.error_log}
                      />
                    )}
                    {job.progress != null && job.status === "running" && (
                      <div className="mt-2">
                        <Progress value={job.progress} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {llm_runs.length > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>LLM run history</span>
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--surface-sunken)] border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium tabular-nums text-[var(--text-muted)]"
                    title={`${llm_runs.length} extraction runs on file`}
                  >
                    <span
                      aria-hidden="true"
                      className="size-1.5 rounded-full bg-[var(--accent)]"
                    />
                    {llm_runs.length} {llm_runs.length === 1 ? "run" : "runs"}
                    {latestLlmRun?.model && (
                      <span className="ml-0.5 text-[var(--text-subtle)]">
                        · {latestLlmRun.model}
                      </span>
                    )}
                  </span>
                </span>
              }
              description="Past LLM extraction runs and their results."
            >
              <div className="divide-y divide-[var(--border)] -mx-5">
                {llm_runs.map((run) => (
                  <div key={run.id} className="px-5 py-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[var(--text-sm)] font-medium text-[var(--text)]">
                        {run.model}
                      </span>
                      <span className="text-[var(--text-xs)] text-[var(--text-subtle)]">
                        {run.created_at
                          ? new Date(run.created_at).toLocaleString()
                          : ""}
                      </span>
                    </div>
                    {run.prompt_template && (
                      <details className="mt-1">
                        <summary className="text-[var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                          View prompt
                        </summary>
                        <pre className="mt-1 text-[var(--text-xs)] bg-[var(--surface-sunken)] p-2 rounded-[var(--radius)] overflow-x-auto whitespace-pre-wrap text-[var(--text)]">
                          {run.prompt_template}
                        </pre>
                      </details>
                    )}
                    {run.parsed_fields && (
                      <details className="mt-1">
                        <summary className="text-[var(--text-xs)] text-[var(--text-muted)] cursor-pointer hover:text-[var(--text)]">
                          View extracted fields (
                          {Object.keys(run.parsed_fields).length})
                        </summary>
                        <div className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-1">
                          {Object.entries(run.parsed_fields).map(([k, v]) => (
                            <div key={k} className="text-[var(--text-xs)]">
                              <span className="text-[var(--text-muted)]">{k}:</span>{" "}
                              <span className="text-[var(--text)]">
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
            </Card>
          )}
        </Stack>
      </PageContainer>
    </div>
  );
}

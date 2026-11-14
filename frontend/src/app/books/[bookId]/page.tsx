"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getBookDetail,
  getPageImageUrl,
  getBookCurrentStages,
  getBookPages,
  getBookJobs,
  getAllBookJobs,
  getLlmRuns,
  getOcrStatus,
  type PageResponse,
  type JobResponse,
  type LlmRunResponse,
} from "@/lib/api";
import StatusBadge from "@/components/shared/status-badge";
import { Chip } from "@/components/shared/chip";
import CollapsibleSection from "@/components/shared/collapsible-section";
import { BookDetailSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card, Stack } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import Image from "next/image";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import WorkflowResumeBanner from "@/components/book/workflow-resume-banner";
import WorkflowShell from "@/components/shared/workflow-shell";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import Pagination from "@/components/shared/pagination";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";

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
  const [expandedPageId, setExpandedPageId] = useState<string | null>(null);
  const [pagesPage, setPagesPage] = useState(1);
  const [pagesPageSize, setPagesPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [jobsPage, setJobsPage] = useState(1);
  const [runsPage, setRunsPage] = useState(1);

  const { data: detail, isLoading } = useQuery({
    queryKey: ["book-detail", bookId],
    queryFn: () => getBookDetail(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const { data: stages } = useQuery({
    queryKey: ["book", bookId, "stages", "current"],
    queryFn: () => getBookCurrentStages(bookId),
    enabled: !!bookId,
    staleTime: 5 * 1000,
  });

  const { data: pagesData, isLoading: pagesLoading } = useQuery({
    queryKey: ["book", bookId, "pages", pagesPage, pagesPageSize],
    queryFn: () =>
      getBookPages(bookId, {
        page: pagesPage,
        page_size: pagesPageSize,
        include_ocr: true,
      }),
    enabled: !!bookId,
    staleTime: 30 * 1000,
  });

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["book", bookId, "jobs", jobsPage],
    queryFn: () =>
      getBookJobs(bookId, { page: jobsPage, page_size: DEFAULT_PAGE_SIZE }),
    enabled: !!bookId,
    staleTime: 10 * 1000,
  });

  const { data: allJobs } = useQuery({
    queryKey: ["book", bookId, "jobs", "all"],
    queryFn: () => getAllBookJobs(bookId),
    enabled: !!bookId,
    staleTime: 10 * 1000,
  });

  const { data: ocrStatus } = useQuery({
    queryKey: ["book", bookId, "ocr-status"],
    queryFn: () => getOcrStatus(bookId),
    enabled: !!bookId,
    staleTime: 15 * 1000,
  });

  const { data: llmRunsData, isLoading: runsLoading } = useQuery({
    queryKey: ["book", bookId, "llm-runs", runsPage],
    queryFn: () =>
      getLlmRuns(bookId, { page: runsPage, page_size: DEFAULT_PAGE_SIZE }),
    enabled: !!bookId,
    staleTime: 30 * 1000,
  });

  const bookTitle = detail?.book.title;
  useDocumentTitle(bookTitle ? `${bookTitle} · Books` : "Book");

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

  const { book, metadata } = detail;
  const pages = pagesData?.items ?? [];
  const jobs = jobsData?.items ?? [];
  const llm_runs = llmRunsData?.items ?? [];
  const statsJobs = allJobs ?? jobs;
  const totalPageCount =
    ocrStatus?.total_pages ?? pagesData?.total ?? book.total_pages ?? 0;
  // Only the owner or an admin ever receives this payload; non-owners get 404.
  const language = LANGUAGE_LABELS[book.language] || book.language;
  const metadataFields = metadata ?? {};
  const nonEmptyFieldCount = Object.values(metadataFields).filter(
    (v) => v != null && v !== ""
  ).length;

  // Derived per-section state — surfaces the relative health of each area
  // at a glance in the card title, so the four cards stop looking identical.
  // Counts come from the OCR status aggregate and the full job list; the
  // tables themselves render only the current page.
  const ocrDoneCount = ocrStatus?.ocr_complete_count ?? 0;
  const lowConfidenceCount =
    ocrStatus?.pages.filter(
      (p) => p.confidence != null && p.confidence < 60,
    ).length ?? 0;
  const runningJobs = statsJobs.filter((j) => j.status === "running").length;
  const failedJobs = statsJobs.filter((j) => j.status === "failed").length;
  const completedJobs = statsJobs.filter((j) => j.status === "completed").length;
  const ocrJobsTotal = statsJobs.filter((j) => j.job_type === "ocr").length;
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
          : ocrDoneCount === totalPageCount
            ? "complete"
            : "partial";
  const latestLlmRun = llm_runs[0]; // runs are returned newest-first by the API

  const jobColumns: DataTableColumn<JobResponse>[] = [
    {
      key: "job",
      header: "Job",
      cell: (job) => (
        <div className="min-w-0">
          <span className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
            {job.job_type === "ocr"
              ? "OCR"
              : job.job_type === "llm"
                ? "LLM Extraction"
                : job.job_type}
          </span>
          {job.error_log && (
            <p className="mt-1 text-[length:var(--text-xs)] text-[var(--danger-700)] dark:text-[var(--danger-100)]">
              {job.error_log}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (job) => <StatusBadge status={job.status} />,
    },
    {
      key: "progress",
      header: "Progress",
      hideBelow: "sm",
      cell: (job) =>
        job.progress != null && job.status === "running" ? (
          <div className="w-32">
            <Progress value={job.progress} showValue />
          </div>
        ) : (
          <span className="text-[length:var(--text-xs)] text-[var(--text-subtle)]">
            &#8212;
          </span>
        ),
    },
    {
      key: "created",
      header: "Created",
      hideBelow: "md",
      cell: (job) => (
        <span className="whitespace-nowrap text-[length:var(--text-xs)] text-[var(--text-subtle)]">
          {job.created_at ? new Date(job.created_at).toLocaleString() : "—"}
        </span>
      ),
    },
  ];

  const pageColumns: DataTableColumn<PageResponse>[] = [
    {
      key: "page",
      header: "Page",
      cell: (page) => (
        <span className="whitespace-nowrap text-[length:var(--text-sm)] font-medium text-[var(--text)]">
          Page {page.page_number}
        </span>
      ),
    },
    {
      key: "confidence",
      header: "Confidence",
      hideBelow: "sm",
      cell: (page) =>
        page.ocr_confidence != null ? (
          <Chip
            tone={
              page.ocr_confidence >= 80
                ? "success"
                : page.ocr_confidence >= 60
                  ? "warning"
                  : "danger"
            }
          >
            {Math.round(page.ocr_confidence)}%
          </Chip>
        ) : (
          <span className="text-[length:var(--text-xs)] text-[var(--text-subtle)]">
            —
          </span>
        ),
    },
    {
      key: "text",
      header: "OCR text",
      hideBelow: "md",
      cell: (page) => (
        <span className="block max-w-[420px] truncate text-[length:var(--text-xs)] text-[var(--text-subtle)]">
          {page.ocr_text ? `${page.ocr_text.substring(0, 80)}…` : "—"}
        </span>
      ),
    },
    {
      key: "toggle",
      header: <span className="sr-only">Details</span>,
      className: "text-right",
      cell: (page) => (
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={expandedPageId === page.id}
          onClick={() =>
            setExpandedPageId((prev) => (prev === page.id ? null : page.id))
          }
        >
          {expandedPageId === page.id ? "Hide" : "Show"}
        </Button>
      ),
    },
  ];

  const runColumns: DataTableColumn<LlmRunResponse>[] = [
    {
      key: "model",
      header: "Model",
      cell: (run) => (
        <span className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
          {run.model}
        </span>
      ),
    },
    {
      key: "created",
      header: "Created",
      hideBelow: "sm",
      cell: (run) => (
        <span className="whitespace-nowrap text-[length:var(--text-xs)] text-[var(--text-subtle)]">
          {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
        </span>
      ),
    },
    {
      key: "details",
      header: "Details",
      cell: (run) => (
        <div className="space-y-1">
          {run.prompt_template && (
            <details>
              <summary className="cursor-pointer text-[length:var(--text-xs)] text-[var(--text-muted)] hover:text-[var(--text)]">
                View prompt
              </summary>
              <pre className="mt-1 whitespace-pre-wrap rounded-[var(--radius)] bg-[var(--surface-sunken)] p-2 text-[length:var(--text-xs)] text-[var(--text)]">
                {run.prompt_template}
              </pre>
            </details>
          )}
          {run.parsed_fields && (
            <details>
              <summary className="cursor-pointer text-[length:var(--text-xs)] text-[var(--text-muted)] hover:text-[var(--text)]">
                View extracted fields ({Object.keys(run.parsed_fields).length})
              </summary>
              <div className="mt-1 grid grid-cols-1 gap-1 sm:grid-cols-2">
                {Object.entries(run.parsed_fields).map(([k, v]) => (
                  <div key={k} className="text-[length:var(--text-xs)]">
                    <span className="text-[var(--text-muted)]">{k}:</span>{" "}
                    <span className="text-[var(--text)]">{v ?? "null"}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      ),
    },
  ];

  return (
    <WorkflowShell bookId={bookId}>
      <PageContainer>
        <PageHeader
          back={
            <LinkButton href="/dashboard" variant="ghost" size="sm">
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
              Dashboard
            </LinkButton>
          }
          eyebrow={language ? `Books · ${language}` : "Books"}
          title={book.title || metadataFields.label || book.filename}
          description={
            <span className="flex flex-wrap items-center gap-2 text-[length:var(--text-sm)] text-[var(--text-muted)]">
              <StatusBadge status={book.status} stageStatus={stages?.items[0]?.status as "initiated" | "processing" | "completed" | "failed" | "cancelled" | undefined} />
              {book.total_pages && (
                <>
                  <span aria-hidden="true">&bull;</span>
                  <span>{book.total_pages} pages</span>
                </>
              )}
              <span aria-hidden="true">&bull;</span>
              <span>{nonEmptyFieldCount} metadata fields</span>
              {detail.owner_display_name && (
                <>
                  <span aria-hidden="true">&bull;</span>
                  <span>Uploaded by {detail.owner_display_name}</span>
                </>
              )}
            </span>
          }
          actions={
            <div className="flex items-center gap-2">
              {book.status === "awaiting_review" && (
                <LinkButton
                  href={`/books/${bookId}/metadata-review`}
                  variant="primary"
                  size="md"
                >
                  Review now
                </LinkButton>
              )}
              {book.status === "complete" && (
                <LinkButton
                  href={`/books/${bookId}/metadata-review`}
                  variant="outline"
                  size="md"
                >
                  Edit Metadata
                </LinkButton>
              )}
            </div>
          }
        />

        <WorkflowResumeBanner detail={detail.book} />

        {book.status === "awaiting_review" && (
          <Card>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-4">
              <div
                aria-hidden="true"
                className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--warning-50)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]"
              >
                <svg
                  className="size-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  strokeWidth={1.75}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                  />
                </svg>
              </div>
              <div className="flex-1 space-y-2">
                <h2 className="text-[length:var(--text-base)] font-semibold text-[var(--text)]">
                  Review needed
                </h2>
                <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                  {book.low_confidence_count && book.low_confidence_count > 0
                    ? `${book.low_confidence_count} metadata field${book.low_confidence_count === 1 ? "" : "s"} below the confidence threshold. Open the metadata review to inspect and correct them.`
                    : "The auto-chain has finished. Open the metadata review to confirm the extracted values before exporting."}
                </p>
                <div>
                  <LinkButton
                    href={`/books/${bookId}/metadata-review`}
                    variant="primary"
                    size="sm"
                  >
                    Open metadata review
                  </LinkButton>
                </div>
              </div>
            </div>
          </Card>
        )}

        <Stack gap={6}>
          {Object.keys(metadataFields).length > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Metadata</span>
                  <Chip
                    dot
                    tone="success"
                    title={`${nonEmptyFieldCount} fields with values`}
                  >
                    {nonEmptyFieldCount} of {Object.keys(metadataFields).length}
                  </Chip>
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
                          <div key={fn} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-[length:var(--text-sm)]">
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
                            <div key={k} className="flex flex-col sm:flex-row gap-1 sm:gap-3 text-[length:var(--text-sm)]">
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

          {totalPageCount > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Pages</span>
                  <Chip
                    dot
                    tone={
                      ocrState === "complete"
                        ? "success"
                        : ocrState === "all-failed"
                          ? "danger"
                          : ocrState === "not-started"
                            ? "neutral"
                            : "warning"
                    }
                    title={
                      ocrState === "not-started"
                        ? "No OCR has been run on this book yet"
                        : ocrState === "all-failed"
                          ? `OCR was attempted but no pages succeeded (${failedJobs} failed job${failedJobs === 1 ? "" : "s"})`
                          : `${ocrDoneCount} of ${totalPageCount} pages have OCR text`
                    }
                  >
                    {ocrState === "not-started" ? (
                      <span>Not started</span>
                    ) : ocrState === "all-failed" ? (
                      <span>All failed</span>
                    ) : (
                      <>
                        {ocrDoneCount} of {totalPageCount} OCR&apos;d
                        {lowConfidenceCount > 0 && (
                          <span className="ml-0.5 font-medium">
                            · {lowConfidenceCount} low conf
                          </span>
                        )}
                      </>
                    )}
                  </Chip>
                </span>
              }
              description="Expand a row to see the page image and its OCR text."
              flush
            >
              <DataTable
                bare
                caption="Pages"
                columns={pageColumns}
                rows={pages}
                loading={pagesLoading}
                rowKey={(page) => page.id}
                expandedRowKey={expandedPageId}
                renderExpandedRow={(page) => (
                  <div className="flex flex-col gap-4 md:flex-row">
                    <div className="md:w-1/2">
                      <Image
                        src={page.image_url ?? getPageImageUrl(page.id)}
                        alt={`Page ${page.page_number}`}
                        width={800}
                        height={1100}
                        sizes="(min-width: 768px) 50vw, 100vw"
                        className="h-auto max-h-[500px] w-auto rounded-[var(--radius)] border border-[var(--border)]"
                        unoptimized
                      />
                    </div>
                    <div className="md:w-1/2">
                      <h4 className="mb-2 text-[length:var(--text-xs)] font-medium text-[var(--text-muted)]">
                        OCR Text
                      </h4>
                      <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap rounded-[var(--radius)] bg-[var(--surface-sunken)] p-3 text-[length:var(--text-xs)] text-[var(--text)]">
                        {page.ocr_text || "(No OCR text available)"}
                      </pre>
                    </div>
                  </div>
                )}
              />
              <Pagination
                page={pagesPage}
                totalPages={pagesData?.total_pages ?? 0}
                onPageChange={setPagesPage}
                pageSize={pagesPageSize}
                onPageSizeChange={(size) => {
                  setPagesPageSize(size);
                  setPagesPage(1);
                }}
                disabled={pagesLoading}
              />
            </Card>
          )}

          {(jobsData?.total ?? 0) > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>Processing history</span>
                  <Chip
                    dot
                    tone={
                      runningJobs > 0
                        ? "info"
                        : failedJobs > 0
                          ? "danger"
                          : completedJobs === statsJobs.length
                            ? "success"
                            : "neutral"
                    }
                    title={`${completedJobs} of ${statsJobs.length} jobs completed`}
                  >
                    {runningJobs > 0
                      ? `${runningJobs} running`
                      : `${completedJobs} of ${statsJobs.length} done`}
                    {failedJobs > 0 && (
                      <span className="ml-0.5 font-medium">
                        · {failedJobs} failed
                      </span>
                    )}
                  </Chip>
                </span>
              }
              description="Past and current jobs for this book."
              flush
            >
              <DataTable
                bare
                caption="Processing history"
                columns={jobColumns}
                rows={jobs}
                loading={jobsLoading}
                rowKey={(job) => job.id}
              />
              <Pagination
                page={jobsPage}
                totalPages={jobsData?.total_pages ?? 0}
                onPageChange={setJobsPage}
                disabled={jobsLoading}
              />
            </Card>
          )}

          {(llmRunsData?.total ?? 0) > 0 && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <span>LLM run history</span>
                  <Chip
                    dot
                    tone="accent"
                    title={`${llmRunsData?.total ?? 0} extraction runs on file`}
                  >
                    {llmRunsData?.total ?? 0}{" "}
                    {(llmRunsData?.total ?? 0) === 1 ? "run" : "runs"}
                    {latestLlmRun?.model && (
                      <span className="ml-0.5 opacity-80">
                        · {latestLlmRun.model}
                      </span>
                    )}
                  </Chip>
                </span>
              }
              description="Past LLM extraction runs and their results."
              flush
            >
              <DataTable
                bare
                caption="LLM run history"
                columns={runColumns}
                rows={llm_runs}
                loading={runsLoading}
                rowKey={(run) => run.id}
              />
              <Pagination
                page={runsPage}
                totalPages={llmRunsData?.total_pages ?? 0}
                onPageChange={setRunsPage}
                disabled={runsLoading}
              />
            </Card>
          )}
        </Stack>
      </PageContainer>
    </WorkflowShell>
  );
}

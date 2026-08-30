import type { BookDetail } from "./api";
import type { AdminJobRow } from "./api";

export type ResumeVariant = "info" | "success" | "warning" | "danger";

export interface ResumeFailureContext {
  jobId: string;
  jobType: "ocr" | "llm" | "preprocessing";
  error: string;
}

export interface ResumeTarget {
  ctaLabel: string;
  href: string;
  headline: string;
  description: string;
  variant: ResumeVariant;
  showProgress: boolean;
  failureContext?: ResumeFailureContext;
}

/**
 * Pick the most recent failed job for this book, regardless of job type.
 * Used to surface a "your last step failed" banner with a re-run action.
 */
function findLatestFailedJob(jobs: AdminJobRow[]): AdminJobRow | null {
  for (const j of jobs) {
    if (j.status === "failed") return j;
  }
  return null;
}

/**
 * Returns the destination and banner content for resuming a book that is
 * mid-workflow or has a failed job. Pure: takes data, returns a target.
 * Returns `null` for books in `complete` state with no failed jobs.
 */
export function getResumeTarget(
  book: Pick<BookDetail, "id" | "status">,
  jobs: AdminJobRow[] = [],
): ResumeTarget | null {
  const bookId = book.id;

  // Most recent failed job takes priority — it means the user came back to
  // a book whose last attempt errored out.
  const failed = findLatestFailedJob(jobs);
  if (failed) {
    const errorExcerpt = (failed.error_log ?? "Unknown error").split("\n")[0];
    if (failed.job_type === "ocr") {
      return {
        ctaLabel: "Re-run OCR",
        href: `/books/${bookId}/ocr-processing`,
        headline: "OCR failed",
        description: errorExcerpt,
        variant: "danger",
        showProgress: false,
        failureContext: {
          jobId: failed.id,
          jobType: "ocr",
          error: errorExcerpt,
        },
      };
    }
    if (failed.job_type === "llm") {
      return {
        ctaLabel: "Re-run extraction",
        href: `/books/${bookId}/llm-config`,
        headline: "LLM extraction failed",
        description: errorExcerpt,
        variant: "danger",
        showProgress: false,
        failureContext: {
          jobId: failed.id,
          jobType: "llm",
          error: errorExcerpt,
        },
      };
    }
    // preprocessing → re-running OCR also re-runs preprocessing
    return {
      ctaLabel: "Re-run preprocessing",
      href: `/books/${bookId}/preprocessing`,
      headline: "Preprocessing failed",
      description: errorExcerpt,
      variant: "danger",
      showProgress: false,
      failureContext: {
        jobId: failed.id,
        jobType: "preprocessing",
        error: errorExcerpt,
      },
    };
  }

  switch (book.status) {
    case "uploaded":
      return {
        ctaLabel: "Select pages",
        href: `/books/${bookId}/select-pages`,
        headline: "Ready to begin",
        description:
          "This book has been uploaded but no pages have been selected yet.",
        variant: "info",
        showProgress: false,
      };
    case "pages_selected":
      return {
        ctaLabel: "Configure preprocessing",
        href: `/books/${bookId}/preprocessing`,
        headline: "Pages selected",
        description:
          "Review preprocessing settings, then start OCR to read the scanned pages.",
        variant: "info",
        showProgress: false,
      };
    case "ocr_running":
      return {
        ctaLabel: "View progress",
        href: `/books/${bookId}/ocr-processing`,
        headline: "OCR in progress",
        description:
          "Tesseract is reading the scanned pages. You can wait here or jump to the live view — the job continues in the background.",
        variant: "info",
        showProgress: true,
      };
    case "ocr_complete":
      return {
        ctaLabel: "Review OCR",
        href: `/books/${bookId}/ocr-review`,
        headline: "OCR finished",
        description:
          "All pages have been read. Correct any errors in the OCR text before starting extraction.",
        variant: "success",
        showProgress: false,
      };
    case "llm_running":
      return {
        ctaLabel: "View progress",
        href: `/books/${bookId}/llm-config`,
        headline: "LLM extraction in progress",
        description:
          "The language model is extracting bibliographic metadata from the OCR text. You can wait here — the job runs in the background.",
        variant: "info",
        showProgress: true,
      };
    case "complete":
    default:
      return null;
  }
}
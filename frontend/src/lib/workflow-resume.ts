import type { BookDetail, BookStageResponse } from "./api";

export type ResumeVariant = "info" | "success" | "warning" | "danger";

export interface ResumeFailureContext {
  stage: string;
  attempt: number;
  error: string;
}

export interface ResumeTarget {
  ctaLabel: string;
  href: string | ((bookId: string) => string);
  headline: string;
  description: string;
  variant: ResumeVariant;
  showProgress: boolean;
  failureContext?: ResumeFailureContext;
}

const STAGE_CTA: Record<string, { ctaLabel: string; href: string | ((bookId: string) => string); headline: string; description: string; variant: ResumeVariant; showProgress: boolean }> = {
  upload: {
    ctaLabel: "Select pages",
    href: (bookId: string) => `/books/${bookId}/select-pages`,
    headline: "Ready to begin",
    description: "This book has been uploaded but no pages have been selected yet.",
    variant: "info",
    showProgress: false,
  },
  page_selection: {
    ctaLabel: "Configure preprocessing",
    href: (bookId: string) => `/books/${bookId}/preprocessing`,
    headline: "Pages selected",
    description: "Review preprocessing settings, then start OCR to read the scanned pages.",
    variant: "info",
    showProgress: false,
  },
  ocr: {
    ctaLabel: "View progress",
    href: (bookId: string) => `/books/${bookId}/ocr-processing`,
    headline: "OCR in progress",
    description: "Tesseract is reading the scanned pages. You can wait here or jump to the live view — the job continues in the background.",
    variant: "info",
    showProgress: true,
  },
  llm_extraction: {
    ctaLabel: "View progress",
    href: (bookId: string) => `/books/${bookId}/llm-config`,
    headline: "LLM extraction in progress",
    description: "The language model is extracting bibliographic metadata from the OCR text. You can wait here — the job runs in the background.",
    variant: "info",
    showProgress: true,
  },
  human_review: {
    ctaLabel: "Review metadata",
    href: (bookId: string) => `/books/${bookId}/metadata-review`,
    headline: "Review metadata",
    description: "Review and correct the extracted metadata before finalizing.",
    variant: "info",
    showProgress: false,
  },
  completion: {
    ctaLabel: "View library",
    href: () => `/library`,
    headline: "Complete",
    description: "This book has been fully processed.",
    variant: "success",
    showProgress: false,
  },
};

function findFailedStage(stages: BookStageResponse[] = []): BookStageResponse | null {
  for (const s of stages) {
    if (s.status === "failed" || s.status === "cancelled") {
      return s;
    }
  }
  return null;
}

export function getResumeTarget(
  book: Pick<BookDetail, "id" | "status">,
  stages: BookStageResponse[] = [],
): ResumeTarget | null {
  const bookId = book.id;

  const failed = findFailedStage(stages);
  if (failed) {
    const errorExcerpt = (failed.error_log ?? "Unknown error").split("\n")[0];
    const ctaMap: Record<string, { ctaLabel: string; href: string; headline: string }> = {
      ocr: { ctaLabel: "Re-run OCR", href: `/books/${bookId}/ocr-processing`, headline: "OCR failed" },
      llm_extraction: { ctaLabel: "Re-run extraction", href: `/books/${bookId}/llm-config`, headline: "LLM extraction failed" },
      preprocessing: { ctaLabel: "Re-run preprocessing", href: `/books/${bookId}/preprocessing`, headline: "Preprocessing failed" },
      page_selection: { ctaLabel: "Select pages", href: `/books/${bookId}/select-pages`, headline: "Page selection failed" },
    };
    const mapped = ctaMap[failed.stage_name] || { ctaLabel: "Retry", href: `/books/${bookId}`, headline: "Stage failed" };
    return {
      ctaLabel: mapped.ctaLabel,
      href: mapped.href,
      headline: mapped.headline,
      description: errorExcerpt,
      variant: "danger",
      showProgress: false,
      failureContext: {
        stage: failed.stage_name,
        attempt: failed.attempt,
        error: errorExcerpt,
      },
    };
  }

  const currentStage = stages.find((s) => s.status === "processing" || s.status === "initiated");
  if (!currentStage) {
    if (book.status === "complete") return null;
    return {
      ctaLabel: "Select pages",
      href: `/books/${bookId}/select-pages`,
      headline: "Ready to begin",
      description: "This book has been uploaded but no pages have been selected yet.",
      variant: "info",
      showProgress: false,
    };
  }

  const cta = STAGE_CTA[currentStage.stage_name];
  if (!cta) return null;

  return {
    ctaLabel: cta.ctaLabel,
    href: typeof cta.href === "function" ? cta.href(bookId) : cta.href,
    headline: cta.headline,
    description: cta.description,
    variant: cta.variant,
    showProgress: cta.showProgress,
  };
}

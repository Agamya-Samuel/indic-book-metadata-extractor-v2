import type {
  BookDetail,
  BookStageResponse,
  JobResponse,
  PageResponse,
} from "./api";

/**
 * Single source of truth for the seven-stage book workflow.
 *
 * The backend tracks six stages (`upload`, `page_selection`, `ocr`,
 * `llm_extraction`, `human_review`, `completion`); preprocessing is not a
 * backend stage — it is a sub-state derived from each page's
 * `preprocessing_config`. This module folds that into one honest model so the
 * stepper, page guards and resume banner can never disagree with the server.
 */

export type StepKey =
  | "upload"
  | "pages"
  | "preprocessing"
  | "ocr"
  | "ocr_review"
  | "llm"
  | "review";

export type StepState =
  | "not_started"
  | "current"
  | "complete"
  | "failed"
  | "stale";

export type ProcessingKind = "page_extraction" | "ocr" | "llm";

export interface WorkflowStep {
  key: StepKey;
  label: string;
  shortLabel: string;
  /** Route to open for this step. Upload is absolute; book steps are scoped. */
  href: string;
  state: StepState;
  /** Short running/blocked hint shown next to the label. */
  detail?: string;
}

export interface WorkflowProcessing {
  kind: ProcessingKind;
  job: JobResponse | null;
  /** 0–100, the backend's native job progress scale. */
  progress: number;
}

export interface WorkflowStateInput {
  book:
    | (Pick<BookDetail, "id" | "status"> & { needs_review?: boolean })
    | null
    | undefined;
  stages?: BookStageResponse[] | null;
  pages?: PageResponse[] | null;
  jobs?: JobResponse[] | null;
}

export interface WorkflowState {
  /** Steps in workflow order. */
  steps: WorkflowStep[];
  byKey: Record<StepKey, WorkflowStep>;
  /** First step that is not complete; `review` once everything is done. */
  currentStep: StepKey;
  processing: WorkflowProcessing | null;
}

export const STEP_ORDER: StepKey[] = [
  "upload",
  "pages",
  "preprocessing",
  "ocr",
  "ocr_review",
  "llm",
  "review",
];

interface StepMeta {
  label: string;
  shortLabel: string;
  path: string | ((bookId: string) => string);
}

const STEP_META: Record<StepKey, StepMeta> = {
  upload: { label: "Upload", shortLabel: "Upload", path: "/upload" },
  pages: {
    label: "Select Pages",
    shortLabel: "Pages",
    path: (id) => `/books/${id}/select-pages`,
  },
  preprocessing: {
    label: "Preprocessing",
    shortLabel: "Preprocess",
    path: (id) => `/books/${id}/preprocessing`,
  },
  ocr: {
    label: "OCR",
    shortLabel: "OCR",
    path: (id) => `/books/${id}/ocr-processing`,
  },
  ocr_review: {
    label: "OCR Review",
    shortLabel: "Review",
    path: (id) => `/books/${id}/ocr-review`,
  },
  llm: {
    label: "LLM Extraction",
    shortLabel: "LLM",
    path: (id) => `/books/${id}/llm-config`,
  },
  review: {
    label: "Metadata Review",
    shortLabel: "Metadata",
    path: (id) => `/books/${id}/metadata-review`,
  },
};

const ACTIVE_JOB_STATUSES = new Set(["queued", "running"]);

const JOB_TYPE_TO_PROCESSING: Record<string, ProcessingKind> = {
  page_extraction: "page_extraction",
  ocr: "ocr",
  llm: "llm",
};

export function stepMeta(key: StepKey): StepMeta {
  return STEP_META[key];
}

export function stepHref(key: StepKey, bookId: string): string {
  const meta = STEP_META[key];
  return typeof meta.path === "function" ? meta.path(bookId) : meta.path;
}

export function deriveWorkflowState({
  book,
  stages,
  pages,
  jobs,
}: WorkflowStateInput): WorkflowState {
  const bookId = book?.id ?? "";
  const stageList = stages ?? [];
  const pageList = pages ?? [];
  const jobList = jobs ?? [];

  const activeJob = (types: string[]): JobResponse | null =>
    jobList.find(
      (j) => types.includes(j.job_type) && ACTIVE_JOB_STATUSES.has(j.status),
    ) ?? null;

  const pageExtractionJob = activeJob(["page_extraction"]);
  const ocrJob = activeJob(["ocr"]);
  const llmJob = activeJob(["llm"]);

  const ocrStageRow = stageList.find((s) => s.stage_name === "ocr");
  const llmStageRow = stageList.find((s) => s.stage_name === "llm_extraction");
  const humanStageRow = stageList.find((s) => s.stage_name === "human_review");
  const ocrStage = ocrStageRow?.status;
  const llmStage = llmStageRow?.status;
  const humanStage = humanStageRow?.status;

  const bookComplete = book?.status === "complete";

  // A downstream stage from an earlier attempt is stale when the upstream
  // stage has since been restarted (higher attempt number). This is exactly
  // what a re-run OCR over existing metadata looks like.
  const isDownstreamStale = (
    upstream: BookStageResponse | undefined,
    downstream: BookStageResponse | undefined,
  ): boolean =>
    !!upstream &&
    !!downstream &&
    (upstream.attempt ?? 1) > (downstream.attempt ?? 1);

  const llmStale = isDownstreamStale(ocrStageRow, llmStageRow);
  const reviewStale =
    isDownstreamStale(llmStageRow, humanStageRow) || llmStale;

  const ocrStarted = ocrStageRow !== undefined || ocrJob !== null;
  const llmStarted = llmStageRow !== undefined && !llmStale;
  const humanStarted = humanStageRow !== undefined && !reviewStale;

  // The pipeline is monotonic: starting a later stage proves every earlier
  // one finished, even when an upstream stage row is missing (legacy books).
  const beyondOcr = llmStarted || humanStarted || bookComplete;
  const pagesComplete =
    pageList.length > 0 || ocrStarted || beyondOcr;
  const preprocessingComplete =
    (pageList.length > 0 && pageList.every((p) => !!p.preprocessing_config)) ||
    ocrStarted ||
    beyondOcr;
  const ocrComplete = ocrStage === "completed" || beyondOcr;

  const state: Record<StepKey, StepState> = {
    upload: book ? "complete" : "not_started",
    pages: pageExtractionJob
      ? "current"
      : pagesComplete
        ? "complete"
        : "not_started",
    preprocessing: preprocessingComplete ? "complete" : "not_started",
    ocr:
      ocrStage === "completed"
        ? "complete"
        : ocrStage === "failed" || ocrStage === "cancelled"
          ? "failed"
          : ocrJob || ocrStage === "processing" || ocrStage === "initiated"
            ? "current"
            : ocrComplete
              ? "complete"
              : "not_started",
    ocr_review:
      llmStarted || humanStarted
        ? "complete"
        : ocrComplete
          ? "current"
          : "not_started",
    llm:
      llmStale
        ? "stale"
        : llmStage === "completed"
          ? "complete"
          : llmStage === "failed" || llmStage === "cancelled"
            ? "failed"
            : llmJob || llmStage === "processing" || llmStage === "initiated"
              ? "current"
              : humanStarted
                ? "complete"
                : "not_started",
    review:
      reviewStale
        ? "stale"
        : humanStage === "completed" || bookComplete
          ? "complete"
          : llmStage === "completed"
            ? "current"
            : "not_started",
  };

  let currentStep: StepKey = "review";
  let blocked = false;
  for (const key of STEP_ORDER) {
    if (state[key] !== "complete") {
      if (!blocked) {
        currentStep = key;
        if (state[key] === "not_started") {
          state[key] = "current";
        }
      }
      blocked = true;
    }
  }

  const processingJob = pageExtractionJob ?? ocrJob ?? llmJob;
  const processing: WorkflowProcessing | null = processingJob
    ? {
        kind: JOB_TYPE_TO_PROCESSING[processingJob.job_type] ?? "ocr",
        job: processingJob,
        progress: processingJob.progress ?? 0,
      }
    : null;

  const steps: WorkflowStep[] = STEP_ORDER.map((key) => {
    const meta = STEP_META[key];
    let detail: string | undefined;
    if (key === "pages" && pageExtractionJob) detail = "Rendering pages…";
    if (key === "ocr" && ocrJob) detail = "Reading pages…";
    if (key === "llm" && llmJob) detail = "Extracting metadata…";
    return {
      key,
      label: meta.label,
      shortLabel: meta.shortLabel,
      href: stepHref(key, bookId),
      state: state[key],
      detail,
    };
  });

  const byKey = steps.reduce(
    (acc, step) => {
      acc[step.key] = step;
      return acc;
    },
    {} as Record<StepKey, WorkflowStep>,
  );

  return { steps, byKey, currentStep, processing };
}

import { describe, it, expect } from "vitest";
import { deriveWorkflowState, type StepKey } from "@/lib/workflow-state";
import type {
  BookDetail,
  BookStageResponse,
  JobResponse,
  PageResponse,
  PreprocessingConfig,
} from "@/lib/api";

const CONFIG: PreprocessingConfig = {
  grayscale: true,
  brightness: 0,
  contrast: 0,
  binarization: "sauvola",
  adaptive_block_size: 11,
  adaptive_c: 2,
  deskew: true,
  denoise: true,
  denoise_strength: 7,
};

function makeBook(overrides: Partial<BookDetail> = {}): BookDetail {
  return {
    id: "book-1",
    filename: "book.pdf",
    title: null,
    language: "tel",
    total_pages: 10,
    status: "uploaded",
    created_at: "2024-01-01T00:00:00",
    updated_at: "2024-01-01T00:00:00",
    ...overrides,
  };
}

function makeStage(
  stage_name: string,
  status: string,
  attempt = 1,
): BookStageResponse {
  return {
    id: `${stage_name}-${attempt}`,
    book_id: "book-1",
    stage_name,
    attempt,
    status,
    started_at: null,
    completed_at: null,
    error_log: null,
    created_at: "2024-01-01T00:00:00",
    updated_at: "2024-01-01T00:00:00",
  };
}

function makePage(
  page_number: number,
  config: PreprocessingConfig | null,
): PageResponse {
  return {
    id: `page-${page_number}`,
    page_number,
    image_path: `pages/${page_number}.png`,
    preprocessing_config: config,
  };
}

function makeJob(overrides: Partial<JobResponse> = {}): JobResponse {
  return {
    id: "job-1",
    book_id: "book-1",
    job_type: "ocr",
    status: "running",
    progress: 0,
    created_at: "2024-01-01T00:00:00",
    started_at: "2024-01-01T00:00:00",
    completed_at: null,
    error_log: null,
    ...overrides,
  };
}

function stepState(
  state: ReturnType<typeof deriveWorkflowState>,
  key: StepKey,
) {
  return state.byKey[key].state;
}

describe("deriveWorkflowState", () => {
  it("marks upload complete and pages as the first step for a fresh book", () => {
    const state = deriveWorkflowState({ book: makeBook() });
    expect(stepState(state, "upload")).toBe("complete");
    expect(stepState(state, "pages")).toBe("current");
    expect(stepState(state, "ocr")).toBe("not_started");
    expect(state.currentStep).toBe("pages");
    expect(state.processing).toBeNull();
  });

  it("treats a null book as an empty workflow", () => {
    const state = deriveWorkflowState({ book: null });
    expect(stepState(state, "upload")).toBe("current");
    expect(stepState(state, "ocr")).toBe("not_started");
    expect(state.currentStep).toBe("upload");
  });

  it("completes pages and points at preprocessing once pages exist", () => {
    const state = deriveWorkflowState({
      book: makeBook(),
      pages: [makePage(1, null), makePage(2, null)],
    });
    expect(stepState(state, "pages")).toBe("complete");
    expect(stepState(state, "preprocessing")).toBe("current");
    expect(state.currentStep).toBe("preprocessing");
  });

  it("completes preprocessing when every page has a config", () => {
    const state = deriveWorkflowState({
      book: makeBook(),
      pages: [makePage(1, CONFIG), makePage(2, CONFIG)],
    });
    expect(stepState(state, "preprocessing")).toBe("complete");
    expect(stepState(state, "ocr")).toBe("current");
    expect(state.currentStep).toBe("ocr");
  });

  it("does not complete preprocessing when only some pages have a config", () => {
    const state = deriveWorkflowState({
      book: makeBook(),
      pages: [makePage(1, CONFIG), makePage(2, null)],
    });
    expect(stepState(state, "preprocessing")).toBe("current");
  });

  it("reports a running OCR job as processing", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "ocr_running" }),
      pages: [makePage(1, CONFIG)],
      stages: [makeStage("ocr", "processing")],
      jobs: [makeJob({ job_type: "ocr", status: "running", progress: 42 })],
    });
    expect(stepState(state, "ocr")).toBe("current");
    expect(state.processing).toMatchObject({ kind: "ocr", progress: 42 });
  });

  it("completes OCR and points at OCR review when the ocr stage completes", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "ocr_complete" }),
      pages: [makePage(1, CONFIG)],
      stages: [makeStage("ocr", "completed")],
    });
    expect(stepState(state, "ocr")).toBe("complete");
    expect(stepState(state, "ocr_review")).toBe("current");
    expect(state.currentStep).toBe("ocr_review");
  });

  it("marks OCR failed when the stage fails", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "ocr_running" }),
      pages: [makePage(1, CONFIG)],
      stages: [makeStage("ocr", "failed")],
    });
    expect(stepState(state, "ocr")).toBe("failed");
    expect(state.currentStep).toBe("ocr");
  });

  it("completes OCR review once LLM extraction is initiated", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "llm_running" }),
      pages: [makePage(1, CONFIG)],
      stages: [makeStage("ocr", "completed"), makeStage("llm_extraction", "processing")],
    });
    expect(stepState(state, "ocr_review")).toBe("complete");
    expect(stepState(state, "llm")).toBe("current");
    expect(state.currentStep).toBe("llm");
  });

  it("completes LLM and points at metadata review", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "awaiting_review" }),
      stages: [
        makeStage("ocr", "completed"),
        makeStage("llm_extraction", "completed"),
      ],
    });
    expect(stepState(state, "llm")).toBe("complete");
    expect(stepState(state, "review")).toBe("current");
    expect(state.currentStep).toBe("review");
  });

  it("completes review when the human_review stage completes", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "awaiting_review" }),
      stages: [
        makeStage("llm_extraction", "completed"),
        makeStage("human_review", "completed"),
      ],
    });
    expect(stepState(state, "review")).toBe("complete");
    expect(state.steps.every((s) => s.state === "complete")).toBe(true);
    expect(state.currentStep).toBe("review");
  });

  it("completes review when the book status is complete", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "complete" }),
    });
    expect(stepState(state, "review")).toBe("complete");
  });

  it("marks downstream completed steps stale after an upstream re-run", () => {
    const state = deriveWorkflowState({
      book: makeBook({ status: "ocr_running" }),
      stages: [
        makeStage("ocr", "processing", 2),
        makeStage("llm_extraction", "completed", 1),
      ],
    });
    expect(stepState(state, "ocr")).toBe("current");
    expect(stepState(state, "llm")).toBe("stale");
    expect(state.currentStep).toBe("ocr");
  });

  it("reports a running page-extraction job on the pages step", () => {
    const state = deriveWorkflowState({
      book: makeBook(),
      jobs: [
        makeJob({
          id: "job-pe",
          job_type: "page_extraction",
          status: "running",
          progress: 25,
        }),
      ],
    });
    expect(stepState(state, "pages")).toBe("current");
    expect(state.processing).toMatchObject({
      kind: "page_extraction",
      progress: 25,
    });
  });

  it("builds hrefs for each step", () => {
    const state = deriveWorkflowState({ book: makeBook() });
    expect(state.byKey.pages.href).toBe("/books/book-1/select-pages");
    expect(state.byKey.review.href).toBe("/books/book-1/metadata-review");
    expect(state.byKey.upload.href).toBe("/upload");
  });
});

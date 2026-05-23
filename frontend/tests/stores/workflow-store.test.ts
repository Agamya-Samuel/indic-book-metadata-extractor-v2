import { describe, it, expect, beforeEach, vi } from "vitest";
import { useWorkflowStore, statusToStep } from "@/stores/workflow-store";
import type { WorkflowStep } from "@/stores/workflow-store";

vi.mock("@/lib/api", () => ({
  getBook: vi.fn().mockResolvedValue({ status: "ocr_complete" }),
}));

describe("statusToStep", () => {
  it.each([
    ["uploaded", 2],
    ["pages_selected", 3],
    ["ocr_running", 3],
    ["ocr_complete", 5],
    ["llm_running", 5],
    ["complete", 7],
  ] as [string, number][])('maps "%s" to step %s', (status, step) => {
    expect(statusToStep(status)).toBe(step as WorkflowStep);
  });

  it("returns step 1 for unknown status", () => {
    expect(statusToStep("unknown_status")).toBe(1);
  });
});

describe("useWorkflowStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useWorkflowStore.getState().reset();
  });

  it("has correct initial state", () => {
    const state = useWorkflowStore.getState();
    expect(state.bookId).toBeNull();
    expect(state.currentStep).toBe(1);
    expect(state.completedStep).toBe(1);
    expect(state.ocrJobId).toBeNull();
    expect(state.ocrJobStatus).toBeNull();
  });

  it("sets book ID", () => {
    useWorkflowStore.getState().setBookId("book-abc");
    expect(useWorkflowStore.getState().bookId).toBe("book-abc");
  });

  it("sets current step", () => {
    useWorkflowStore.getState().setStep(3);
    expect(useWorkflowStore.getState().currentStep).toBe(3);
  });

  it("sets completed step", () => {
    useWorkflowStore.getState().setCompletedStep(4);
    expect(useWorkflowStore.getState().completedStep).toBe(4);
  });

  it("nextStep increments and updates completedStep", () => {
    useWorkflowStore.getState().setStep(2);
    useWorkflowStore.getState().nextStep();
    const state = useWorkflowStore.getState();
    expect(state.currentStep).toBe(3);
    expect(state.completedStep).toBe(3);
  });

  it("nextStep does not exceed step 7", () => {
    useWorkflowStore.getState().setStep(7);
    useWorkflowStore.getState().nextStep();
    expect(useWorkflowStore.getState().currentStep).toBe(7);
  });

  it("previousStep decrements current step", () => {
    useWorkflowStore.getState().setStep(4);
    useWorkflowStore.getState().previousStep();
    expect(useWorkflowStore.getState().currentStep).toBe(3);
  });

  it("previousStep does not go below step 1", () => {
    useWorkflowStore.getState().setStep(1);
    useWorkflowStore.getState().previousStep();
    expect(useWorkflowStore.getState().currentStep).toBe(1);
  });

  it("sets OCR job ID", () => {
    useWorkflowStore.getState().setOcrJobId("job-123");
    expect(useWorkflowStore.getState().ocrJobId).toBe("job-123");
  });

  it("sets OCR job status", () => {
    useWorkflowStore.getState().setOcrJobStatus("running");
    expect(useWorkflowStore.getState().ocrJobStatus).toBe("running");
  });

  it("resets all state", () => {
    useWorkflowStore.getState().setBookId("book-1");
    useWorkflowStore.getState().setStep(5);
    useWorkflowStore.getState().setCompletedStep(4);
    useWorkflowStore.getState().setOcrJobId("job-1");
    useWorkflowStore.getState().setOcrJobStatus("completed");

    useWorkflowStore.getState().reset();

    const state = useWorkflowStore.getState();
    expect(state.bookId).toBeNull();
    expect(state.currentStep).toBe(1);
    expect(state.completedStep).toBe(1);
    expect(state.ocrJobId).toBeNull();
    expect(state.ocrJobStatus).toBeNull();
  });

  it("nextStep updates completedStep to max", () => {
    useWorkflowStore.getState().setCompletedStep(5);
    useWorkflowStore.getState().setStep(3);
    useWorkflowStore.getState().nextStep();
    const state = useWorkflowStore.getState();
    expect(state.currentStep).toBe(4);
    expect(state.completedStep).toBe(5);
  });

  it("hydrates from server", async () => {
    await useWorkflowStore.getState().hydrateFromServer("book-xyz");
    const state = useWorkflowStore.getState();
    expect(state.bookId).toBe("book-xyz");
    expect(state.currentStep).toBe(5);
    expect(state.completedStep).toBe(5);
  });
});

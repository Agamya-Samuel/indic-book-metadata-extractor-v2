import { create } from "zustand";

type WorkflowStep = 1 | 2 | 3 | 4 | 5 | 6 | 7;

interface WorkflowStore {
  bookId: string | null;
  currentStep: WorkflowStep;
  ocrJobId: string | null;
  ocrJobStatus: string | null;
  setBookId: (bookId: string | null) => void;
  setStep: (step: WorkflowStep) => void;
  nextStep: () => void;
  previousStep: () => void;
  setOcrJobId: (jobId: string | null) => void;
  setOcrJobStatus: (status: string | null) => void;
  reset: () => void;
}

const STEP_MAP: Record<string, WorkflowStep> = {
  uploaded: 1,
  pages_selected: 3,
  ocr_running: 4,
  ocr_complete: 5,
  llm_running: 6,
  complete: 7,
};

export function statusToStep(status: string): WorkflowStep {
  return STEP_MAP[status] ?? 1;
}

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  bookId: null,
  currentStep: 1,
  ocrJobId: null,
  ocrJobStatus: null,

  setBookId: (bookId) => set({ bookId }),

  setStep: (step) => set({ currentStep: step }),

  nextStep: () =>
    set((state) => ({
      currentStep: Math.min(state.currentStep + 1, 7) as WorkflowStep,
    })),

  previousStep: () =>
    set((state) => ({
      currentStep: Math.max(state.currentStep - 1, 1) as WorkflowStep,
    })),

  setOcrJobId: (jobId) => set({ ocrJobId: jobId }),

  setOcrJobStatus: (status) => set({ ocrJobStatus: status }),

  reset: () =>
    set({
      bookId: null,
      currentStep: 1,
      ocrJobId: null,
      ocrJobStatus: null,
    }),
}));

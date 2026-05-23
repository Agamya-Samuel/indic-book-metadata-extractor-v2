import { create } from "zustand";
import { persist } from "zustand/middleware";
import { useEffect } from "react";
import { getBook } from "@/lib/api";

export type WorkflowStep = 1 | 2 | 3 | 4 | 5 | 6 | 7;

interface WorkflowStore {
  bookId: string | null;
  currentStep: WorkflowStep;
  completedStep: WorkflowStep;
  ocrJobId: string | null;
  ocrJobStatus: string | null;
  setBookId: (bookId: string | null) => void;
  setStep: (step: WorkflowStep) => void;
  setCompletedStep: (step: WorkflowStep) => void;
  nextStep: () => void;
  previousStep: () => void;
  setOcrJobId: (jobId: string | null) => void;
  setOcrJobStatus: (status: string | null) => void;
  hydrateFromServer: (bookId: string) => Promise<void>;
  reset: () => void;
}

const STEP_MAP: Record<string, WorkflowStep> = {
  uploaded: 2,
  pages_selected: 3,
  ocr_running: 3,
  ocr_complete: 5,
  llm_running: 5,
  complete: 7,
};

export function statusToStep(status: string): WorkflowStep {
  return STEP_MAP[status] ?? 1;
}

export const useWorkflowStore = create<WorkflowStore>()(
  persist(
    (set) => ({
      bookId: null,
      currentStep: 1,
      completedStep: 1,
      ocrJobId: null,
      ocrJobStatus: null,

      setBookId: (bookId) => set({ bookId }),

      setStep: (step) => set({ currentStep: step }),

      setCompletedStep: (step) => set({ completedStep: step }),

      nextStep: () =>
        set((state) => {
          const next = Math.min(state.currentStep + 1, 7) as WorkflowStep;
          return {
            currentStep: next,
            completedStep: Math.max(state.completedStep, next),
          };
        }),

      previousStep: () =>
        set((state) => ({
          currentStep: Math.max(state.currentStep - 1, 1) as WorkflowStep,
        })),

      setOcrJobId: (jobId) => set({ ocrJobId: jobId }),

      setOcrJobStatus: (status) => set({ ocrJobStatus: status }),

      hydrateFromServer: async (bookId: string) => {
        try {
          const book = await getBook(bookId);
          const step = statusToStep(book.status);
          set({
            bookId,
            currentStep: step,
            completedStep: step,
          });
        } catch {
          set({ bookId });
        }
      },

      reset: () =>
        set({
          bookId: null,
          currentStep: 1,
          completedStep: 1,
          ocrJobId: null,
          ocrJobStatus: null,
        }),
    }),
    {
      name: "workflow-storage",
      partialize: (state) => ({
        bookId: state.bookId,
        currentStep: state.currentStep,
        completedStep: state.completedStep,
      }),
    }
  )
);

export function useWorkflowHydration(bookId: string) {
  const storeBookId = useWorkflowStore((s) => s.bookId);
  const hydrateFromServer = useWorkflowStore((s) => s.hydrateFromServer);

  useEffect(() => {
    if (bookId && storeBookId !== bookId) {
      hydrateFromServer(bookId);
    }
  }, [bookId, storeBookId, hydrateFromServer]);
}

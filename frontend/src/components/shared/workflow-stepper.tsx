"use client";

import Link from "next/link";

export type WorkflowStep = 1 | 2 | 3 | 4 | 5 | 6 | 7;

interface WorkflowStepDef {
  step: WorkflowStep;
  label: string;
  shortLabel: string;
  getPath: (bookId: string) => string;
}

const WORKFLOW_STEPS: WorkflowStepDef[] = [
  { step: 1, label: "Upload", shortLabel: "Upload", getPath: () => "/upload" },
  {
    step: 2,
    label: "Select Pages",
    shortLabel: "Pages",
    getPath: (id) => `/books/${id}/select-pages`,
  },
  {
    step: 3,
    label: "Preprocessing",
    shortLabel: "Preprocess",
    getPath: (id) => `/books/${id}/preprocessing`,
  },
  {
    step: 4,
    label: "OCR Review",
    shortLabel: "OCR",
    getPath: (id) => `/books/${id}/ocr-review`,
  },
  {
    step: 5,
    label: "LLM Config",
    shortLabel: "LLM",
    getPath: (id) => `/books/${id}/llm-config`,
  },
  {
    step: 6,
    label: "Metadata Review",
    shortLabel: "Metadata",
    getPath: (id) => `/books/${id}/metadata-review`,
  },
  {
    step: 7,
    label: "Complete",
    shortLabel: "Done",
    getPath: () => "/library",
  },
];

interface WorkflowStepperProps {
  bookId: string;
  currentStep: WorkflowStep;
  completedStep: WorkflowStep;
}

export default function WorkflowStepper({
  bookId,
  currentStep,
  completedStep,
}: WorkflowStepperProps) {
  return (
    <nav
      className="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-4 py-3"
      aria-label="Workflow progress"
    >
      <div className="max-w-screen-2xl mx-auto">
        <ol className="flex items-center gap-1 overflow-x-auto" role="list">
          {WORKFLOW_STEPS.map((def, idx) => {
            const isCompleted = def.step < currentStep && def.step <= completedStep;
            const isCurrent = def.step === currentStep;
            const isClickable = isCompleted || (def.step <= completedStep && def.step !== currentStep);

            return (
              <li key={def.step} className="flex items-center">
                {idx > 0 && (
                  <svg
                    className={`w-4 h-4 mx-1 flex-shrink-0 ${
                      isCompleted || isCurrent ? "text-blue-500 dark:text-blue-400" : "text-gray-300 dark:text-gray-600"
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                )}

                {isClickable ? (
                  <Link
                    href={def.getPath(bookId)}
                    aria-current={isCurrent ? "step" : undefined}
                    className={`flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
                      isCurrent
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                        : isCompleted
                          ? "text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30"
                          : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                    }`}
                  >
                    <span
                      className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                        isCurrent
                          ? "bg-blue-600 text-white dark:bg-blue-500"
                          : isCompleted
                            ? "bg-green-500 text-white"
                            : "bg-gray-200 text-gray-500 dark:bg-gray-600 dark:text-gray-400"
                      }`}
                    >
                      {isCompleted ? (
                        <svg
                          className="w-3 h-3"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                          aria-hidden="true"
                        >
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      ) : (
                        def.step
                      )}
                    </span>
                    <span className="hidden md:inline">{def.label}</span>
                    <span className="md:hidden">{def.shortLabel}</span>
                  </Link>
                ) : (
                  <span
                    aria-current={isCurrent ? "step" : undefined}
                    className={`flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap ${
                      isCurrent
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                        : "text-gray-400 dark:text-gray-500 cursor-not-allowed"
                    }`}
                  >
                    <span
                      className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                        isCurrent
                          ? "bg-blue-600 text-white dark:bg-blue-500"
                          : "bg-gray-200 text-gray-400 dark:bg-gray-600 dark:text-gray-500"
                      }`}
                    >
                      {def.step}
                    </span>
                    <span className="hidden md:inline">{def.label}</span>
                    <span className="md:hidden">{def.shortLabel}</span>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}

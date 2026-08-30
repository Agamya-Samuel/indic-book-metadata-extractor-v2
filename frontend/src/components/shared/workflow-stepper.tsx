"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

export type WorkflowStep = 1 | 2 | 3 | 4 | 5 | 6 | 7;

interface WorkflowStepDef {
  step: WorkflowStep;
  label: string;
  shortLabel: string;
  getPath: (bookId: string) => string;
  requiresHumanReview?: boolean;
  isAutomaticProcessing?: boolean;
}

const WORKFLOW_STEPS: WorkflowStepDef[] = [
  { step: 1, label: "Upload", shortLabel: "Upload", getPath: () => "/upload" },
  { step: 2, label: "Select Pages", shortLabel: "Pages", getPath: (id) => `/books/${id}/select-pages`, requiresHumanReview: true },
  { step: 3, label: "Preprocessing", shortLabel: "Preprocess", getPath: (id) => `/books/${id}/preprocessing` },
  { step: 4, label: "OCR Review", shortLabel: "OCR", getPath: (id) => `/books/${id}/ocr-review`, requiresHumanReview: true },
  { step: 5, label: "LLM Config", shortLabel: "LLM", getPath: (id) => `/books/${id}/llm-config`, requiresHumanReview: true },
  { step: 6, label: "Metadata Review", shortLabel: "Metadata", getPath: (id) => `/books/${id}/metadata-review`, requiresHumanReview: true },
  { step: 7, label: "Complete", shortLabel: "Done", getPath: () => "/library" },
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
      aria-label="Workflow progress"
      className="border-b border-[var(--border)] bg-[var(--surface)]/60 backdrop-blur"
    >
      <div className="mx-auto max-w-[var(--content-max)] px-4 sm:px-6 lg:px-8">
        <ol
          className="flex items-center gap-0.5 overflow-x-auto py-3"
          role="list"
        >
          {WORKFLOW_STEPS.map((def, idx) => {
            const isCompleted =
              def.step < currentStep && def.step <= completedStep;
            const isCurrent = def.step === currentStep;
            const isClickable =
              isCompleted ||
              (def.step <= completedStep && def.step !== currentStep);
            const showHumanBadge = def.requiresHumanReview && !isCompleted;

            return (
              <li key={def.step} className="flex items-center shrink-0">
                {idx > 0 && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mx-1 sm:mx-1.5 h-px w-4 sm:w-6",
                      isCompleted || isCurrent
                        ? "bg-[var(--accent)]"
                        : "bg-[var(--border)]",
                    )}
                  />
                )}

                {isClickable ? (
                  <Link
                    href={def.getPath(bookId)}
                    aria-current={isCurrent ? "step" : undefined}
                    aria-label={`${def.label}${isCurrent ? ", current step" : isCompleted ? ", completed" : ""}${def.requiresHumanReview ? ", requires human review" : ""}`}
                    className={cn(
                      "group inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-[var(--radius)] min-h-11",
                      "text-[var(--text-sm)] font-medium whitespace-nowrap",
                      "transition-colors duration-[var(--duration-fast)]",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
                      isCurrent
                        ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                        : isCompleted
                          ? "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]"
                          : "text-[var(--text-subtle)] hover:bg-[var(--surface-sunken)]",
                    )}
                  >
                    <StepCircle
                      step={def.step}
                      completed={isCompleted}
                      current={isCurrent}
                      requiresHumanReview={def.requiresHumanReview}
                    />
                    <span className="hidden md:inline">{def.label}</span>
                    <span className="md:hidden">{def.shortLabel}</span>
                    {showHumanBadge && (
                      <HumanReviewBadge />
                    )}
                  </Link>
                ) : (
                  <span
                    aria-current={isCurrent ? "step" : undefined}
                    aria-label={`${def.label}, locked — complete the previous step first`}
                    aria-disabled="true"
                    className={cn(
                      "inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-[var(--radius)]",
                      "text-[var(--text-sm)] font-medium whitespace-nowrap",
                      isCurrent
                        ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                        : "text-[var(--text-subtle)] cursor-not-allowed",
                    )}
                  >
                    <StepCircle
                      step={def.step}
                      completed={false}
                      current={isCurrent}
                      requiresHumanReview={def.requiresHumanReview}
                    />
                    <span className="hidden md:inline">{def.label}</span>
                    <span className="md:hidden">{def.shortLabel}</span>
                    {showHumanBadge && (
                      <HumanReviewBadge />
                    )}
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

function StepCircle({
  step,
  completed,
  current,
  requiresHumanReview,
}: {
  step: WorkflowStep;
  completed: boolean;
  current: boolean;
  requiresHumanReview?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-5 items-center justify-center rounded-full text-[10px] font-bold leading-none",
        completed
          ? "bg-[var(--success-600)] text-[var(--text-inverse)]"
          : current
            ? requiresHumanReview
              ? "bg-[var(--warning-500)] text-[var(--text-inverse)] animate-current-step"
              : "bg-[var(--accent)] text-[var(--text-inverse)] animate-current-step"
            : "bg-[var(--surface-sunken)] text-[var(--text-subtle)] border border-[var(--border)]",
      )}
    >
      {completed ? (
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="size-3 animate-step-check"
        >
          <path
            fillRule="evenodd"
            d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
            clipRule="evenodd"
          />
        </svg>
      ) : (
        step
      )}
    </span>
  );
}

function HumanReviewBadge() {
  return (
    <span
      title="This step requires human review"
      className={cn(
        "hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full",
        "bg-[var(--warning-100)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/30 dark:text-[var(--warning-100)]",
        "text-[10px] font-medium"
      )}
    >
      <svg
        className="w-3 h-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
        />
      </svg>
      Review
    </span>
  );
}

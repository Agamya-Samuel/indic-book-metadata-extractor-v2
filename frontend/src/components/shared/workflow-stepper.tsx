"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import type { StepKey, StepState, WorkflowStep } from "@/lib/workflow-state";

interface WorkflowStepperProps {
  steps: WorkflowStep[];
  currentStep?: StepKey;
  className?: string;
}

const STATE_LABEL: Record<StepState, string> = {
  complete: "completed",
  current: "current step",
  failed: "failed",
  stale: "out of date",
  not_started: "not started",
};

/**
 * Presentational stepper. All state is derived by `deriveWorkflowState`; this
 * component never decides what is complete.
 */
export default function WorkflowStepper({
  steps,
  currentStep,
  className,
}: WorkflowStepperProps) {
  return (
    <nav
      aria-label="Workflow progress"
      className={cn(
        "border-b border-[var(--border)] bg-[var(--surface)]/60 backdrop-blur",
        className,
      )}
    >
      <div className="mx-auto max-w-[var(--content-max)] px-4 sm:px-6 lg:px-8">
        <ol className="flex items-center gap-0.5 overflow-x-auto py-3" role="list">
          {steps.map((step, idx) => {
            const isCurrent = step.key === currentStep || step.state === "current";
            const clickable = step.state !== "not_started";
            const label = `${step.label}, ${STATE_LABEL[step.state]}`;

            const inner = (
              <>
                <StepMarker step={step} index={idx} />
                <span className="hidden md:inline">{step.label}</span>
                <span className="md:hidden">{step.shortLabel}</span>
                {step.detail && (
                  <span className="hidden lg:inline text-[var(--text-xs)] text-[var(--text-muted)]">
                    {step.detail}
                  </span>
                )}
              </>
            );

            return (
              <li key={step.key} className="flex items-center shrink-0">
                {idx > 0 && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mx-1 sm:mx-1.5 h-px w-4 sm:w-6",
                      step.state === "complete" || isCurrent
                        ? "bg-[var(--accent)]"
                        : "bg-[var(--border)]",
                    )}
                  />
                )}

                {clickable ? (
                  <Link
                    href={step.href}
                    aria-current={isCurrent ? "step" : undefined}
                    aria-label={label}
                    title={step.detail}
                    data-state={step.state}
                    className={cn(
                      "group inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-[var(--radius)] min-h-11",
                      "text-[var(--text-sm)] font-medium whitespace-nowrap",
                      "transition-colors duration-[var(--duration-fast)]",
                      focusRing,
                      step.state === "current" || isCurrent
                        ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                        : step.state === "failed"
                          ? "text-[var(--danger-700)] dark:text-[var(--danger-100)] hover:bg-[var(--danger-50)] dark:hover:bg-[var(--danger-900)]/20"
                          : step.state === "stale"
                            ? "text-[var(--warning-700)] dark:text-[var(--warning-100)] hover:bg-[var(--warning-50)] dark:hover:bg-[var(--warning-900)]/20"
                            : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                    )}
                  >
                    {inner}
                  </Link>
                ) : (
                  <span
                    aria-label={`${step.label}, locked — complete the previous step first`}
                    aria-disabled="true"
                    data-state={step.state}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-[var(--radius)]",
                      "text-[var(--text-sm)] font-medium whitespace-nowrap",
                      "text-[var(--text-subtle)] cursor-not-allowed",
                    )}
                  >
                    {inner}
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

function StepMarker({ step, index }: { step: WorkflowStep; index: number }) {
  const base =
    "flex size-5 items-center justify-center rounded-full text-[10px] font-bold leading-none";

  if (step.state === "complete") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--success-600)] text-[var(--text-inverse)]")}
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="size-3 animate-step-check">
          <path
            fillRule="evenodd"
            d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    );
  }

  if (step.state === "failed") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--danger-600)] text-[var(--text-inverse)]")}
      >
        !
      </span>
    );
  }

  if (step.state === "stale") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--warning-500)] text-[var(--text-inverse)]")}
      >
        ↻
      </span>
    );
  }

  if (step.state === "current") {
    return (
      <span
        aria-hidden="true"
        className={cn(
          base,
          "bg-[var(--accent)] text-[var(--text-inverse)] animate-current-step",
        )}
      >
        {step.detail ? (
          <svg className="size-3 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          index + 1
        )}
      </span>
    );
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        base,
        "bg-[var(--surface-sunken)] text-[var(--text-subtle)] border border-[var(--border)]",
      )}
    >
      {index + 1}
    </span>
  );
}
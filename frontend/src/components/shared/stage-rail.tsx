"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import { Button } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";
import { StepMarker } from "@/components/shared/step-marker";
import type {
  ProcessingKind,
  StepKey,
  StepState,
  WorkflowProcessing,
  WorkflowStep,
} from "@/lib/workflow-state";

const STATE_LABEL: Record<StepState, string> = {
  complete: "completed",
  current: "current step",
  failed: "failed",
  stale: "out of date",
  not_started: "not started",
};

/** Which stage owns each background monitor. */
const MONITOR_OWNER: Record<ProcessingKind, StepKey> = {
  page_extraction: "pages",
  ocr: "ocr",
  llm: "llm",
};

export interface StageRailProps {
  steps: WorkflowStep[];
  currentStep?: StepKey;
  processing?: WorkflowProcessing | null;
  className?: string;
}

/**
 * The persistent stage rail for a book: one row per stage with its state, plus
 * a running sub-row under the stage that owns the active monitor job. All state
 * is derived upstream by `deriveWorkflowState`; this component never decides
 * what is complete.
 */
export function StageRail({
  steps,
  currentStep,
  processing,
  className,
}: StageRailProps) {
  return (
    <nav aria-label="Workflow stages" className={className}>
      <ol className="flex flex-col gap-0.5" role="list">
        {steps.map((step, idx) => (
          <RailItem
            key={step.key}
            step={step}
            index={idx}
            current={step.key === currentStep}
            monitor={
              processing && MONITOR_OWNER[processing.kind] === step.key
                ? processing
                : null
            }
          />
        ))}
      </ol>
    </nav>
  );
}

function RailItem({
  step,
  index,
  current,
  monitor,
}: {
  step: WorkflowStep;
  index: number;
  current: boolean;
  monitor: WorkflowProcessing | null;
}) {
  const clickable = step.state !== "not_started";
  const running = monitor !== null;
  const isCurrent = current || step.state === "current";
  // A stage whose job is running is the live state; it outranks "stale" (the
  // previous output is out of date precisely because this run is redoing it).
  const label = running
    ? `${step.label}, running`
    : `${step.label}, ${STATE_LABEL[step.state]}`;

  const inner = (
    <>
      <StepMarker
        state={running ? "current" : step.state}
        index={index}
        busy={running}
        size="md"
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">{step.label}</span>
        {step.detail && !monitor && (
          <span className="truncate text-[length:var(--text-xs)] font-normal text-[var(--text-muted)]">
            {step.detail}
          </span>
        )}
      </span>
    </>
  );

  const rowClass = cn(
    "flex min-h-11 w-full items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-2",
    "text-[length:var(--text-sm)] font-medium",
    "transition-colors duration-[var(--duration-fast)]",
    running || isCurrent
      ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
      : step.state === "failed"
        ? "text-[var(--danger-700)] dark:text-[var(--danger-100)] hover:bg-[var(--danger-50)] dark:hover:bg-[var(--danger-900)]/20"
        : step.state === "stale"
          ? "text-[var(--warning-700)] dark:text-[var(--warning-100)] hover:bg-[var(--warning-50)] dark:hover:bg-[var(--warning-900)]/20"
          : step.state === "complete"
            ? "text-[var(--text)] hover:bg-[var(--surface-sunken)]"
            : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
  );

  return (
    <li>
      {clickable ? (
        <Link
          href={step.href}
          aria-current={isCurrent ? "step" : undefined}
          aria-label={label}
          className={cn(rowClass, focusRing)}
        >
          {inner}
        </Link>
      ) : (
        <span
          aria-disabled="true"
          aria-label={`${step.label}, locked — complete the previous stage first`}
          className={cn(rowClass, "cursor-not-allowed text-[var(--text-subtle)]")}
        >
          {inner}
        </span>
      )}

      {monitor && (
        {/* ml-14 + px-2.5 + spinner(12) + gap(8) = the stage label's x, so the
            sub-row's text lines up under the stage name. */}
        <div className="mb-1 ml-[14px] mr-1 rounded-[var(--radius)] bg-[var(--surface-sunken)] px-2.5 py-2">
          <div className="flex items-center gap-2">
            <Spinner className="size-3 shrink-0 text-[var(--accent-text)]" />
            <span className="min-w-0 flex-1 truncate text-[length:var(--text-xs)] text-[var(--text-muted)]">
              {step.detail ?? "Running"}
            </span>
            <span className="shrink-0 text-[length:var(--text-xs)] font-medium tabular-nums text-[var(--text)]">
              {Math.round(monitor.progress)}%
            </span>
          </div>
          <div
            role="progressbar"
            aria-label="Job progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(monitor.progress)}
            className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--border)]"
          >
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-500 ease-out"
              style={{
                width: `${Math.max(0, Math.min(100, monitor.progress))}%`,
              }}
            />
          </div>
        </div>
      )}
    </li>
  );
}

export interface StageRailMobileProps {
  steps: WorkflowStep[];
  currentStep?: StepKey;
  processing?: WorkflowProcessing | null;
  className?: string;
}

/**
 * Mobile companion to the rail: a sticky bar showing the current stage plus a
 * sheet holding the full list. Hidden from `lg` up, where the rail is shown.
 */
export function StageRailMobile({
  steps,
  currentStep,
  processing,
  className,
}: StageRailMobileProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    panelRef.current?.querySelector<HTMLElement>("a")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const currentIndex = Math.max(
    0,
    steps.findIndex((s) => s.key === currentStep),
  );
  const current = steps[currentIndex];

  return (
    <div className={cn("lg:hidden", className)}>
      <div className="sticky top-[var(--nav-height)] z-30 border-b border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur">
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <StepMarker
              state={current.state}
              index={currentIndex}
              busy={!!processing}
              size="sm"
            />
            <span className="min-w-0 truncate text-[length:var(--text-sm)] font-medium text-[var(--text)]">
              {current.label}
            </span>
            {processing && (
              <span className="text-[length:var(--text-xs)] tabular-nums text-[var(--text-muted)]">
                {Math.round(processing.progress)}%
              </span>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOpen(true)}
            aria-expanded={open}
          >
            All stages
          </Button>
        </div>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50"
          role="dialog"
          aria-modal="true"
          aria-label="Workflow stages"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            ref={panelRef}
            className="absolute inset-y-0 left-0 w-72 max-w-[85vw] overflow-y-auto border-r border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-md)]"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[length:var(--text-sm)] font-semibold text-[var(--text)]">
                Stages
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setOpen(false)}
                aria-label="Close stage list"
              >
                Close
              </Button>
            </div>
            <StageRail
              steps={steps}
              currentStep={currentStep}
              processing={processing}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default StageRail;

import { cn } from "@/lib/utils";
import type { StepState } from "@/lib/workflow-state";

export interface StepMarkerProps {
  state: StepState;
  /** Zero-based position; rendered as `index + 1` when the marker shows a number. */
  index: number;
  /** Show a spinner instead of the number for a running current step. */
  busy?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const SIZES: Record<NonNullable<StepMarkerProps["size"]>, string> = {
  sm: "size-5 text-[10px]",
  md: "size-6 text-[11px]",
};

const SPINNER_SIZES: Record<NonNullable<StepMarkerProps["size"]>, string> = {
  sm: "size-3",
  md: "size-3.5",
};

/**
 * The state disc for a workflow stage: complete, failed, stale, running
 * (current), or not started. Shared by the stage rail and, until Phase 1
 * retires it, the horizontal stepper.
 */
export function StepMarker({
  state,
  index,
  busy = false,
  size = "sm",
  className,
}: StepMarkerProps) {
  const base = cn(
    "flex shrink-0 items-center justify-center rounded-full font-bold leading-none",
    SIZES[size],
    className,
  );

  if (state === "complete") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--success-600)] text-[var(--text-inverse)]")}
      >
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className={cn("size-3 animate-step-check", size === "md" && "size-3.5")}
        >
          <path
            fillRule="evenodd"
            d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    );
  }

  if (state === "failed") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--danger-600)] text-[var(--text-inverse)]")}
      >
        !
      </span>
    );
  }

  if (state === "stale") {
    return (
      <span
        aria-hidden="true"
        className={cn(base, "bg-[var(--warning-500)] text-[var(--text-inverse)]")}
      >
        ↻
      </span>
    );
  }

  if (state === "current") {
    return (
      <span
        aria-hidden="true"
        className={cn(
          base,
          "bg-[var(--accent)] text-[var(--text-inverse)] animate-current-step",
        )}
      >
        {busy ? (
          <svg
            className={cn("animate-spin", SPINNER_SIZES[size])}
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
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
        "border border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-subtle)]",
      )}
    >
      {index + 1}
    </span>
  );
}

export default StepMarker;

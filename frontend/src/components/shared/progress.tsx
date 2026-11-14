"use client";

import { cn } from "@/lib/utils";

/**
 * The one progress primitive. The whole app uses a 0–100 contract for
 * `value` (the backend's native job-progress scale); `max` exists only for
 * the rare caller that has a raw fraction.
 */

export function clampPercent(
  value: number | null | undefined,
  max = 100,
): number {
  if (value == null || Number.isNaN(value) || max <= 0) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

export type ProgressTone = "accent" | "success" | "warning" | "danger";

const TONE_FILL: Record<ProgressTone, string> = {
  accent: "bg-[var(--accent)]",
  success: "bg-[var(--success-600)]",
  warning: "bg-[var(--warning-600)]",
  danger: "bg-[var(--danger-600)]",
};

export interface ProgressProps {
  /** Progress in the 0–100 range. */
  value?: number;
  /** Optional denominator; defaults to 100 (the app-wide contract). */
  max?: number;
  indeterminate?: boolean;
  label?: string;
  /** Accessible name when the bar is shown without a visible label. */
  ariaLabel?: string;
  showValue?: boolean;
  size?: "sm" | "md";
  tone?: ProgressTone;
  className?: string;
}

export function Progress({
  value,
  max = 100,
  indeterminate = false,
  label,
  ariaLabel,
  showValue = false,
  size = "sm",
  tone = "accent",
  className,
}: ProgressProps) {
  const pct = clampPercent(value, max);
  const fill = TONE_FILL[tone];

  return (
    <div className={cn("w-full", className)}>
      {(label || (showValue && !indeterminate)) && (
        <div className="mb-1 flex items-center justify-between gap-2 text-[length:var(--text-xs)] text-[var(--text-muted)]">
          <span className="truncate">{label}</span>
          {showValue && !indeterminate && (
            <span className="shrink-0 tabular-nums">{Math.round(pct)}%</span>
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={indeterminate ? undefined : Math.round(pct)}
        aria-label={ariaLabel ?? label}
        className={cn(
          "w-full overflow-hidden rounded-full bg-[var(--surface-sunken)] border border-[var(--border)]",
          size === "sm" ? "h-1.5" : "h-2",
        )}
      >
        {indeterminate ? (
          <div
            className={cn(
              "h-full w-1/3 rounded-full",
              fill,
              "animate-[progress-indet_1.4s_ease-in-out_infinite]",
            )}
          />
        ) : (
          <div
            className={cn("h-full rounded-full transition-[width] duration-300", fill)}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}

export default Progress;

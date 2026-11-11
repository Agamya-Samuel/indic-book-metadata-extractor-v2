"use client";

import { cn, formatElapsed } from "@/lib/utils";
import { Button } from "@/components/shared/button";
import { Progress, type ProgressTone } from "@/components/shared/progress";
import StatusBadge from "@/components/shared/status-badge";

interface JobProgressCardProps {
  title: string;
  /** 0–100. */
  progress: number;
  status?: string;
  /** Current phase, e.g. "Preprocessing page 12". */
  phase?: string;
  /** Item counter, e.g. "Page 12 of 84". */
  itemLabel?: string;
  elapsedMs?: number;
  error?: string | null;
  onCancel?: () => void;
  onRetry?: () => void;
  cancelling?: boolean;
  tone?: ProgressTone;
  className?: string;
}

/**
 * Honest progress for a long operation: phase, percentage, item counter,
 * elapsed time, cancel, and a failure state with retry.
 */
export function JobProgressCard({
  title,
  progress,
  status,
  phase,
  itemLabel,
  elapsedMs = 0,
  error,
  onCancel,
  onRetry,
  cancelling = false,
  tone,
  className,
}: JobProgressCardProps) {
  const failed = status === "failed" || !!error;
  const cancelled = status === "cancelled";
  const running = status === "running" || status === "queued";
  const indeterminate = !failed && !cancelled && running && progress <= 0;
  const resolvedTone: ProgressTone = failed ? "danger" : tone ?? "accent";

  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-xs)]",
        className,
      )}
      aria-busy={running || undefined}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <h3 className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
            {title}
          </h3>
          {status && <StatusBadge status={status} />}
        </div>
        <div className="flex items-center gap-2 text-[var(--text-xs)] text-[var(--text-muted)] tabular-nums">
          {elapsedMs > 0 && <span>{formatElapsed(elapsedMs)}</span>}
          {onCancel && running && (
            <Button
              variant="outline"
              size="sm"
              onClick={onCancel}
              loading={cancelling}
            >
              Cancel
            </Button>
          )}
          {failed && onRetry && (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      </header>

      <div className="mt-3">
        <Progress
          value={progress}
          indeterminate={indeterminate}
          tone={resolvedTone}
          label={phase}
          showValue={!indeterminate}
          size="md"
        />
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-[var(--text-xs)] text-[var(--text-muted)]">
        <span className="truncate">{itemLabel}</span>
        {cancelled && <span className="text-[var(--warning-700)]">Cancelled</span>}
      </div>

      {failed && error && (
        <p
          role="alert"
          className="mt-3 rounded-[var(--radius)] border border-[var(--danger-500)]/30 bg-[var(--danger-50)] px-3 py-2 text-[var(--text-xs)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]"
        >
          {error}
        </p>
      )}
    </section>
  );
}

export default JobProgressCard;

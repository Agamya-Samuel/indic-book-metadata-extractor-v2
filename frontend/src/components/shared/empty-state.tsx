import * as React from "react";
import { cn } from "@/lib/utils";

/** A polite, full-bleed empty state. Title names what should be here, action shows how to fill it. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center px-6 py-12 sm:py-16",
        "rounded-[var(--radius-lg)] border border-dashed border-[var(--border)]",
        "bg-[var(--surface-sunken)]/40",
        "animate-fade-in",
        className,
      )}
    >
      {icon && (
        <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[var(--surface-raised)] text-[var(--text-muted)] border border-[var(--border)]">
          {icon}
        </div>
      )}
      <h3 className="text-[var(--text-md)] font-semibold text-[var(--text)]">
        {title}
      </h3>
      {description && (
        <p className="mt-1.5 max-w-md text-[var(--text-sm)] text-[var(--text-muted)]">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** A polite error state with a recovery action. */
export function ErrorState({
  title = "Something went wrong",
  description,
  action,
  className,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--danger-500)]/30",
        "bg-[var(--danger-50)] dark:bg-[var(--danger-900)]/15",
        "px-4 py-3 text-[var(--text-sm)]",
        "text-[var(--danger-700)] dark:text-[var(--danger-100)]",
        "animate-fade-in",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          className="mt-0.5 size-4 shrink-0 fill-current"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-5.5a.75.75 0 001.5 0V9a.75.75 0 00-1.5 0v3.5zm.75 2a1 1 0 100-2 1 1 0 000 2z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1 min-w-0">
          <p className="font-medium">{title}</p>
          {description && (
            <p className="mt-1 text-[var(--text-xs)] opacity-90">
              {description}
            </p>
          )}
          {action && <div className="mt-2.5">{action}</div>}
        </div>
      </div>
    </div>
  );
}

/** An inline informational banner — success, info, warning, neutral. */
type BannerTone = "info" | "success" | "warning" | "neutral";

const toneClass: Record<BannerTone, string> = {
  info: "border-[var(--info-500)]/30 bg-[var(--info-50)] dark:bg-[var(--info-900)]/15 text-[var(--info-700)] dark:text-[var(--info-100)]",
  success:
    "border-[var(--success-500)]/30 bg-[var(--success-50)] dark:bg-[var(--success-900)]/15 text-[var(--success-700)] dark:text-[var(--success-100)]",
  warning:
    "border-[var(--warning-500)]/30 bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/15 text-[var(--warning-700)] dark:text-[var(--warning-100)]",
  neutral: "border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text)]",
};

export function Banner({
  tone = "neutral",
  children,
  className,
}: {
  tone?: BannerTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius)] border px-4 py-3 text-[var(--text-sm)]",
        "animate-fade-in",
        toneClass[tone],
        className,
      )}
      role={tone === "warning" || tone === "info" ? "status" : undefined}
    >
      {children}
    </div>
  );
}

/** A linear progress bar. Indeterminate variant uses a sliding block. */
export function Progress({
  value,
  max = 100,
  indeterminate,
  className,
  tone = "accent",
}: {
  value?: number;
  max?: number;
  indeterminate?: boolean;
  className?: string;
  tone?: "accent" | "success" | "warning" | "danger";
}) {
  const pct =
    typeof value === "number" ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const fill = {
    accent: "bg-[var(--accent)]",
    success: "bg-[var(--success-600)]",
    warning: "bg-[var(--warning-600)]",
    danger: "bg-[var(--danger-600)]",
  }[tone];
  return (
    <div
      className={cn(
        "h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-sunken)] border border-[var(--border)]",
        className,
      )}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={indeterminate ? undefined : value}
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
  );
}

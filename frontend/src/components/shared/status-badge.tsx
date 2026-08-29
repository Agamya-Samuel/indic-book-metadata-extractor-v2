"use client";

import { cn } from "@/lib/utils";

type BadgeStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

interface Config {
  bg: string;
  text: string;
  ring: string;
  dot: string;
  label: string;
  pulse?: boolean;
}

const statusConfig: Record<BadgeStatus, Config> = {
  queued: {
    bg: "bg-[var(--neutral-100)] dark:bg-[var(--neutral-800)]",
    text: "text-[var(--text-muted)]",
    ring: "ring-[var(--border)]",
    dot: "bg-[var(--text-muted)]",
    label: "Queued",
  },
  running: {
    bg: "bg-[var(--info-50)] dark:bg-[var(--info-900)]/20",
    text: "text-[var(--info-700)] dark:text-[var(--info-100)]",
    ring: "ring-[var(--info-500)]/30",
    dot: "bg-[var(--info-500)]",
    label: "Running",
    pulse: true,
  },
  completed: {
    bg: "bg-[var(--success-50)] dark:bg-[var(--success-900)]/20",
    text: "text-[var(--success-700)] dark:text-[var(--success-100)]",
    ring: "ring-[var(--success-500)]/30",
    dot: "bg-[var(--success-600)]",
    label: "Completed",
  },
  failed: {
    bg: "bg-[var(--danger-50)] dark:bg-[var(--danger-900)]/20",
    text: "text-[var(--danger-700)] dark:text-[var(--danger-100)]",
    ring: "ring-[var(--danger-500)]/30",
    dot: "bg-[var(--danger-600)]",
    label: "Failed",
  },
  cancelled: {
    bg: "bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/20",
    text: "text-[var(--warning-700)] dark:text-[var(--warning-100)]",
    ring: "ring-[var(--warning-500)]/30",
    dot: "bg-[var(--warning-600)]",
    label: "Cancelled",
  },
};

const fallback: Config = {
  bg: "bg-[var(--neutral-100)] dark:bg-[var(--neutral-800)]",
  text: "text-[var(--text-muted)]",
  ring: "ring-[var(--border)]",
  dot: "bg-[var(--text-muted)]",
  label: "",
};

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status as BadgeStatus] ?? {
    ...fallback,
    label: status,
  };

  return (
    <span
      role="status"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5",
        "text-[11px] font-medium uppercase tracking-wide",
        "ring-1 ring-inset",
        config.bg,
        config.text,
        config.ring,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "relative inline-flex size-1.5 rounded-full",
          config.dot,
        )}
      >
        {config.pulse && (
          <span
            className={cn(
              "absolute inset-0 rounded-full opacity-75 animate-ping",
              config.dot,
            )}
          />
        )}
      </span>
      {config.label}
    </span>
  );
}

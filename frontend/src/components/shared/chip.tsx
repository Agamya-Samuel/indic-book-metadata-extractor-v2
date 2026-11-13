import * as React from "react";
import { cn } from "@/lib/utils";

export type ChipTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "info";

const TONES: Record<ChipTone, { shell: string; dot: string }> = {
  neutral: {
    shell:
      "border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-muted)]",
    dot: "bg-[var(--text-subtle)]",
  },
  accent: {
    shell:
      "border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--accent-soft-text)]",
    dot: "bg-[var(--accent)]",
  },
  success: {
    shell:
      "border-[var(--success-500)]/30 bg-[var(--success-50)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]",
    dot: "bg-[var(--success-500)]",
  },
  warning: {
    shell:
      "border-[var(--warning-500)]/30 bg-[var(--warning-50)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]",
    dot: "bg-[var(--warning-500)]",
  },
  danger: {
    shell:
      "border-[var(--danger-500)]/30 bg-[var(--danger-50)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]",
    dot: "bg-[var(--danger-500)]",
  },
  info: {
    shell:
      "border-[var(--info-500)]/30 bg-[var(--info-50)] text-[var(--info-700)] dark:bg-[var(--info-900)]/20 dark:text-[var(--info-100)]",
    dot: "bg-[var(--info-500)]",
  },
};

export interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: ChipTone;
  /** Leading status dot. */
  dot?: boolean;
  /** Monospace rendering for identifiers (e.g. a Wikidata property). */
  mono?: boolean;
  children?: React.ReactNode;
}

/** A compact label pill: counts, states, identifiers. */
export function Chip({
  tone = "neutral",
  dot = false,
  mono = false,
  className,
  children,
  ...rest
}: ChipProps) {
  const { shell, dot: dotClass } = TONES[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border font-medium tabular-nums whitespace-nowrap",
        mono
          ? "rounded-[var(--radius-xs)] px-1 py-0.5 font-mono text-[10px]"
          : "rounded-full px-2 py-0.5 text-[11px]",
        shell,
        className,
      )}
      {...rest}
    >
      {dot && (
        <span
          aria-hidden="true"
          className={cn("size-1.5 shrink-0 rounded-full", dotClass)}
        />
      )}
      {children}
    </span>
  );
}

export default Chip;

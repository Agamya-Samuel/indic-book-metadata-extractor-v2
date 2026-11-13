import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Tone = "error" | "success" | "warning" | "info";

const TONES: Record<Tone, { box: string; role: "alert" | "status" }> = {
  error: {
    box: "border-[var(--danger-500)]/30 bg-[var(--danger-50)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]",
    role: "alert",
  },
  success: {
    box: "border-[var(--success-500)]/30 bg-[var(--success-50)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]",
    role: "status",
  },
  warning: {
    box: "border-[var(--warning-500)]/30 bg-[var(--warning-50)] text-[var(--warning-700)] dark:bg-[var(--warning-900)]/20 dark:text-[var(--warning-100)]",
    role: "status",
  },
  info: {
    box: "border-[var(--info-500)]/30 bg-[var(--info-50)] text-[var(--info-700)] dark:bg-[var(--info-900)]/20 dark:text-[var(--info-100)]",
    role: "status",
  },
};

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "role"> {
  tone?: Tone;
  /** Override the default role (alert for error, status otherwise). */
  role?: "alert" | "status";
}

/** The single inline message surface: form errors, confirmations, notices. */
export function Alert({
  tone = "error",
  role,
  className,
  children,
  ...rest
}: AlertProps) {
  const config = TONES[tone];
  return (
    <div
      role={role ?? config.role}
      data-tone={tone}
      className={cn(
        "rounded-[var(--radius)] border px-3 py-2 text-[var(--text-sm)]",
        config.box,
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
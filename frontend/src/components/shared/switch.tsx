"use client";

import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}

/** A labelled on/off control (role="switch") for account preferences. */
export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
  className,
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        "disabled:opacity-50",
        checked ? "bg-[var(--accent)]" : "bg-[var(--border-strong)]",
        focusRing,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "inline-block size-5 rounded-full bg-white shadow-[var(--shadow-xs)] transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
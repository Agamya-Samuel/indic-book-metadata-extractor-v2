import * as React from "react";
import { cn } from "@/lib/utils";

export type StepNumberVariant = "filled" | "outlined";

export interface StepNumberProps
  extends Omit<
    React.HTMLAttributes<HTMLSpanElement>,
    "color"
  > {
  /** The step number to display. */
  step: number;
  /** Filled (accent background) or outlined (neutral border). */
  variant?: StepNumberVariant;
}

/**
 * A small numbered circle used to mark steps in a sequence — pipeline steps,
 * numbered lists, workflow cards. Replaces the duplicated 4-instance pattern
 * across bulk-operations cards and the library empty-state number list.
 *
 * Two variants:
 * - `filled`: solid accent background, inverse text (bulk-operations step cards)
 * - `outlined`: neutral border + surface background, muted text (library step list)
 *
 * Always `aria-hidden` — the number is decorative context for a labeled parent.
 */
export const StepNumber = React.forwardRef<HTMLSpanElement, StepNumberProps>(
  ({ step, variant = "filled", className, ...rest }, ref) => {
    const base =
      "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold tabular-nums";
    const styles = {
      filled: "bg-[var(--accent)] text-[var(--text-inverse)]",
      outlined:
        "border border-[var(--border)] bg-[var(--surface)] font-semibold text-[var(--text-muted)]",
    };
    return (
      <span
        ref={ref}
        aria-hidden="true"
        className={cn(base, styles[variant], className)}
        {...rest}
      >
        {step}
      </span>
    );
  },
);
StepNumber.displayName = "StepNumber";

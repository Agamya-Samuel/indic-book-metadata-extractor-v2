import * as React from "react";
import { cn } from "@/lib/utils";

export interface ToolbarProps {
  children: React.ReactNode;
  className?: string;
  /** Pin the bar directly under the sticky navbar. */
  sticky?: boolean;
}

/**
 * A horizontal control bar for `workspace` layouts: page nav, view toggles,
 * apply actions. Purely presentational — the controls inside carry their own
 * semantics.
 */
export function Toolbar({ children, className, sticky = false }: ToolbarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2",
        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)]",
        "px-3 py-2 shadow-[var(--shadow-xs)]",
        sticky &&
          "sticky top-[var(--nav-height)] z-20 bg-[var(--surface)]/95 backdrop-blur",
        className,
      )}
    >
      {children}
    </div>
  );
}

export interface ToolbarGroupProps {
  children: React.ReactNode;
  className?: string;
  /** Push the group to the trailing edge of the bar. */
  align?: "start" | "end";
}

/** A cluster of related controls inside a Toolbar. */
export function ToolbarGroup({
  children,
  className,
  align = "start",
}: ToolbarGroupProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2",
        align === "end" && "ml-auto",
        className,
      )}
    >
      {children}
    </div>
  );
}

export default Toolbar;

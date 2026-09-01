import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A circular loading spinner. Uses the standard `animate-spin` Tailwind
 * utility, which drives the `spin` keyframe defined in globals.css.
 *
 * Sized via Tailwind classes — pass `className` with `h-*`/`w-*` to set
 * the diameter, and a color via `border-[var(--accent)]` etc.
 */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block rounded-full border-2 border-current border-r-transparent animate-spin",
        className,
      )}
    />
  );
}

"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/utils";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
  /** Render a description or right-aligned meta next to the title. */
  meta?: React.ReactNode;
}

export default function CollapsibleSection({
  title,
  count,
  defaultOpen = true,
  children,
  className,
  meta,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <section
      className={cn(
        "overflow-hidden rounded-[var(--radius)]",
        "border border-[var(--border)]",
        "bg-[var(--surface)]",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className={cn(
          "group flex w-full items-center justify-between gap-3 px-4 py-3 text-left",
          "hover:bg-[var(--surface-sunken)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-inset",
          "transition-colors duration-[var(--duration-fast)]",
        )}
      >
        <span className="flex items-center gap-2 min-w-0">
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className={cn(
              "size-3.5 shrink-0 text-[var(--text-muted)]",
              "transition-transform duration-[var(--duration-fast)] ease-[var(--ease-out)]",
              isOpen ? "rotate-90" : "rotate-0",
            )}
            fill="currentColor"
          >
            <path d="M7.05 4.05a.75.75 0 011.06 0l5 5a.75.75 0 010 1.06l-5 5a.75.75 0 11-1.06-1.06L11.44 10 7.05 5.61a.75.75 0 010-1.06z" />
          </svg>
          <span className="text-[var(--text-sm)] font-semibold text-[var(--text)] truncate">
            {title}
          </span>
          {count !== undefined && (
            <span className="text-[var(--text-xs)] tabular-nums text-[var(--text-muted)]">
              {count} {count === 1 ? "field" : "fields"}
            </span>
          )}
        </span>
        {meta && (
          <span className="shrink-0 text-[var(--text-xs)] text-[var(--text-muted)]">
            {meta}
          </span>
        )}
      </button>
      <div
        id={panelId}
        // The grid-template-rows 0fr → 1fr pattern animates the height of the
        // container smoothly without measuring the content. The inner div
        // has min-height: 0 + overflow: hidden so the children can be
        // clipped to a zero-height row, then fade in once the row opens.
        // `aria-hidden` mirrors `hidden` for assistive tech, but `hidden`
        // alone is not used — we want the height to animate, not snap.
        aria-hidden={!isOpen}
        className={cn(
          "grid transition-[grid-template-rows] duration-[var(--duration)] ease-[var(--ease-out)]",
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
        style={{
          transitionProperty: "grid-template-rows",
        }}
      >
        <div
          className={cn(
            "min-h-0 overflow-hidden border-t border-[var(--border)]",
            "transition-opacity duration-[var(--duration)] ease-[var(--ease-out)]",
            isOpen ? "opacity-100" : "opacity-0",
          )}
        >
          <div className="px-4 py-3">{children}</div>
        </div>
      </div>
    </section>
  );
}

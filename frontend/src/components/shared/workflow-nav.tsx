import * as React from "react";
import { LinkButton } from "@/components/shared/button";
import { cn } from "@/lib/utils";

const ArrowLeft = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="size-3.5" aria-hidden="true">
    <path
      fillRule="evenodd"
      d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06-.02z"
      clipRule="evenodd"
    />
  </svg>
);

const ArrowRight = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="size-3.5" aria-hidden="true">
    <path
      fillRule="evenodd"
      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
      clipRule="evenodd"
    />
  </svg>
);

export interface WorkflowNavLink {
  href: string;
  label: string;
}

export interface WorkflowNavProps {
  /** Previous stage, omitted on the first stage. */
  prev?: WorkflowNavLink;
  /** Next stage, omitted when the page's primary action is its own. */
  next?: WorkflowNavLink;
  /** Extra trailing actions rendered before the next link. */
  children?: React.ReactNode;
  className?: string;
}

/**
 * The one workflow navigation footer: previous stage on the left, extra actions
 * and the next stage on the right. Replaces the per-page prev/next inventions
 * so every stage ends the same way.
 */
export function WorkflowNav({ prev, next, children, className }: WorkflowNavProps) {
  return (
    <nav
      aria-label="Workflow navigation"
      className={cn(
        "mt-8 flex flex-wrap items-center justify-between gap-3",
        "border-t border-[var(--border)] pt-4",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {prev && (
          <LinkButton
            href={prev.href}
            variant="outline"
            size="sm"
            leftIcon={ArrowLeft}
          >
            {prev.label}
          </LinkButton>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
        {next && (
          <LinkButton href={next.href} size="sm" rightIcon={ArrowRight}>
            {next.label}
          </LinkButton>
        )}
      </div>
    </nav>
  );
}

export default WorkflowNav;
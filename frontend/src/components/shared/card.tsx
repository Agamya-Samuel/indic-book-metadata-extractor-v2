import * as React from "react";
import { cn } from "@/lib/utils";

/** Page-level container with consistent gutter. */
export function PageContainer({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-[var(--content-max)] px-4 sm:px-6 lg:px-8 py-6 sm:py-8",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Page header: eyebrow, title, description, actions. */
export interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  back?: React.ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  back,
}: PageHeaderProps) {
  return (
    <header className="mb-6 sm:mb-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0 flex-1">
          {back && <div className="mb-3">{back}</div>}
          {eyebrow && (
            <p className="text-[var(--text-xs)] font-medium uppercase tracking-wider text-[var(--accent-soft-text)] mb-2">
              {eyebrow}
            </p>
          )}
          <h1 className="text-[var(--text-2xl)] sm:text-[var(--text-3xl)] font-semibold tracking-tight text-[var(--text)] leading-tight">
            {title}
          </h1>
          {description && (
            <p className="mt-2 text-[var(--text-sm)] sm:text-[var(--text-base)] text-[var(--text-muted)] max-w-[var(--reading-max)]">
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}

/** A contained surface with optional header, body, footer. */
export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  /** Section title rendered in the card header. */
  title?: React.ReactNode;
  description?: React.ReactNode;
  /** Trailing element in the card header (e.g. a button, a count). */
  headerAction?: React.ReactNode;
  /** Hide the divider between body children — they handle their own. */
  divided?: boolean;
  /** Suppress the inner padding on the body. */
  flush?: boolean;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, title, description, headerAction, divided, flush, children, ...rest },
  ref,
) {
  const hasHeader = title || description || headerAction;
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]",
        "shadow-[var(--shadow-xs)]",
        "transition-shadow duration-[var(--duration-fast)] ease-[var(--ease-out)]",
        className,
      )}
      {...rest}
    >
      {hasHeader && (
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[var(--border)]">
          <div className="min-w-0 flex-1">
            {title && (
              <h2 className="text-[var(--text-sm)] font-semibold text-[var(--text)] truncate">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-0.5 text-[var(--text-xs)] text-[var(--text-muted)]">
                {description}
              </p>
            )}
          </div>
          {headerAction && <div className="shrink-0">{headerAction}</div>}
        </div>
      )}
      {divided ? (
        <div className="divide-y divide-[var(--border)]">
          {React.Children.map(children, (child) => (
            <div className={cn(flush ? "" : "px-5 py-3.5")}>{child}</div>
          ))}
        </div>
      ) : (
        <div className={cn(flush ? "" : "px-5 py-4")}>{children}</div>
      )}
    </div>
  );
});

/** Vertical stack with consistent rhythm. */
export function Stack({
  children,
  className,
  gap = 4,
}: {
  children: React.ReactNode;
  className?: string;
  gap?: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
}) {
  const gapClass = {
    1: "space-y-1",
    2: "space-y-2",
    3: "space-y-3",
    4: "space-y-4",
    5: "space-y-5",
    6: "space-y-6",
    7: "space-y-7",
    8: "space-y-8",
  }[gap];
  return <div className={cn(gapClass, className)}>{children}</div>;
}

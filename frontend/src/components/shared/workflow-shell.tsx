"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getBook,
  getAllBookCurrentStages,
  getAllBookJobs,
  getAllBookPages,
} from "@/lib/api";
import { deriveWorkflowState } from "@/lib/workflow-state";
import { StageRail, StageRailMobile } from "@/components/shared/stage-rail";
import { cn } from "@/lib/utils";

interface WorkflowShellProps {
  bookId: string;
  /**
   * Page content. Pages currently render the shell as a top bar; Phase 1
   * migrates them to pass children, at which point this becomes required.
   */
  children?: React.ReactNode;
  /** Heading above the desktop rail. */
  railLabel?: string;
  className?: string;
}

/**
 * Shared workflow chrome: a persistent stage rail on the left (sticky, 15rem)
 * wrapping the page content, with a sticky stage bar + sheet on narrow screens.
 *
 * Query keys are shared with the stage pages (`["book", id]`,
 * `["book", id, "pages"]`, `["book", id, "jobs"]`) so React Query dedupes the
 * requests instead of double-fetching.
 */
export default function WorkflowShell({
  bookId,
  children,
  railLabel = "Workflow",
  className,
}: WorkflowShellProps) {
  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    enabled: !!bookId,
    staleTime: 15_000,
  });

  const stagesQuery = useQuery({
    queryKey: ["book", bookId, "stages", "current", "all"],
    queryFn: () => getAllBookCurrentStages(bookId),
    enabled: !!bookId,
    staleTime: 5_000,
    retry: false,
  });

  const pagesQuery = useQuery({
    queryKey: ["book", bookId, "pages", "all"],
    queryFn: () => getAllBookPages(bookId),
    enabled: !!bookId,
    staleTime: 10_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["book", bookId, "jobs", "all"],
    queryFn: () => getAllBookJobs(bookId),
    enabled: !!bookId,
    staleTime: 2_000,
  });

  const state = deriveWorkflowState({
    book: bookQuery.data,
    stages: stagesQuery.data,
    pages: pagesQuery.data,
    jobs: jobsQuery.data,
  });

  return (
    <div className={cn("flex w-full items-stretch", className)}>
      <aside className="hidden w-60 shrink-0 border-r border-[var(--border)] bg-[var(--surface)] lg:block">
        <div className="sticky top-[var(--nav-height)] max-h-[calc(100dvh-var(--nav-height))] overflow-y-auto px-3 py-4">
          <p className="mb-2 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            {railLabel}
          </p>
          <StageRail
            steps={state.steps}
            currentStep={state.currentStep}
            processing={state.processing}
          />
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <StageRailMobile
          steps={state.steps}
          currentStep={state.currentStep}
          processing={state.processing}
        />
        {children}
      </div>
    </div>
  );
}
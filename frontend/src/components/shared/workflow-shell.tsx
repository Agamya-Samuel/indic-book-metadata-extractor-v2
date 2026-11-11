"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getBook,
  getBookCurrentStages,
  getBookJobs,
  getBookPages,
} from "@/lib/api";
import { deriveWorkflowState } from "@/lib/workflow-state";
import WorkflowStepper from "@/components/shared/workflow-stepper";

interface WorkflowShellProps {
  bookId: string;
  className?: string;
}

/**
 * Shared workflow chrome. Fetches the server truth (book, current stages,
 * pages, jobs) and renders a stepper driven by `deriveWorkflowState`.
 *
 * Query keys are shared with the stage pages (`["book", id]`,
 * `["book", id, "pages"]`, `["book", id, "jobs"]`) so React Query dedupes the
 * requests instead of double-fetching.
 */
export default function WorkflowShell({ bookId, className }: WorkflowShellProps) {
  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    enabled: !!bookId,
    staleTime: 15_000,
  });

  const stagesQuery = useQuery({
    queryKey: ["book", bookId, "stages", "current"],
    queryFn: () => getBookCurrentStages(bookId),
    enabled: !!bookId,
    staleTime: 5_000,
    retry: false,
  });

  const pagesQuery = useQuery({
    queryKey: ["book", bookId, "pages"],
    queryFn: () => getBookPages(bookId),
    enabled: !!bookId,
    staleTime: 10_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["book", bookId, "jobs"],
    queryFn: () => getBookJobs(bookId),
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
    <WorkflowStepper
      steps={state.steps}
      currentStep={state.currentStep}
      className={className}
    />
  );
}
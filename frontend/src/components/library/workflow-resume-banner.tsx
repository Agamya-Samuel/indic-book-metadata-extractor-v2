"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminJobs,
  runOcr,
  runExtraction,
  DEFAULT_EXTRACTION_CONFIG,
} from "@/lib/api";
import { getResumeTarget, type ResumeTarget } from "@/lib/workflow-resume";
import StatusBadge from "@/components/shared/status-badge";
import { Button, LinkButton } from "@/components/shared/button";
import { Progress } from "@/components/shared/empty-state";
import { cn } from "@/lib/utils";

interface Props {
  detail: { id: string; status: string };
}

const variantContainer: Record<
  ResumeTarget["variant"],
  string
> = {
  info: "border-[var(--info-500)]/30 bg-[var(--info-50)] dark:bg-[var(--info-900)]/15",
  success:
    "border-[var(--success-500)]/30 bg-[var(--success-50)] dark:bg-[var(--success-900)]/15",
  warning:
    "border-[var(--warning-500)]/30 bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/15",
  danger:
    "border-[var(--danger-500)]/30 bg-[var(--danger-50)] dark:bg-[var(--danger-900)]/15",
};

const variantHeadline: Record<ResumeTarget["variant"], string> = {
  info: "text-[var(--info-700)] dark:text-[var(--info-100)]",
  success: "text-[var(--success-700)] dark:text-[var(--success-100)]",
  warning: "text-[var(--warning-700)] dark:text-[var(--warning-100)]",
  danger: "text-[var(--danger-700)] dark:text-[var(--danger-100)]",
};

const variantProgress: Record<
  ResumeTarget["variant"],
  "accent" | "success" | "warning" | "danger"
> = {
  info: "accent",
  success: "success",
  warning: "warning",
  danger: "danger",
};

export default function WorkflowResumeBanner({ detail }: Props) {
  const qc = useQueryClient();

  const bookId = detail.id;

  // Pull all jobs (admin endpoint exposes them across all books; page_size 50
  // covers any reasonable book). We only need the most recent job of each
  // type, but fetching the first page keeps the call simple.
  const { data: jobsData } = useQuery({
    queryKey: ["library-resume-jobs", bookId],
    queryFn: () => getAdminJobs({ book_id: bookId, page_size: 50 }),
    enabled: detail.status !== "complete",
    staleTime: 5 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return false;
      }
      const items = q.state.data?.items ?? [];
      const live = items.some(
        (j) => j.status === "running" || j.status === "queued",
      );
      return live ? 3_000 : 15_000;
    },
  });

  const target = React.useMemo(
    () => getResumeTarget(detail, jobsData?.items ?? []),
    [detail, jobsData?.items],
  );

  const invalidate = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: ["book", bookId] });
    qc.invalidateQueries({ queryKey: ["library-resume-jobs", bookId] });
    qc.invalidateQueries({ queryKey: ["book", bookId, "jobs"] });
    qc.invalidateQueries({ queryKey: ["library"] });
  }, [qc, bookId]);

  const rerunOcr = useMutation({
    mutationFn: () => runOcr(bookId),
    onSuccess: () => {
      toast.success("OCR re-run queued");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  const rerunExt = useMutation({
    mutationFn: () => runExtraction(bookId, { ...DEFAULT_EXTRACTION_CONFIG }),
    onSuccess: () => {
      toast.success("Extraction re-run queued");
      invalidate();
    },
    onError: (err: unknown) => {
      toast.error(getErrorMessage(err));
    },
  });

  if (!target) return null;

  // Pull the live progress for whichever job type is currently relevant.
  const items = jobsData?.items ?? [];
  let liveProgress = null;
  if (!target.failureContext && target.showProgress) {
    const matchType =
      detail.status === "ocr_running"
        ? "ocr"
        : detail.status === "llm_running"
          ? "llm"
          : null;
    if (matchType) {
      liveProgress =
        items.find(
          (j) =>
            j.job_type === matchType &&
            (j.status === "running" ||
              j.status === "queued" ||
              j.status === "completed"),
        ) ?? null;
    }
  }

  const pending = rerunOcr.isPending || rerunExt.isPending;

  const onRerunClick = () => {
    if (!target.failureContext) return;
    if (target.failureContext.jobType === "llm") {
      rerunExt.mutate();
    } else {
      // ocr + preprocessing both go through the OCR pipeline
      rerunOcr.mutate();
    }
  };

  return (
    <section
      aria-label="Workflow status"
      className={cn(
        "rounded-[var(--radius-lg)] border px-4 sm:px-5 py-4 animate-fade-in",
        variantContainer[target.variant],
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              className={cn(
                "text-[var(--text-md)] font-semibold",
                variantHeadline[target.variant],
              )}
            >
              {target.headline}
            </h2>
            <StatusBadge
              status={
                detail.status === "ocr_running" || detail.status === "llm_running"
                  ? "running"
                  : detail.status === "complete"
                    ? "completed"
                    : detail.status === "ocr_complete"
                      ? "completed"
                      : "queued"
              }
            />
          </div>
          <p className="mt-1 text-[var(--text-sm)] text-[var(--text)]">
            {target.description}
          </p>

          {target.failureContext && (
            <pre
              className={cn(
                "mt-2 max-h-24 overflow-auto rounded-[var(--radius)]",
                "border border-[var(--danger-500)]/20 bg-[var(--surface)]/60",
                "px-3 py-2 text-[11px] font-mono whitespace-pre-wrap",
                "text-[var(--text-muted)]",
              )}
            >
              {target.failureContext.error}
            </pre>
          )}

          {liveProgress && (
            <div className="mt-3 max-w-md">
              <Progress
                value={liveProgress.progress * 100}
                tone={variantProgress[target.variant]}
              />
              <p className="mt-1 text-[var(--text-xs)] tabular-nums text-[var(--text-muted)]">
                {Math.round(liveProgress.progress * 100)}% complete
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {target.failureContext ? (
            <>
              <Button
                variant={target.variant === "danger" ? "danger" : "primary"}
                onClick={onRerunClick}
                loading={pending}
                disabled={pending}
              >
                {target.ctaLabel}
              </Button>
              <LinkButton href={target.href} variant="outline">
                View details
              </LinkButton>
            </>
          ) : (
            <LinkButton
              href={target.href}
              variant="primary"
            >
              {target.ctaLabel}
            </LinkButton>
          )}
        </div>
      </div>
    </section>
  );
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const r = (err as { response?: { data?: { detail?: unknown } } }).response;
    if (r?.data?.detail) {
      return typeof r.data.detail === "string"
        ? r.data.detail
        : JSON.stringify(r.data.detail);
    }
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
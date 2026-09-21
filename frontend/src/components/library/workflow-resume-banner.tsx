"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getBookCurrentStages,
  runOcr,
  runExtraction,
  DEFAULT_EXTRACTION_CONFIG,
} from "@/lib/api";
import { getResumeTarget, type ResumeTarget } from "@/lib/workflow-resume";
import { getErrorMessage } from "@/lib/error-handler";
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
  const { data: stagesData } = useQuery({
    queryKey: ["book", bookId, "stages", "current"],
    queryFn: () => getBookCurrentStages(bookId),
    enabled: detail.status !== "complete",
    staleTime: 5 * 1000,
    refetchInterval: (q) => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return false;
      }
      const items = q.state.data ?? [];
      const live = items.some(
        (s) => s.status === "processing" || s.status === "initiated",
      );
      return live ? 3_000 : 15_000;
    },
  });

  const target = React.useMemo(
    () => getResumeTarget(detail, stagesData ?? []),
    [detail, stagesData],
  );

  const resolvedHref = React.useMemo(() => {
    if (!target) return "";
    return typeof target.href === "function" ? target.href(bookId) : target.href;
  }, [target, bookId]);

  const invalidate = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: ["book", bookId] });
    qc.invalidateQueries({ queryKey: ["book", bookId, "stages"] });
    qc.invalidateQueries({ queryKey: ["book", bookId, "stages", "current"] });
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

  const pending = rerunOcr.isPending || rerunExt.isPending;

  const onRerunClick = () => {
    if (!target.failureContext) return;
    if (target.failureContext.stage === "llm_extraction") {
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
              <LinkButton href={resolvedHref} variant="outline">
                View details
              </LinkButton>
            </>
          ) : (
            <LinkButton
              href={resolvedHref}
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
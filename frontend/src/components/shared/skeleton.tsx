"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[var(--radius-sm)]",
        "bg-[var(--surface-sunken)]",
        "border border-[var(--border)]",
        className,
      )}
      aria-hidden="true"
    />
  );
}

export function SkeletonPageHeader() {
  return (
    <div className="space-y-2.5">
      <Skeleton className="h-7 w-64" />
      <Skeleton className="h-4 w-80" />
    </div>
  );
}

export function SkeletonFormField() {
  return (
    <div className="flex items-start gap-4 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
      <Skeleton className="mt-1 h-3.5 w-36 shrink-0" />
      <Skeleton className="h-8 w-full" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="space-y-2 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] px-5 py-4 shadow-[var(--shadow-xs)]"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16 rounded-full" />
            </div>
            <Skeleton className="h-3.5 w-20" />
          </div>
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonImage({
  aspectRatio = "3/4",
}: {
  aspectRatio?: string;
}) {
  return (
    <div
      className="w-full"
      style={{ aspectRatio }}
      aria-hidden="true"
    >
      <Skeleton className="h-full w-full" />
    </div>
  );
}

function WorkflowSkeletonShell({
  children,
  fullBleed = false,
}: {
  children: ReactNode;
  fullBleed?: boolean;
}) {
  return (
    <div
      className="flex min-h-[calc(100dvh-var(--nav-height))] w-full flex-1 items-stretch"
      role="status"
      aria-label="Loading page"
    >
      <aside className="hidden w-60 shrink-0 border-r border-[var(--border)] bg-[var(--surface)] lg:block">
        <div className="sticky top-[var(--nav-height)] px-3 py-4">
          <Skeleton className="mb-3 ml-2.5 h-3 w-20" />
          <div className="space-y-1.5">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="flex min-h-11 items-center gap-2.5 px-2.5">
                <Skeleton className="size-6 shrink-0 rounded-full" />
                <Skeleton className="h-3 flex-1" />
              </div>
            ))}
          </div>
        </div>
      </aside>
      <div
        className={cn(
          "min-w-0 flex-1",
          fullBleed && "h-[calc(100dvh-var(--nav-height))] overflow-hidden",
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function SkeletonCanvas() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-[500px] w-full" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

export function BookDetailSkeleton() {
  return (
    <WorkflowSkeletonShell>
      <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
        <SkeletonPageHeader />
        <div className="mt-8 space-y-4">
          <div className="space-y-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[var(--shadow-xs)]">
            <Skeleton className="h-5 w-40" />
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonFormField key={i} />
            ))}
          </div>
        </div>
      </div>
    </WorkflowSkeletonShell>
  );
}

export function WorkflowPageSkeleton() {
  return (
    <WorkflowSkeletonShell>
      <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
        <SkeletonPageHeader />
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-3">
            <Skeleton className="h-56 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
          <div className="space-y-4 lg:col-span-5">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <div className="space-y-4 lg:col-span-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </WorkflowSkeletonShell>
  );
}

export function OcrReviewSkeleton() {
  return (
    <WorkflowSkeletonShell fullBleed>
      <div className="flex h-full flex-col">
        <Skeleton className="h-14 w-full rounded-none border-x-0 border-t-0" />
        <div className="flex-1 p-4">
          <div className="flex h-full flex-col gap-4 lg:flex-row">
            <div className="lg:w-[60%]">
              <SkeletonCanvas />
            </div>
            <div className="space-y-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4 lg:w-[40%]">
              <Skeleton className="h-4 w-24" />
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-3 w-full" />
              ))}
            </div>
          </div>
        </div>
      </div>
    </WorkflowSkeletonShell>
  );
}

export function MetadataReviewSkeleton() {
  return (
    <WorkflowSkeletonShell>
      <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
        <SkeletonPageHeader />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonFormField key={i} />
          ))}
        </div>
      </div>
    </WorkflowSkeletonShell>
  );
}

export function SelectPagesSkeleton() {
  return (
    <WorkflowSkeletonShell>
      <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
        <SkeletonPageHeader />
        <div className="mt-8 space-y-6">
          <div className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[var(--shadow-xs)]">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-9 w-32" />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8">
            {Array.from({ length: 12 }).map((_, i) => (
              <SkeletonImage key={i} />
            ))}
          </div>
        </div>
      </div>
    </WorkflowSkeletonShell>
  );
}

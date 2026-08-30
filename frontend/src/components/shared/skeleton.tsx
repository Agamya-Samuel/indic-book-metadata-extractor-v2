"use client";

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

export function SkeletonCard() {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]",
        "shadow-[var(--shadow-xs)]",
      )}
    >
      <Skeleton className="aspect-[3/4] w-full rounded-none border-0" />
      <div className="space-y-2 p-3">
        <Skeleton className="h-3.5 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <div className="flex gap-2 pt-1">
          <Skeleton className="h-4 w-12 rounded-full" />
          <Skeleton className="h-4 w-16" />
        </div>
      </div>
    </div>
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

export function LibrarySkeleton() {
  return (
    <div
      className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
      role="status"
      aria-label="Loading library"
    >
      {Array.from({ length: 10 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function BookDetailSkeleton() {
  return (
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
  );
}

export function WorkflowPageSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
      <SkeletonPageHeader />
      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-2 lg:col-span-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
        <div className="lg:col-span-6">
          <SkeletonCanvas />
        </div>
        <div className="space-y-4 lg:col-span-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function OcrReviewSkeleton() {
  return (
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
  );
}

export function MetadataReviewSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
      <SkeletonPageHeader />
      <div className="mt-8 space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonFormField key={i} />
        ))}
      </div>
    </div>
  );
}

export function SelectPagesSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[var(--content-max)] px-4 py-8 sm:px-6 lg:px-8">
      <SkeletonPageHeader />
      <div className="mt-8 space-y-6">
        <div className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[var(--shadow-xs)]">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <SkeletonImage key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

"use client";

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse bg-gray-200 dark:bg-gray-700 rounded ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-gray-800 border rounded-lg overflow-hidden">
      <Skeleton className="aspect-[3/4] w-full" />
      <div className="p-3 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <div className="flex gap-2">
          <Skeleton className="h-4 w-12 rounded-full" />
          <Skeleton className="h-4 w-16" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonPageHeader() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-6 w-64" />
      <Skeleton className="h-4 w-48" />
    </div>
  );
}

export function SkeletonFormField() {
  return (
    <div className="flex items-start gap-3 px-3 py-2 rounded border border-gray-100 dark:border-gray-700">
      <Skeleton className="h-4 w-36 shrink-0 mt-1" />
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
          className="bg-white dark:bg-gray-800 shadow rounded-lg border-l-4 border-gray-200 dark:border-gray-600 px-5 py-4 space-y-2"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-24 rounded" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="h-4 w-20" />
          </div>
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonImage({ aspectRatio = "3/4" }: { aspectRatio?: string }) {
  return (
    <div className={`bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center`} style={{ aspectRatio }}>
      <svg className="w-8 h-8 text-gray-300 dark:text-gray-600" fill="currentColor" viewBox="0 0 24 24">
        <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" />
      </svg>
    </div>
  );
}

export function SkeletonCanvas() {
  return (
    <div className="space-y-2">
      <Skeleton className="w-full h-[500px] rounded" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

export function LibrarySkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {Array.from({ length: 10 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function BookDetailSkeleton() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <SkeletonPageHeader />
        </div>
      </div>
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-4 space-y-3">
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b px-4 py-3">
        <div className="max-w-screen-2xl mx-auto">
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
        <SkeletonPageHeader />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-2 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full rounded" />
            ))}
          </div>
          <div className="lg:col-span-6">
            <SkeletonCanvas />
          </div>
          <div className="lg:col-span-4 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function OcrReviewSkeleton() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      <div className="bg-white dark:bg-gray-800 border-b px-4 py-3">
        <div className="max-w-screen-2xl mx-auto">
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
      <div className="bg-white dark:bg-gray-800 border-b px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <SkeletonPageHeader />
          <Skeleton className="h-8 w-48" />
        </div>
      </div>
      <div className="flex-1 p-4">
        <div className="flex flex-col lg:flex-row gap-4 h-full">
          <div className="lg:w-[60%]">
            <SkeletonCanvas />
          </div>
          <div className="lg:w-[40%] bg-white dark:bg-gray-800 border-l rounded p-4 space-y-3">
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      <div className="bg-white dark:bg-gray-800 border-b px-4 py-3">
        <div className="max-w-screen-2xl mx-auto">
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
      <div className="bg-white dark:bg-gray-800 border-b px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <SkeletonPageHeader />
          <Skeleton className="h-8 w-48" />
        </div>
      </div>
      <div className="flex-1 max-w-screen-2xl mx-auto w-full p-6 space-y-6">
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonFormField key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function SelectPagesSkeleton() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="bg-white dark:bg-gray-800 border-b px-4 py-3">
        <div className="max-w-screen-2xl mx-auto">
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-6">
        <SkeletonPageHeader />
        <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6">
          <div className="flex items-center justify-between">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-8 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <SkeletonImage key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

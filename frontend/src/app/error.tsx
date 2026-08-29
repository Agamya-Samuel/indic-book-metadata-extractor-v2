"use client";

import { Button, LinkButton } from "@/components/shared/button";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useDocumentTitle("Something went wrong");

  return (
    <main className="flex min-h-[calc(100dvh-var(--nav-height))] items-center justify-center px-4">
      <div className="mx-auto w-full max-w-md text-center">
        <div
          aria-hidden="true"
          className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full border border-[var(--danger-500)]/30 bg-[var(--danger-50)] text-[var(--danger-600)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-500)]"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            className="size-6"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
        </div>
        <h1 className="text-[var(--text-2xl)] font-semibold tracking-tight text-[var(--text)]">
          Something went wrong
        </h1>
        <p className="mt-2 text-[var(--text-sm)] text-[var(--text-muted)]">
          An unexpected error occurred while loading this page. You can try again
          or return to the library.
        </p>
        {error.message && (
          <details className="mt-5 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)] p-3 text-left">
            <summary className="cursor-pointer text-[var(--text-xs)] font-medium text-[var(--text-muted)] hover:text-[var(--text)]">
              Show error details
            </summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[var(--text-xs)] font-mono text-[var(--danger-700)] dark:text-[var(--danger-300)]">
              {error.message}
            </pre>
          </details>
        )}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <Button type="button" onClick={reset}>
            Try again
          </Button>
          <LinkButton href="/" variant="outline">
            Go to library
          </LinkButton>
        </div>
      </div>
    </main>
  );
}

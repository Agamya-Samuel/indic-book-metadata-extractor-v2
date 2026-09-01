"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getBook, selectPages } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { PageContainer } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import { ErrorState, Progress } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";

const STORAGE_KEY = (bookId: string) => `book:${bookId}:pendingPages`;

function readPendingPagesRaw(bookId: string): { found: boolean; pages: number[] | null } {
  if (typeof window === "undefined") return { found: false, pages: null };
  const raw = sessionStorage.getItem(STORAGE_KEY(bookId));
  if (raw === null) return { found: false, pages: null };
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed) && parsed.length > 0 && parsed.every((n) => typeof n === "number")) {
      return { found: true, pages: parsed };
    }
    return { found: true, pages: null };
  } catch {
    return { found: true, pages: null };
  }
}

function subscribeNoop() {
  return () => {};
}

export default function ExtractingPagesPage() {
  useDocumentTitle("Extracting pages");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;

  useWorkflowHydration(bookId);
  const { currentStep, completedStep, setStep: setWorkflowStep, setCompletedStep } = useWorkflowStore();

  const { data: book, isLoading: isLoadingBook } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  // Subscribe to sessionStorage. The state machine is:
  //   { status: "ssr" }            — before mount on the client
  //   { status: "missing" }        — no pending pages in storage
  //   { status: "ready", pages }   — pages are present and valid
  // This avoids setState-in-effect and SSR hydration mismatches.
  const storageSnapshot = useSyncExternalStore(
    subscribeNoop,
    () => readPendingPagesRaw(bookId),
    () => ({ found: false, pages: null }) as { found: boolean; pages: number[] | null },
  );
  const storageState: { status: "ssr" | "missing" | "ready"; pages: number[] | null } =
    !storageSnapshot.found
      ? { status: "ssr", pages: null }
      : storageSnapshot.pages
        ? { status: "ready", pages: storageSnapshot.pages }
        : { status: "missing", pages: null };
  const pendingPages = storageState.status === "ready" ? storageState.pages : null;

  const selectPagesMutation = useMutation({
    mutationFn: (pages: number[]) => selectPages(bookId, pages),
    onSuccess: () => {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(STORAGE_KEY(bookId));
      }
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      queryClient.invalidateQueries({ queryKey: ["book", bookId, "pages"] });
      setWorkflowStep(3);
      setCompletedStep(3);
    },
  });

  useEffect(() => {
    if (
      pendingPages &&
      !selectPagesMutation.isPending &&
      !selectPagesMutation.isSuccess &&
      !selectPagesMutation.isError
    ) {
      selectPagesMutation.mutate(pendingPages);
    }
  }, [pendingPages, selectPagesMutation]);

  useEffect(() => {
    if (selectPagesMutation.isSuccess) {
      toast.success(`${pendingPages?.length ?? 0} pages extracted successfully`);
      const t = setTimeout(() => {
        router.push(`/books/${bookId}/preprocessing`);
      }, 500);
      return () => clearTimeout(t);
    }
  }, [selectPagesMutation.isSuccess, pendingPages, router, bookId]);

  if (isLoadingBook || storageState.status === "ssr") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--accent)]" />
      </div>
    );
  }

  if (!book) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState title="Book not found" />
      </div>
    );
  }

  if (storageState.status === "missing") {
    return (
      <div className="min-h-screen flex flex-col bg-[var(--background)]">
        <WorkflowStepper
          bookId={bookId}
          currentStep={currentStep < 2 ? 2 : currentStep}
          completedStep={completedStep}
        />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md mx-auto">
            <h2 className="text-[var(--text-xl)] font-semibold text-[var(--text)] mb-2">
              No pending pages
            </h2>
            <p className="text-[var(--text-muted)] text-[var(--text-sm)] mb-6">
              Please select the pages you want to process.
            </p>
            <LinkButton href={`/books/${bookId}/select-pages`} variant="primary">
              Go to Page Selection
            </LinkButton>
          </div>
        </div>
      </div>
    );
  }

  const pageCount = pendingPages?.length ?? 0;
  const isExtracting = selectPagesMutation.isPending || (!selectPagesMutation.isSuccess && !selectPagesMutation.isError);
  const isComplete = selectPagesMutation.isSuccess;
  const errorMessage = selectPagesMutation.error ? String(selectPagesMutation.error) : null;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--background)]">
      <WorkflowStepper
        bookId={bookId}
        currentStep={currentStep < 3 ? 3 : currentStep}
        completedStep={completedStep}
      />

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-md mx-auto">
          {isExtracting && (
            <>
              <div className="animate-pulse mb-6">
                <svg
                  className="w-16 h-16 mx-auto text-[var(--accent)]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                  />
                </svg>
              </div>
              <h2 className="text-[var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                Extracting page images
              </h2>
              <p className="text-[var(--text-muted)] text-[var(--text-sm)] mb-6">
                Rendering {pageCount} page{pageCount !== 1 ? "s" : ""} from{" "}
                <span className="font-medium">{book.title || book.filename}</span>
              </p>
              <div className="mb-4">
                <Progress value={50} />
              </div>
              <p className="text-[var(--text-xs)] text-[var(--text-muted)]">
                This may take a few seconds for large books.
              </p>
            </>
          )}

          {isComplete && (
            <>
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-[var(--success-600)] flex items-center justify-center animate-success-glow">
                  <svg
                    className="w-8 h-8 text-[var(--text-inverse)] animate-step-check"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              </div>
              <h2 className="text-[var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                Pages Extracted
              </h2>
              <p className="text-[var(--text-muted)] text-[var(--text-sm)] mb-6">
                {pageCount} page{pageCount !== 1 ? "s" : ""} ready for preprocessing.
                Redirecting to the next step.
              </p>
              <Button onClick={() => router.push(`/books/${bookId}/preprocessing`)}>
                Continue to Preprocessing
              </Button>
            </>
          )}

          {errorMessage && (
            <>
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-[var(--danger-600)] flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-[var(--text-inverse)]"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                    />
                  </svg>
                </div>
              </div>
              <h2 className="text-[var(--text-xl)] font-semibold text-[var(--text)] mb-2">
                Extraction Failed
              </h2>
              <div className="mb-6 text-left bg-[var(--surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-4">
                <pre className="text-[var(--text-xs)] text-[var(--danger-700)] dark:text-[var(--danger-100)] whitespace-pre-wrap font-mono">
                  {errorMessage}
                </pre>
              </div>
              <div className="flex gap-3 justify-center">
                <LinkButton
                  href={`/books/${bookId}/select-pages`}
                  variant="primary"
                >
                  Back to Page Selection
                </LinkButton>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="border-t border-[var(--border)] bg-[var(--surface)]">
        <PageContainer className="!py-4">
          <div className="flex items-center justify-between text-[var(--text-sm)] text-[var(--text-muted)]">
            <div className="flex items-center gap-4">
              <span>{book.title || book.filename}</span>
              <span className="text-[var(--border-strong)]">&bull;</span>
              <span>{getLanguageName(book.language)}</span>
              <span className="text-[var(--border-strong)]">&bull;</span>
              <span>{pageCount} pages</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 bg-[var(--accent-soft)] text-[var(--accent-soft-text)] rounded-[var(--radius)] text-[var(--text-xs)] font-medium">
                Extracting Pages
              </span>
            </div>
          </div>
        </PageContainer>
      </div>
    </div>
  );
}

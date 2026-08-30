"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getBook, selectPages, getThumbnailUrl } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useBookStore } from "@/stores/book-store";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { SelectPagesSkeleton } from "@/components/shared/skeleton";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
import { Button, LinkButton } from "@/components/shared/button";
import Image from "next/image";
import { Banner, EmptyState, ErrorState } from "@/components/shared/empty-state";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn } from "@/lib/utils";

export default function SelectPagesPage() {
  useDocumentTitle("Select pages");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const bookId = params.bookId as string;
  const redirectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useWorkflowHydration(bookId);
  const { currentStep, completedStep, setBookId: setWorkflowBookId, setStep: setWorkflowStep, setCompletedStep } = useWorkflowStore();

  const {
    data: book,
    isLoading: isLoadingBook,
    error: bookError,
  } = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const {
    selectedPages,
    togglePageSelection,
    selectPages: selectPagesInStore,
    clearSelection,
    selectAllPages,
  } = useBookStore();

  const selectPagesMutation = useMutation({
    mutationFn: (pages: number[]) => selectPages(bookId, pages),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book", bookId] });
      setShowSuccessBanner(true);
      toast.success(`${selectedCount} pages selected successfully`);
      setWorkflowStep(3);
      setCompletedStep(3);
      clearSelection();
      redirectTimeoutRef.current = setTimeout(() => {
        router.push(`/books/${bookId}/preprocessing`);
      }, 1500);
    },
  });

  const ITEMS_PER_PAGE = 12;
  const [showSuccessBanner, setShowSuccessBanner] = useState(false);
  const [imagesLoaded, setImagesLoaded] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    clearSelection();
  }, [clearSelection]);

  useEffect(() => {
    return () => {
      if (redirectTimeoutRef.current) {
        clearTimeout(redirectTimeoutRef.current);
      }
    };
  }, []);

  if (isLoadingBook) {
    return <SelectPagesSkeleton />;
  }

  if (bookError || !book) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <ErrorState title="Error loading book" />
      </div>
    );
  }

  if (!book.total_pages) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <p className="text-[var(--text-muted)]">Book has no pages</p>
      </div>
    );
  }

  const totalPages = book.total_pages;
  const selectedCount = selectedPages.size;
  const totalPaginationPages = Math.ceil(totalPages / ITEMS_PER_PAGE);
  const startPage = (currentPage - 1) * ITEMS_PER_PAGE + 1;
  const endPage = Math.min(currentPage * ITEMS_PER_PAGE, totalPages);
  const visiblePageNumbers = Array.from(
    { length: endPage - startPage + 1 },
    (_, i) => startPage + i
  );

  const handleSelectAll = () => {
    selectAllPages(totalPages);
  };

  const handleDeselectAll = () => {
    clearSelection();
  };

  const handleSelectFront10 = () => {
    const frontPages = Array.from({ length: Math.min(10, totalPages) }, (_, i) => i + 1);
    selectPagesInStore(frontPages);
  };

  const handleSelectBack5 = () => {
    const backPages = Array.from({ length: Math.min(5, totalPages) }, (_, i) => totalPages - 4 + i);
    selectPagesInStore(backPages);
  };

  const handleConfirm = () => {
    if (selectedCount === 0) return;

    const pages = Array.from(selectedPages).sort((a, b) => a - b);
    selectPagesMutation.mutate(pages);
  };

  const handleImageLoad = (pageNumber: number) => {
    setImagesLoaded((prev) => new Set([...prev, pageNumber]));
  };

  const handleImageError = (pageNumber: number) => {
    setImagesLoaded((prev) => new Set([...prev, pageNumber]));
  };

  if (book && !useWorkflowStore.getState().bookId) {
    setWorkflowBookId(bookId);
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 2 ? 2 : currentStep} completedStep={completedStep} />

      {showSuccessBanner && (
        <div
          className="border-b border-[var(--success-500)]/30 bg-[var(--success-50)] dark:bg-[var(--success-900)]/15 animate-fade-in"
          role="status"
          aria-live="polite"
        >
          <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
            <Banner tone="success" className="flex items-center justify-between bg-transparent border-0 p-0">
              <div className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className="flex size-7 items-center justify-center rounded-full bg-[var(--success-600)] text-[var(--text-inverse)] animate-success-glow"
                >
                  <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="size-3.5 animate-step-check"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.296a1 1 0 010 1.408l-7.997 8a1 1 0 01-1.408 0l-3.999-4a1 1 0 011.408-1.408L8 12.59l7.296-7.294a1 1 0 011.408 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                <div>
                  <p className="text-[var(--text-sm)] font-semibold text-[var(--success-700)] dark:text-[var(--success-100)]">
                    {selectedCount} pages selected
                  </p>
                  <p className="text-[var(--text-xs)] text-[var(--success-700)]/80 dark:text-[var(--success-100)]/80">
                    Ready to preprocess. The next step runs image cleanup before OCR.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <LinkButton
                  href={`/books/${bookId}/preprocessing`}
                  variant="primary"
                  size="sm"
                >
                  Continue to preprocessing
                </LinkButton>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSuccessBanner(false)}
                >
                  Dismiss
                </Button>
              </div>
            </Banner>
          </div>
        </div>
      )}

      <PageContainer>
        <PageHeader
          eyebrow={getLanguageName(book.language)}
          title={book.title || book.filename}
          description={`Total pages: ${totalPages}`}
        />

        <Card className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleSelectAll}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={handleDeselectAll}>
                Deselect All
              </Button>
              <Button variant="outline" size="sm" onClick={handleSelectFront10}>
                Select Front 10
              </Button>
              <Button variant="outline" size="sm" onClick={handleSelectBack5}>
                Select Back 5
              </Button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-[var(--text-sm)] font-medium text-[var(--text-muted)]">
                Selected {selectedCount} / {totalPages} pages
              </span>
              <Button
                onClick={handleConfirm}
                disabled={selectedCount === 0 || selectPagesMutation.isPending}
                loading={selectPagesMutation.isPending}
              >
                {selectPagesMutation.isPending
                  ? "Processing..."
                  : `Confirm ${selectedCount} pages`}
              </Button>
            </div>
          </div>
        </Card>

        {visiblePageNumbers.length === 0 ? (
          <EmptyState
            title="No pages to select"
            description="There are no pages in the visible range."
          />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {visiblePageNumbers.map((pageNumber) => {
              const isSelected = selectedPages.has(pageNumber);
              const isLoaded = imagesLoaded.has(pageNumber);

              return (
                <button
                  key={pageNumber}
                  type="button"
                  onClick={() => togglePageSelection(pageNumber)}
                  aria-pressed={isSelected}
                  className={cn(
                    "relative bg-[var(--surface)] rounded-[var(--radius-lg)] overflow-hidden cursor-pointer transition-all hover:shadow-[var(--shadow-md)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
                    isSelected
                      ? "border-2 border-[var(--accent)] shadow-[var(--shadow-md)]"
                      : "border-2 border-[var(--border)]"
                  )}
                >
                  <div className="aspect-[3/4] relative bg-[var(--surface-sunken)]">
                    <Image
                      src={getThumbnailUrl(bookId, pageNumber)}
                      alt={`Page ${pageNumber}`}
                      fill
                      sizes="(min-width: 1280px) 16vw, (min-width: 768px) 25vw, 50vw"
                      className="object-cover"
                      onLoad={() => handleImageLoad(pageNumber)}
                      onError={() => handleImageError(pageNumber)}
                      unoptimized
                    />
                    {!isLoaded && (
                      <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface-sunken)]">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--text-subtle)]"></div>
                      </div>
                    )}
                  </div>

                  <div className="absolute top-2 right-2">
                    <div
                      className={cn(
                        "w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors",
                        isSelected
                          ? "bg-[var(--accent)] border-[var(--accent)]"
                          : "bg-[var(--surface)] border-[var(--border-strong)]"
                      )}
                    >
                      {isSelected && (
                        <svg className="w-4 h-4 text-[var(--text-inverse)]" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </div>
                  </div>

                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--neutral-1000)]/80 to-transparent p-2">
                    <p className="text-[var(--text-inverse)] text-[var(--text-xs)] font-medium text-center">
                      Page {pageNumber}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {totalPaginationPages > 1 && (
          <nav
            aria-label="Pagination"
            className="mt-6 flex items-center justify-center gap-2"
          >
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(1)}
              disabled={currentPage === 1}
              aria-label="First page"
            >
              ««
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              aria-label="Previous page"
            >
              «
            </Button>
            {Array.from({ length: totalPaginationPages }, (_, i) => i + 1)
              .filter((p) => {
                if (totalPaginationPages <= 7) return true;
                if (p === 1 || p === totalPaginationPages) return true;
                return Math.abs(p - currentPage) <= 1;
              })
              .reduce<(number | "...")[]>((acc, p, i, arr) => {
                if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push("...");
                acc.push(p);
                return acc;
              }, [])
              .map((item, i) =>
                item === "..." ? (
                  <span
                    key={`ellipsis-${i}`}
                    className="px-2 text-[var(--text-muted)]"
                    aria-hidden="true"
                  >
                    …
                  </span>
                ) : (
                  <Button
                    key={item}
                    variant={currentPage === item ? "primary" : "outline"}
                    size="sm"
                    onClick={() => setCurrentPage(item as number)}
                    aria-label={`Page ${item}`}
                    aria-current={currentPage === item ? "page" : undefined}
                  >
                    {item}
                  </Button>
                )
              )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPaginationPages, p + 1))}
              disabled={currentPage === totalPaginationPages}
              aria-label="Next page"
            >
              »
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(totalPaginationPages)}
              disabled={currentPage === totalPaginationPages}
              aria-label="Last page"
            >
              »»
            </Button>
          </nav>
        )}
      </PageContainer>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getBook, selectPages, getThumbnailUrl } from "@/lib/api";
import { getLanguageName } from "@/lib/utils";
import { useBookStore } from "@/stores/book-store";
import { toast } from "sonner";
import WorkflowStepper from "@/components/shared/workflow-stepper";
import { useWorkflowStore, useWorkflowHydration } from "@/stores/workflow-store";
import { SelectPagesSkeleton } from "@/components/shared/skeleton";

export default function SelectPagesPage() {
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

  const [showSuccessBanner, setShowSuccessBanner] = useState(false);
  const [imagesLoaded, setImagesLoaded] = useState<Set<number>>(new Set());

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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-red-600 dark:text-red-400">Error loading book</div>
      </div>
    );
  }

  if (!book.total_pages) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600 dark:text-gray-400">Book has no pages</div>
      </div>
    );
  }

  const totalPages = book.total_pages;
  const selectedCount = selectedPages.size;

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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <WorkflowStepper bookId={bookId} currentStep={currentStep < 2 ? 2 : currentStep} completedStep={completedStep} />

      {showSuccessBanner && (
        <div className="bg-green-50 dark:bg-green-900/20 border-b border-green-200 dark:border-green-800">
          <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <svg
                  className="h-6 w-6 text-green-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="ml-3 text-sm font-medium text-green-800 dark:text-green-300">
                  Successfully selected {selectedCount} pages
                </p>
              </div>
              <div className="flex items-center">
                <Link
                  href={`/books/${bookId}/preprocessing`}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/40 hover:bg-green-200 dark:hover:bg-green-900/60 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  Continue to Preprocessing
                </Link>
                <button
                  type="button"
                  onClick={() => setShowSuccessBanner(false)}
                  className="ml-4 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/40 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            {book.title || book.filename}
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Language: {getLanguageName(book.language)} • Total pages: {totalPages}
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div className="flex items-center space-x-4">
              <button
                type="button"
                onClick={handleSelectAll}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Select All
              </button>
              <button
                type="button"
                onClick={handleDeselectAll}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Deselect All
              </button>
              <button
                type="button"
                onClick={handleSelectFront10}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Select Front 10
              </button>
              <button
                type="button"
                onClick={handleSelectBack5}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Select Back 5
              </button>
            </div>

            <div className="flex items-center space-x-4">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Selected {selectedCount} / {totalPages} pages
              </span>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={selectedCount === 0 || selectPagesMutation.isPending}
                className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {selectPagesMutation.isPending ? "Processing..." : `Confirm ${selectedCount} pages`}
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNumber) => {
            const isSelected = selectedPages.has(pageNumber);
            const isLoaded = imagesLoaded.has(pageNumber);

            return (
              <div
                key={pageNumber}
                className={`relative bg-white dark:bg-gray-800 border-2 rounded-lg overflow-hidden cursor-pointer transition-all hover:shadow-lg ${
                  isSelected ? "border-blue-500 shadow-lg" : "border-gray-200 dark:border-gray-600"
                }`}
                onClick={() => togglePageSelection(pageNumber)}
              >
                <div className="aspect-[3/4] relative bg-gray-100 dark:bg-gray-700">
                  <img
                    src={getThumbnailUrl(bookId, pageNumber)}
                    alt={`Page ${pageNumber}`}
                    className="w-full h-full object-cover"
                    onLoad={() => handleImageLoad(pageNumber)}
                    onError={() => handleImageError(pageNumber)}
                    loading="lazy"
                    decoding="async"
                  />
                  {!isLoaded && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-700">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-400"></div>
                    </div>
                  )}
                </div>

                <div className="absolute top-2 right-2">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                      isSelected
                        ? "bg-blue-500 border-blue-500"
                        : "bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600"
                    }`}
                  >
                    {isSelected && (
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </div>
                </div>

                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                  <p className="text-white text-xs font-medium text-center">
                    Page {pageNumber}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

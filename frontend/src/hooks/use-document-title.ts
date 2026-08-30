"use client";

import { useEffect } from "react";

/**
 * Set the document title. Restores the previous title on unmount so
 * client-side navigation between routes leaves the title correct.
 *
 * The Next.js metadata.title.template from the root layout will still be
 * applied to the SSR document; this hook is for client-only overrides.
 */
export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);
}

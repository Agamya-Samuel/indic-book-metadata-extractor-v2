"use client";

import { useEffect } from "react";

export const DEFAULT_UNSAVED_MESSAGE =
  "You have unsaved changes. Leave without saving?";

/** Synchronous confirm used for programmatic navigation. */
export function confirmDiscard(message: string = DEFAULT_UNSAVED_MESSAGE): boolean {
  if (typeof window === "undefined") return true;
  return window.confirm(message);
}

/**
 * Guards against losing unsaved work:
 * - `beforeunload` for hard navigations / refresh / tab close,
 * - capture-phase click interception for in-app `<Link>` navigation.
 *
 * Returns nothing; call `confirmDiscard()` yourself before `router.push()`
 * when you navigate programmatically.
 */
export function useUnsavedChanges(
  active: boolean,
  message: string = DEFAULT_UNSAVED_MESSAGE,
): void {
  useEffect(() => {
    if (!active) return;

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active, message]);

  useEffect(() => {
    if (!active) return;

    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented) return;
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const target = event.target as Element | null;
      const anchor = target?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (
        !href ||
        href.startsWith("#") ||
        anchor.target === "_blank" ||
        anchor.hasAttribute("download")
      ) {
        return;
      }
      if (confirmDiscard(message)) return;
      event.preventDefault();
      event.stopPropagation();
    };

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [active, message]);
}

"use client";

import * as React from "react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { cn } from "@/lib/utils";
import { focusRing, focusRingInset } from "@/lib/focus-ring";

const WIDTH_KEY = "metadata-review:pane-width";
const COLLAPSED_KEY = "metadata-review:pane-collapsed";
const DEFAULT_PANE_WIDTH = 420;
const MIN_PANE_WIDTH = 320;
const MAX_PANE_WIDTH = 640;
const STEP = 16;
const LARGE_STEP = 64;

function clampPaneWidth(value: number, maxWidth: number): number {
  if (!Number.isFinite(value)) return DEFAULT_PANE_WIDTH;
  return Math.min(maxWidth, Math.max(MIN_PANE_WIDTH, Math.round(value)));
}

function readStoredWidth(): number {
  if (typeof window === "undefined") return DEFAULT_PANE_WIDTH;
  const stored = window.localStorage.getItem(WIDTH_KEY);
  if (!stored) return DEFAULT_PANE_WIDTH;
  const parsed = Number.parseInt(stored, 10);
  return Number.isNaN(parsed) ? DEFAULT_PANE_WIDTH : parsed;
}

function readStoredCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(COLLAPSED_KEY) === "true";
}

function subscribeLayout(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

const getServerWidth = () => DEFAULT_PANE_WIDTH;
const getServerCollapsed = () => false;

export interface ReviewWorkspacePaneControls {
  /** Whether the pane is rendered in the desktop split or the mobile sheet. */
  variant: "split" | "sheet";
  /** Collapses the desktop pane into its slim tab. */
  onCollapse: () => void;
  /** Closes the sub-`lg` bottom sheet after an insert. */
  onRequestCloseSheet: () => void;
}

interface ReviewWorkspaceProps {
  /** The metadata form column. */
  children: React.ReactNode;
  /** Renders the pane body; called once for the split and once for the sheet. */
  renderPane: (controls: ReviewWorkspacePaneControls) => React.ReactNode;
  /** Controlled state for the sub-`lg` sheet. */
  sheetOpen: boolean;
  onSheetOpenChange: (open: boolean) => void;
}

export function ReviewWorkspace({
  children,
  renderPane,
  sheetOpen,
  onSheetOpenChange,
}: ReviewWorkspaceProps) {
  const paneId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const dragState = useRef<{ startX: number; startWidth: number } | null>(null);

  const storedWidth = useSyncExternalStore(
    subscribeLayout,
    readStoredWidth,
    getServerWidth,
  );
  const storedCollapsed = useSyncExternalStore(
    subscribeLayout,
    readStoredCollapsed,
    getServerCollapsed,
  );
  const [widthOverride, setWidthOverride] = useState<number | null>(null);
  const [collapsedOverride, setCollapsedOverride] = useState<boolean | null>(
    null,
  );
  const [containerWidth, setContainerWidth] = useState(0);
  const widthRef = useRef(DEFAULT_PANE_WIDTH);

  const width = widthOverride ?? storedWidth;
  const collapsed = collapsedOverride ?? storedCollapsed;

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(() =>
      setContainerWidth(element.getBoundingClientRect().width),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (sheetOpen && !dialog.open) {
      dialog.showModal();
    } else if (!sheetOpen && dialog.open) {
      dialog.close();
    }
  }, [sheetOpen]);

  const maxWidth =
    containerWidth > 0
      ? Math.max(
          MIN_PANE_WIDTH,
          Math.min(MAX_PANE_WIDTH, Math.floor(containerWidth / 2)),
        )
      : MAX_PANE_WIDTH;
  const effectiveWidth = clampPaneWidth(width, maxWidth);

  const commitWidth = useCallback(
    (next: number, persist = true) => {
      const clamped = clampPaneWidth(next, maxWidth);
      widthRef.current = clamped;
      setWidthOverride(clamped);
      if (persist) window.localStorage.setItem(WIDTH_KEY, String(clamped));
    },
    [maxWidth],
  );

  const setCollapsedState = useCallback((next: boolean) => {
    setCollapsedOverride(next);
    window.localStorage.setItem(COLLAPSED_KEY, String(next));
  }, []);

  const handleSeparatorKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const step = event.shiftKey ? LARGE_STEP : STEP;
      switch (event.key) {
        case "ArrowLeft":
          event.preventDefault();
          commitWidth(effectiveWidth + step);
          break;
        case "ArrowRight":
          event.preventDefault();
          commitWidth(effectiveWidth - step);
          break;
        case "Home":
          event.preventDefault();
          commitWidth(MIN_PANE_WIDTH);
          break;
        case "End":
          event.preventDefault();
          commitWidth(maxWidth);
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          setCollapsedState(true);
          break;
      }
    },
    [commitWidth, effectiveWidth, maxWidth, setCollapsedState],
  );

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      dragState.current = {
        startX: event.clientX,
        startWidth: effectiveWidth,
      };
      widthRef.current = effectiveWidth;
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [effectiveWidth],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drag = dragState.current;
      if (!drag) return;
      commitWidth(drag.startWidth - (event.clientX - drag.startX), false);
    },
    [commitWidth],
  );

  const endDrag = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragState.current) return;
    dragState.current = null;
    window.localStorage.setItem(WIDTH_KEY, String(widthRef.current));
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  const paneControls = {
    onCollapse: () => setCollapsedState(true),
    onRequestCloseSheet: () => onSheetOpenChange(false),
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        "lg:grid lg:items-start",
        collapsed
          ? "lg:grid-cols-[minmax(0,1fr)_2.5rem]"
          : "lg:grid-cols-[minmax(0,1fr)_0.375rem_var(--review-pane-width)]",
      )}
      style={
        {
          "--review-pane-width": `${effectiveWidth}px`,
        } as React.CSSProperties
      }
    >
      <div className="min-w-0 pb-28">{children}</div>

      {!collapsed && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-valuemin={MIN_PANE_WIDTH}
          aria-valuemax={maxWidth}
          aria-valuenow={effectiveWidth}
          aria-controls={paneId}
          aria-label="Resize OCR reference"
          tabIndex={0}
          onKeyDown={handleSeparatorKeyDown}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onDoubleClick={() => commitWidth(DEFAULT_PANE_WIDTH)}
          className={cn(
            "sticky top-[calc(var(--nav-height)+1rem)] hidden h-[calc(100dvh-var(--nav-height)-2rem)] lg:flex",
            "cursor-col-resize touch-none select-none items-center justify-center",
            "rounded-full hover:bg-[var(--accent-soft)]",
            focusRingInset,
          )}
        >
          <span
            aria-hidden="true"
            className="h-10 w-1 rounded-full bg-[var(--border-strong)]"
          />
        </div>
      )}

      {collapsed && (
        <div className="hidden lg:block">
          <button
            type="button"
            onClick={() => setCollapsedState(false)}
            aria-label="Expand OCR reference"
            className={cn(
              "sticky top-[calc(var(--nav-height)+1rem)] flex h-40 w-10 items-center justify-center",
              "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)]",
              "text-[length:var(--text-xs)] font-medium text-[var(--text-muted)]",
              "hover:text-[var(--text)]",
              focusRing,
            )}
          >
            <span className="[writing-mode:vertical-rl]">OCR</span>
          </button>
        </div>
      )}

      {!collapsed && (
        <div
          id={paneId}
          className="sticky top-[calc(var(--nav-height)+1rem)] hidden h-[calc(100dvh-var(--nav-height)-2rem)] min-h-0 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] lg:block"
        >
          {renderPane({ ...paneControls, variant: "split" })}
        </div>
      )}

      <dialog
        ref={dialogRef}
        onClose={() => onSheetOpenChange(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) dialogRef.current?.close();
        }}
        className={cn(
          "fixed inset-x-0 bottom-0 top-auto m-0 h-[85dvh] max-h-[85dvh] w-full max-w-none",
          "rounded-t-[var(--radius-lg)] border-t border-[var(--border)] bg-[var(--surface)] p-0",
          "backdrop:bg-[var(--neutral-1000)]/50",
          "lg:hidden",
        )}
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-4 py-2">
            <span className="text-[length:var(--text-sm)] font-semibold text-[var(--text)]">
              OCR reference
            </span>
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className={cn(
                "rounded-[var(--radius)] px-2 py-1 text-[length:var(--text-sm)] text-[var(--text-muted)]",
                "hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]",
                focusRing,
              )}
            >
              Close
            </button>
          </div>
          <div className="min-h-0 flex-1">
            {renderPane({ ...paneControls, variant: "sheet" })}
          </div>
        </div>
      </dialog>
    </div>
  );
}

export default ReviewWorkspace;

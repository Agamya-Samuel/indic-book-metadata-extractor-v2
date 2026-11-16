"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { getPagePreviewUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/shared/button";
import { Chip } from "@/components/shared/chip";
import { Spinner } from "@/components/shared/spinner";

interface PageViewerProps {
  bookId: string;
  pageNumber: number;
  totalPages: number;
  token?: string | null;
  isSelected: boolean;
  onToggleSelect: () => void;
  onNavigate: (delta: -1 | 1) => void;
  onClose: () => void;
}

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

function clampZoom(value: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(value * 100) / 100));
}

export default function PageViewer({
  bookId,
  pageNumber,
  totalPages,
  token,
  isSelected,
  onToggleSelect,
  onNavigate,
  onClose,
}: PageViewerProps) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();

  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (!el.open) el.showModal();
    closeRef.current?.focus();
    return () => {
      if (el.open) el.close();
    };
  }, []);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const isDark = document.documentElement.classList.contains("dark");
    el.style.backgroundColor = isDark ? "var(--neutral-900)" : "var(--surface)";
    el.style.color = isDark ? "var(--neutral-50)" : "var(--text)";
    el.style.borderColor = isDark ? "var(--neutral-800)" : "var(--border)";
    el.style.colorScheme = isDark ? "dark" : "light";
  }, []);

  const zoomBy = useCallback((delta: number) => {
    setZoom((current) => clampZoom(current + delta));
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        zoomBy(ZOOM_STEP);
      } else if (event.key === "-" || event.key === "_") {
        event.preventDefault();
        zoomBy(-ZOOM_STEP);
      } else if (event.key === "0") {
        event.preventDefault();
        setZoom(1);
      } else if (event.key === "ArrowLeft" && pageNumber > 1) {
        event.preventDefault();
        onNavigate(-1);
      } else if (event.key === "ArrowRight" && pageNumber < totalPages) {
        event.preventDefault();
        onNavigate(1);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNavigate, pageNumber, totalPages, zoomBy]);

  const src = `${getPagePreviewUrl(bookId, pageNumber, token)}&retry=${retryKey}`;

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
      className="m-auto h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] max-w-6xl overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/70"
    >
      <div className="flex h-full flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <h2 id={titleId} className="text-[length:var(--text-sm)] font-semibold">
              Page {pageNumber}
              <span className="ml-1 font-normal text-[var(--text-muted)]">
                of {totalPages}
              </span>
            </h2>
            <Chip tone={isSelected ? "accent" : "neutral"} dot>
              {isSelected ? "Selected" : "Not selected"}
            </Chip>
          </div>

          <div className="flex flex-wrap items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              aria-label="Zoom out"
              onClick={() => zoomBy(-ZOOM_STEP)}
              disabled={zoom <= MIN_ZOOM}
            >
              −
            </Button>
            <span
              className="min-w-12 text-center text-[length:var(--text-xs)] tabular-nums text-[var(--text-muted)]"
              aria-live="polite"
            >
              {Math.round(zoom * 100)}%
            </span>
            <Button
              variant="outline"
              size="sm"
              aria-label="Zoom in"
              onClick={() => zoomBy(ZOOM_STEP)}
              disabled={zoom >= MAX_ZOOM}
            >
              +
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setZoom(1)}>
              Reset
            </Button>
            <Button
              variant={isSelected ? "outline" : "primary"}
              size="sm"
              onClick={onToggleSelect}
            >
              {isSelected ? "Deselect page" : "Select page"}
            </Button>
            <Button
              ref={closeRef}
              variant="ghost"
              size="sm"
              aria-label="Close page viewer"
              onClick={onClose}
            >
              ✕
            </Button>
          </div>
        </header>

        <div className="relative flex-1 overflow-auto bg-[var(--surface-sunken)]">
          {loading && !failed && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <Spinner className="h-10 w-10 border-2 text-[var(--accent-text)]" />
            </div>
          )}

          {failed ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                Could not load page {pageNumber}.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFailed(false);
                  setLoading(true);
                  setRetryKey((key) => key + 1);
                }}
              >
                Try again
              </Button>
            </div>
          ) : (
            <div
              className={cn(
                "p-4",
                zoom === 1 && "flex h-full items-center justify-center",
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={`${pageNumber}-${retryKey}`}
                src={src}
                alt={`Page ${pageNumber} of ${totalPages}`}
                className={cn(
                  "mx-auto block h-auto rounded-[var(--radius)] bg-white shadow-[var(--shadow-sm)]",
                  zoom === 1
                    ? "max-h-full max-w-full object-contain"
                    : "max-w-none",
                )}
                style={zoom === 1 ? undefined : { width: `${zoom * 100}%` }}
                onLoad={() => setLoading(false)}
                onError={() => {
                  setLoading(false);
                  setFailed(true);
                }}
                draggable={false}
              />
            </div>
          )}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-[var(--border)] px-4 py-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onNavigate(-1)}
            disabled={pageNumber <= 1}
          >
            ← Previous
          </Button>
          <p className="hidden text-[length:var(--text-xs)] text-[var(--text-subtle)] sm:block">
            + / − zoom · 0 reset · ← / → change page · Esc close
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onNavigate(1)}
            disabled={pageNumber >= totalPages}
          >
            Next →
          </Button>
        </footer>
      </div>
    </dialog>
  );
}

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/shared/button";
import { useUnsavedChanges } from "@/hooks/use-unsaved-changes";

interface SaveBarProps {
  /** Number of changed fields/items; drives the dirty count copy. */
  dirtyCount?: number;
  onSave: () => void | Promise<void>;
  onDiscard?: () => void;
  saving?: boolean;
  saveLabel?: string;
  discardLabel?: string;
  disabled?: boolean;
  /** Render even when there is nothing to save (for persistent actions). */
  alwaysVisible?: boolean;
  /** Extra actions rendered on the right, e.g. "Mark review complete". */
  extraActions?: React.ReactNode;
  /** Left-aligned custom content; replaces the default dirty-count text. */
  children?: React.ReactNode;
  className?: string;
}

/**
 * Sticky bottom action bar for explicit-save surfaces. Owns the
 * unsaved-changes guard while it is dirty.
 */
export function SaveBar({
  dirtyCount = 0,
  onSave,
  onDiscard,
  saving = false,
  saveLabel = "Save changes",
  discardLabel = "Discard",
  disabled = false,
  alwaysVisible = false,
  extraActions,
  children,
  className,
}: SaveBarProps) {
  const dirty = dirtyCount > 0;
  useUnsavedChanges(dirty);

  if (!dirty && !alwaysVisible) return null;

  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)]",
        "bg-[var(--surface)]/95 backdrop-blur",
        "pb-[env(safe-area-inset-bottom)]",
        className,
      )}
      role="region"
      aria-label="Save changes"
    >
      <div className="mx-auto flex max-w-[var(--content-max)] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="min-w-0 text-[length:var(--text-sm)] text-[var(--text-muted)]">
          {children ??
            (dirty ? (
              <span aria-live="polite">
                {dirtyCount} unsaved {dirtyCount === 1 ? "change" : "changes"}
              </span>
            ) : (
              <span aria-live="polite">All changes saved</span>
            ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {onDiscard && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDiscard}
              disabled={saving || !dirty}
            >
              {discardLabel}
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => void onSave()}
            loading={saving}
            disabled={disabled || (!dirty && !alwaysVisible)}
          >
            {saveLabel}
          </Button>
          {extraActions}
        </div>
      </div>
    </div>
  );
}

export default SaveBar;

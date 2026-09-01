"use client";

import * as React from "react";
import { Button } from "@/components/shared/button";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /**
   * If provided, the user must type this exact string (case-insensitive)
   * into the confirmation field before the confirm button is enabled.
   */
  requireTyped?: string;
  variant?: "danger" | "warning";
  loading?: boolean;
}

/**
 * A minimal modal for destructive actions. Built on the native <dialog> element
 * to avoid adding any new dependencies.
 *
 * The typed-confirmation field is uncontrolled: validity is checked at click
 * time by reading the input's current value, and the field is keyed on `open`
 * via a prop so that it remounts and clears itself when the dialog opens.
 */
export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  requireTyped,
  variant = "danger",
  loading = false,
}: ConfirmDialogProps) {
  const ref = React.useRef<HTMLDialogElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  const handleConfirm = async () => {
    if (loading) return;
    if (requireTyped) {
      const typed = (inputRef.current?.value ?? "").trim().toLowerCase();
      if (typed !== requireTyped.trim().toLowerCase()) return;
    }
    await onConfirm();
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !loading) onClose();
      }}
      className="m-auto w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/40 dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]"
    >
       <div className="px-6 pt-5 pb-2">
         <h2 className="text-[var(--text-md)] font-semibold text-[var(--text)] text-left">
          {title}
        </h2>
        {description && (
          <div className="mt-2 text-[var(--text-sm)] text-[var(--text-muted)]">
            {description}
          </div>
        )}
      </div>

      {requireTyped && (
        <div className="px-6 pt-3">
          <label className="block text-[var(--text-xs)] font-medium text-[var(--text-muted)] mb-1.5">
            Type <span className="font-mono text-[var(--text)]">{requireTyped}</span> to confirm
          </label>
          {/* The key prop on the input causes it to remount whenever the dialog
              opens (open flips false→true), which clears its value. */}
          <input
            key={open ? "open" : "closed"}
            ref={inputRef}
            type="text"
            defaultValue=""
            disabled={loading}
            autoFocus
            className="block w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-subtle)] px-3 h-10 text-base sm:text-[var(--text-sm)] focus:outline-none focus:border-[var(--accent-ring)] focus:ring-2 focus:ring-[var(--accent-ring)]/30 dark:bg-[var(--neutral-800)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-700)]"
          />
        </div>
      )}

      <div className="flex justify-end gap-2 px-6 pt-4 pb-5">
        <Button variant="outline" onClick={onClose} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          variant={variant === "danger" ? "danger" : "primary"}
          onClick={handleConfirm}
          disabled={loading}
          loading={loading}
        >
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
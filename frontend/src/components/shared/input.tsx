"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const fieldBase =
  "block w-full rounded-[var(--radius)] " +
  "border border-[var(--border)] bg-[var(--surface)] " +
  "text-[var(--text)] placeholder:text-[var(--text-subtle)] " +
  // Mobile-first: 1rem (16px) on narrow screens to prevent iOS Safari
  // auto-zoom on focus. Drop to 14px on sm+ where the viewport can absorb it.
  "px-3 text-base sm:text-[var(--text-sm)] " +
  "transition-[border-color,box-shadow,background-color] " +
  "duration-[var(--duration-fast)] " +
  "hover:border-[var(--border-strong)] " +
  "focus:outline-none focus:border-[var(--accent-ring)] " +
  "focus:ring-2 focus:ring-[var(--accent-ring)]/30 " +
  "disabled:opacity-50 disabled:cursor-not-allowed " +
  "aria-[invalid=true]:border-[var(--danger-500)] " +
  "aria-[invalid=true]:focus:ring-[var(--danger-500)]/30 " +
  "dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(fieldBase, "h-10", className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  ),
);
Input.displayName = "Input";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid, ...rest }, ref) => (
    <textarea
      ref={ref}
      className={cn(fieldBase, "min-h-24 py-2.5 leading-relaxed", className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  ),
);
Textarea.displayName = "Textarea";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, invalid, children, ...rest }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          fieldBase,
          "h-10 pr-9 appearance-none cursor-pointer",
          className,
        )}
        aria-invalid={invalid || undefined}
        {...rest}
      >
        {children}
      </select>
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 size-4 text-[var(--text-muted)]"
        viewBox="0 0 20 20"
        fill="none"
      >
        <path
          d="M5 8l5 5 5-5"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  ),
);
Select.displayName = "Select";

/**
 * Form field wrapper: label + control + optional hint/error.
 *
 * Pass a single React element as `children` (e.g. <Input />, <Select />, or
 * a render-prop function). The field will inject the correct
 * `aria-describedby` and `aria-invalid` on the control so screen readers
 * announce the hint and the error alongside the field's value.
 *
 * Example:
 *   <Field label="Email" required htmlFor="email" hint="We never share it.">
 *     <Input id="email" type="email" />
 *   </Field>
 */
export interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  htmlFor?: string;
  /**
   * A single input/select/textarea element, OR a function that receives
   * the id and aria attributes to apply to the control.
   */
  children:
    | React.ReactElement
    | ((ids: {
        id?: string;
        "aria-describedby"?: string;
        "aria-invalid"?: boolean;
      }) => React.ReactElement);
  className?: string;
  trailing?: React.ReactNode;
}

export function Field({
  label,
  hint,
  error,
  required,
  htmlFor,
  children,
  className,
  trailing,
}: FieldProps) {
  const hintId = htmlFor ? `${htmlFor}-hint` : undefined;
  const errorId = htmlFor ? `${htmlFor}-error` : undefined;
  const describedBy = error ? errorId : hint ? hintId : undefined;
  const invalid = Boolean(error);

  const renderedChild = (() => {
    if (typeof children === "function") {
      return children({
        id: htmlFor,
        "aria-describedby": describedBy,
        "aria-invalid": invalid,
      });
    }
    if (!React.isValidElement(children)) return children;
    const child = children as React.ReactElement<Record<string, unknown>>;
    const childProps = child.props as {
      id?: string;
      "aria-describedby"?: string;
      "aria-invalid"?: boolean;
    };
    return React.cloneElement(child, {
      id: htmlFor ?? childProps.id,
      "aria-describedby": describedBy ?? childProps["aria-describedby"],
      "aria-invalid": invalid || childProps["aria-invalid"],
    });
  })();

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label
          htmlFor={htmlFor}
          className="text-[var(--text-sm)] font-medium text-[var(--text)] inline-flex items-center gap-1"
        >
          {label}
          {required && (
            <span aria-hidden="true" className="text-[var(--danger-500)]">
              *
            </span>
          )}
        </label>
        {trailing && (
          <div className="text-[var(--text-xs)] text-[var(--text-muted)]">
            {trailing}
          </div>
        )}
      </div>
      {renderedChild}
      {error ? (
        <p
          id={errorId}
          role="alert"
          className="text-[var(--text-xs)] text-[var(--danger-600)] dark:text-[var(--danger-500)]"
        >
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="text-[var(--text-xs)] text-[var(--text-muted)]">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

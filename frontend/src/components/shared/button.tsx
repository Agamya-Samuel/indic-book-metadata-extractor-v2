"use client";

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "link";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 font-medium " +
  "rounded-[var(--radius)] select-none whitespace-nowrap " +
  "transition-[background-color,border-color,color,box-shadow,transform] " +
  "duration-[var(--duration-fast)] ease-[var(--ease-out)] " +
  "active:translate-y-px " +
  "disabled:opacity-50 disabled:pointer-events-none " +
  "focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 " +
  "focus-visible:ring-offset-[var(--background)]";

const variants: Record<Variant, string> = {
  primary:
    "bg-[var(--accent)] " +
    "hover:bg-[var(--accent-hover)] active:bg-[var(--accent-active)] " +
    "shadow-[var(--shadow-xs)]",
  secondary:
    "bg-[var(--surface-raised)] text-[var(--btn-text)] " +
    "border border-[var(--border)] " +
    "hover:bg-[var(--surface-sunken)] active:bg-[var(--surface-sunken)]",
  outline:
    "bg-transparent text-[var(--btn-text)] " +
    "border border-[var(--border)] " +
    "hover:bg-[var(--surface-sunken)] hover:border-[var(--border-strong)] " +
    "active:bg-[var(--surface-sunken)]",
  ghost:
    "bg-transparent text-[var(--btn-text)] " +
    "hover:bg-[var(--surface-sunken)] active:bg-[var(--surface-sunken)]",
  danger:
    "bg-[var(--danger-600)] " +
    "hover:bg-[var(--danger-700)] active:bg-[var(--danger-900)] " +
    "shadow-[var(--shadow-xs)]",
  link:
    "bg-transparent text-[var(--accent)] underline-offset-4 " +
    "hover:underline px-0 h-auto rounded-none",
};

const sizes: Record<Size, string> = {
  sm: "min-h-11 min-w-11 h-8 px-3 text-[var(--text-sm)]",
  md: "min-h-11 min-w-11 h-10 px-4 text-[var(--text-sm)]",
  lg: "min-h-12 min-w-12 h-12 px-6 text-[var(--text-base)]",
};

/** Returns the className for a button — used by both <Button> and <LinkButton>. */
export function buttonClasses(
  variant: Variant = "primary",
  size: Size = "md",
  className?: string,
) {
  return cn(base, variants[variant], sizes[size], className);
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      leftIcon,
      rightIcon,
      className,
      children,
      disabled,
      type = "button",
      ...rest
    },
    ref,
  ) => {
    const colorStyle =
      variant === "primary" || variant === "danger"
        ? ({ color: "#fff" } as React.CSSProperties)
        : undefined;

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        style={colorStyle}
        className={buttonClasses(variant, size, className)}
        data-variant={variant}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <span
            className="inline-block size-3.5 rounded-full border-2 border-current border-r-transparent animate-spin"
            aria-hidden="true"
          />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        {children && <span className="truncate">{children}</span>}
        {!loading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  },
);
Button.displayName = "Button";

/** A button-styled Next.js <Link>. */
export interface LinkButtonProps
  extends Omit<React.ComponentProps<typeof Link>, "className"> {
  variant?: Variant;
  size?: Size;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

export function LinkButton({
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  className,
  children,
  ...rest
}: LinkButtonProps) {
  const colorStyle =
    variant === "primary" || variant === "danger"
      ? ({ color: "#fff" } as React.CSSProperties)
      : undefined;

  return (
    <Link data-variant={variant} style={colorStyle} className={buttonClasses(variant, size, className)} {...rest}>
      {leftIcon && <span className="shrink-0">{leftIcon}</span>}
      {children && <span className="truncate">{children}</span>}
      {rightIcon && <span className="shrink-0">{rightIcon}</span>}
    </Link>
  );
}

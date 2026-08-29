"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useTheme } from "./theme-provider";

const navLinks = [
  { href: "/library", label: "Library", shortLabel: "Library" },
  {
    href: "/bulk-operations",
    label: "Bulk operations",
    shortLabel: "Bulk",
  },
];

export default function AppNavbar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md supports-[backdrop-filter]:bg-[var(--background)]/70 [padding-left:max(1rem,env(safe-area-inset-left))] [padding-right:max(1rem,env(safe-area-inset-right))]">
      <div className="mx-auto flex h-14 w-full max-w-[var(--content-max)] items-center justify-between gap-3 sm:gap-4">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)] rounded-[var(--radius-sm)]"
          aria-label="Indic Book Metadata Extractor — home"
        >
          <span aria-hidden="true" className="brand-mark">
            ಇ
          </span>
          <span className="flex flex-col leading-tight min-w-0">
            <span className="text-[var(--text-sm)] font-semibold tracking-tight text-[var(--text)] truncate">
              Indic Books
            </span>
            {/* The product subline only fits from sm+; on narrow phones the
                wordmark alone identifies the product, and the aria-label on
                the parent Link keeps the full name in the accessibility tree. */}
            <span className="hidden sm:inline text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">
              Metadata Extractor
            </span>
          </span>
        </Link>

        <nav className="flex shrink-0 items-center gap-0.5 sm:gap-1" aria-label="Primary">
          {navLinks.map((link) => {
            const active =
              pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-11 items-center px-2.5 sm:px-3 py-1.5 text-[var(--text-sm)] font-medium rounded-[var(--radius)]",
                  "transition-colors duration-[var(--duration-fast)]",
                  active
                    ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                )}
              >
                <span className="sm:hidden">{link.shortLabel}</span>
                <span className="hidden sm:inline">{link.label}</span>
              </Link>
            );
          })}

          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className={cn(
              "ml-1 inline-flex size-9 items-center justify-center rounded-[var(--radius)]",
              "text-[var(--text-muted)] hover:text-[var(--text)]",
              "hover:bg-[var(--surface-sunken)]",
              "transition-colors duration-[var(--duration-fast)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
            )}
          >
            {theme === "dark" ? (
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="size-4"
                aria-hidden="true"
              >
                <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm5.66 2.34a1 1 0 010 1.41l-.7.7a1 1 0 11-1.42-1.4l.71-.71a1 1 0 011.41 0zM18 9a1 1 0 110 2h-1a1 1 0 110-2h1zM10 6a4 4 0 100 8 4 4 0 000-8zM3 9a1 1 0 100 2H2a1 1 0 100-2h1zm1.93-3.66a1 1 0 011.41 0l.71.71a1 1 0 11-1.41 1.41l-.71-.7a1 1 0 010-1.42zM10 16a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm-5.07-.66a1 1 0 011.41 0l.71.71a1 1 0 11-1.41 1.41l-.71-.7a1 1 0 010-1.42zm10.14 0a1 1 0 011.41 1.42l-.7.7a1 1 0 11-1.42-1.4l.71-.72z" />
              </svg>
            ) : (
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="size-4"
                aria-hidden="true"
              >
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            )}
          </button>
        </nav>
      </div>
    </header>
  );
}

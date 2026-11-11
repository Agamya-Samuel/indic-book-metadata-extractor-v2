"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";

const LINKS = [
  { href: "/admin", label: "Operations", exact: true },
  { href: "/admin/books", label: "Books" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/users", label: "Users" },
];

export function AdminNavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="space-y-1">
      {LINKS.map((link) => {
        const active = link.exact
          ? pathname === link.href
          : pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <li key={link.href}>
            <Link
              href={link.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-10 items-center rounded-[var(--radius)] px-3 py-2",
                "text-[var(--text-sm)] font-medium transition-colors",
                focusRing,
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]",
              )}
            >
              {link.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Mobile-only admin navigation: a compact bar with a drawer. The desktop
 * sidebar is rendered by `admin/layout.tsx` using `AdminNavLinks`.
 */
export default function AdminNav() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    panelRef.current?.querySelector<HTMLElement>("a")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="lg:hidden">
      <div className="sticky top-[var(--nav-height)] z-30 border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="flex items-center justify-between px-4 py-2">
          <span className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
            Admin
          </span>
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open admin navigation"
            aria-expanded={open}
            className={cn(
              "inline-flex size-10 items-center justify-center rounded-[var(--radius)]",
              "hover:bg-[var(--surface-sunken)]",
              focusRing,
            )}
          >
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50"
          role="dialog"
          aria-modal="true"
          aria-label="Admin navigation"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            ref={panelRef}
            className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-lg)]"
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="text-[var(--text-sm)] font-semibold text-[var(--text)]">
                Admin
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close admin navigation"
                className={cn(
                  "inline-flex size-9 items-center justify-center rounded-[var(--radius)]",
                  "hover:bg-[var(--surface-sunken)]",
                  focusRing,
                )}
              >
                <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            <AdminNavLinks onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
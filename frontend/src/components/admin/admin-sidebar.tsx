"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/admin", label: "Dashboard", exact: true },
  { href: "/admin/books", label: "Books" },
  { href: "/admin/jobs", label: "Jobs" },
];

export default function AdminSidebar({
  className,
}: {
  className?: string;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Admin sections"
      className={cn(
        "flex gap-1 overflow-x-auto border-b border-[var(--border)] bg-[var(--surface-sunken)]/40",
        className,
      )}
    >
      {links.map((link) => {
        const active = link.exact
          ? pathname === link.href
          : pathname === link.href || pathname.startsWith(`${link.href}/`);

        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex min-h-11 items-center px-3 sm:px-4 py-2 text-[var(--text-sm)] font-medium",
              "border-b-2 -mb-px transition-colors duration-[var(--duration-fast)]",
              "whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)] rounded-t-[var(--radius-sm)]",
              active
                ? "border-[var(--accent)] text-[var(--text)] bg-[var(--surface)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface)]/60",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
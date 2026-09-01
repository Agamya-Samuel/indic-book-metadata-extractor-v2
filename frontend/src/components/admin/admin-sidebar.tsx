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
        "border-b border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <div className="mx-auto w-full max-w-[var(--content-max)] px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <p className="hidden sm:block text-[var(--text-xs)] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Admin
          </p>
          <ul className="flex gap-1 overflow-x-auto">
            {links.map((link) => {
              const active = link.exact
                ? pathname === link.href
                : pathname === link.href || pathname.startsWith(`${link.href}/`);

              return (
                <li key={link.href} className="shrink-0">
                  <Link
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex min-h-11 items-center gap-2 px-3 sm:px-4 py-3 text-[var(--text-sm)] font-medium",
                      "border-b-2 -mb-px transition-colors duration-[var(--duration-fast)]",
                      "whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)] rounded-t-[var(--radius-sm)]",
                      active
                        ? "border-[var(--accent)] text-[var(--text)]"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border-strong)]",
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="size-1.5 rounded-full bg-[var(--accent)]"
                      />
                    )}
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </nav>
  );
}
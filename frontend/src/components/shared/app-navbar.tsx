"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import { getPendingUserCount } from "@/lib/api";
import { useTheme } from "./theme-provider";
import { useAuth } from "@/components/auth/auth-provider";
import { NotificationBell } from "@/components/notifications/notification-bell";

const navLinks = [
  {
    href: "/dashboard",
    label: "Dashboard",
    shortLabel: "Home",
    scope: "auth",
  },
  { href: "/upload", label: "Upload", shortLabel: "Upload", scope: "auth" },
  {
    href: "/admin/bulk",
    label: "Bulk operations",
    shortLabel: "Bulk",
    scope: "admin",
  },
  { href: "/admin", label: "Admin", shortLabel: "Admin", scope: "admin" },
] as const;

export default function AppNavbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const { user, loading, isAuthenticated, isAdmin, isApproved, logout } =
    useAuth();

  const { data: pendingCount = 0 } = useQuery({
    queryKey: ["admin-pending-count"],
    queryFn: getPendingUserCount,
    enabled: isAdmin,
    staleTime: 60 * 1000,
  });

  const visibleLinks = navLinks.filter((link) => {
    if (link.scope === "admin") return isAdmin;
    if (link.scope === "auth") return isAuthenticated && isApproved;
    return true;
  });

  // The account menu is a native <details>, which stays open until its summary
  // is clicked again — close it the way the notifications panel closes.
  const accountRef = useRef<HTMLDetailsElement>(null);
  const accountSummaryRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const closeOnOutside = (event: MouseEvent) => {
      const el = accountRef.current;
      if (el?.open && !el.contains(event.target as Node)) el.open = false;
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      const el = accountRef.current;
      if (event.key === "Escape" && el?.open) {
        el.open = false;
        accountSummaryRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  const closeAccountMenu = () => {
    if (accountRef.current) accountRef.current.open = false;
  };

  const handleLogout = async () => {
    closeAccountMenu();
    await logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md supports-[backdrop-filter]:bg-[var(--background)]/70 [padding-left:max(1rem,env(safe-area-inset-left))] [padding-right:max(1rem,env(safe-area-inset-right))]">
      <div className="mx-auto flex h-14 w-full max-w-[var(--content-max)] items-center justify-between gap-3 sm:gap-4">
        <Link
          href="/"
          className={cn(
            "group flex shrink-0 items-center gap-2.5 rounded-[var(--radius-sm)]",
            focusRing,
          )}
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

        {/* The link group may scroll on very narrow phones; the utilities to the
            right (bell, account, theme) stay pinned. */}
        <nav
          className="flex min-w-0 items-center gap-0.5 overflow-x-auto sm:gap-1"
          aria-label="Primary"
        >
          {visibleLinks.map((link) => {
            const active =
              pathname === link.href || pathname.startsWith(`${link.href}/`);
            const badge =
              link.href === "/admin" && pendingCount > 0 ? pendingCount : 0;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                aria-label={
                  badge > 0
                    ? `${link.label}, ${badge} pending approval${badge !== 1 ? "s" : ""}`
                    : undefined
                }
                className={cn(
                  "inline-flex min-h-11 items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-[var(--text-sm)] font-medium rounded-[var(--radius)]",
                  "transition-colors duration-[var(--duration-fast)]",
                  active
                    ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                  focusRing,
                )}
              >
                <span className="sm:hidden">{link.shortLabel}</span>
                <span className="hidden sm:inline">{link.label}</span>
                {badge > 0 && (
                  <span
                    aria-hidden="true"
                    className="inline-flex min-w-5 items-center justify-center rounded-full bg-[var(--accent)] px-1.5 text-[10px] font-semibold leading-5 text-white"
                  >
                    {badge > 99 ? "99+" : badge}
                  </span>
                )}
              </Link>
            );
          })}

          {!loading && !isAuthenticated && (
            <div className="ml-1 flex items-center gap-1">
              <Link
                href="/login"
                className={cn(
                  "inline-flex min-h-11 items-center px-2.5 sm:px-3 py-1.5 text-[var(--text-sm)] font-medium rounded-[var(--radius)]",
                  "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                  focusRing,
                )}
              >
                Log in
              </Link>
              <Link
                href="/register"
                className={cn(
                  "hidden sm:inline-flex min-h-11 items-center px-2.5 sm:px-3 py-1.5 text-[var(--text-sm)] font-medium rounded-[var(--radius)]",
                  "text-[var(--accent-text)] hover:bg-[var(--accent-soft)]",
                  focusRing,
                )}
              >
                Register
              </Link>
            </div>
          )}

          {isAuthenticated && isApproved && <NotificationBell />}

          {isAuthenticated && user && (
            <details ref={accountRef} className="relative ml-1">
              <summary
                ref={accountSummaryRef}
                className={cn(
                  "flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-[var(--radius)] px-2.5 py-1.5",
                  "text-[var(--text-sm)] font-medium text-[var(--text-muted)]",
                  "hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]",
                  focusRing,
                )}
                aria-label="Account menu"
              >
                <span
                  aria-hidden="true"
                  className="flex size-6 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[11px] font-semibold text-[var(--accent-soft-text)]"
                >
                  {user.display_name.slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden max-w-[8rem] truncate sm:inline">
                  {user.display_name}
                </span>
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                  className="size-3.5"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </summary>
              {/* Anchored to the trigger from sm+; on phones it spans the
                  viewport width so it cannot hang off the screen edge. */}
              <div
                className={cn(
                  "fixed inset-x-3 top-[calc(var(--nav-height)+0.5rem)] z-50 max-h-[70vh] overflow-y-auto",
                  "rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]",
                  "sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:max-h-none sm:w-60 sm:overflow-hidden",
                )}
              >
                <div className="border-b border-[var(--border)] px-4 py-3">
                  <p className="truncate text-[var(--text-sm)] font-semibold text-[var(--text)]">
                    {user.display_name}
                  </p>
                  <p className="truncate text-[var(--text-xs)] text-[var(--text-muted)]">
                    {user.email}
                  </p>
                  {isAdmin && (
                    <p className="mt-1 text-[10px] font-medium uppercase tracking-wider text-[var(--accent-text)]">
                      Administrator
                    </p>
                  )}
                </div>
                {isApproved && (
                  <Link
                    href="/dashboard"
                    onClick={closeAccountMenu}
                    className={cn(
                      "block px-4 py-2.5 text-[var(--text-sm)] text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                      focusRing,
                    )}
                  >
                    Dashboard
                  </Link>
                )}
                <button
                  type="button"
                  onClick={handleLogout}
                  className={cn(
                    "block w-full px-4 py-2.5 text-left text-[var(--text-sm)] text-[var(--text)] hover:bg-[var(--surface-sunken)]",
                    focusRing,
                  )}
                >
                  Log out
                </button>
              </div>
            </details>
          )}

          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className={cn(
              "ml-1 inline-flex size-9 items-center justify-center rounded-[var(--radius)]",
              "text-[var(--text-muted)] hover:text-[var(--text)]",
              "hover:bg-[var(--surface-sunken)]",
              "transition-colors duration-[var(--duration-fast)]",
              focusRing,
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

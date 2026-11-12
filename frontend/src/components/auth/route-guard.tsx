"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Spinner } from "@/components/shared/spinner";
import { useAuth } from "./auth-provider";

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
];

const ADMIN_PATHS = ["/admin"];

// Exact-match admin pages. `/library` itself is admin-only, but
// `/library/<bookId>` is owner-or-admin (the backend enforces it), so it must
// stay reachable for a regular owner opening their own book.
const ADMIN_EXACT_PATHS = ["/library"];

const PENDING_PATH = "/pending-approval";

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function isPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PATHS.some((path) => matchesPrefix(pathname, path));
}

function isAdminPath(pathname: string): boolean {
  if (ADMIN_EXACT_PATHS.includes(pathname)) return true;
  return ADMIN_PATHS.some((path) => matchesPrefix(pathname, path));
}

function FullPageSpinner() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner className="size-8 text-[var(--accent)]" />
      <span className="sr-only">Loading session</span>
    </div>
  );
}

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, isAdmin, isApproved } = useAuth();

  const publicPath = isPublicPath(pathname);
  const adminPath = isAdminPath(pathname);
  const pendingPath = pathname === PENDING_PATH;

  useEffect(() => {
    if (loading) return;
    if (!user && !publicPath) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
      return;
    }
    // Unapproved accounts (pending or rejected) can only reach the holding
    // screen; every application route redirects there.
    if (user && !isApproved && !pendingPath) {
      router.replace(PENDING_PATH);
      return;
    }
    if (user && isApproved && pendingPath) {
      router.replace("/dashboard");
      return;
    }
    if (user && adminPath && !isAdmin) {
      router.replace("/dashboard");
    }
  }, [
    loading,
    user,
    publicPath,
    adminPath,
    pendingPath,
    isApproved,
    isAdmin,
    pathname,
    router,
  ]);

  if (loading) return <FullPageSpinner />;
  if (!user && !publicPath) return <FullPageSpinner />;
  if (user && !isApproved && !pendingPath) return <FullPageSpinner />;
  if (user && isApproved && pendingPath) return <FullPageSpinner />;
  if (user && adminPath && !isAdmin) return <FullPageSpinner />;

  return <>{children}</>;
}

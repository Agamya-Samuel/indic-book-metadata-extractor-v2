"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Spinner } from "@/components/shared/spinner";
import { useAuth } from "./auth-provider";

const PUBLIC_PATHS = [
  "/library",
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
];

const ADMIN_PATHS = ["/admin", "/bulk-operations"];

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function isPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PATHS.some((path) => matchesPrefix(pathname, path));
}

function isAdminPath(pathname: string): boolean {
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
  const { user, loading, isAdmin } = useAuth();

  const publicPath = isPublicPath(pathname);
  const adminPath = isAdminPath(pathname);

  useEffect(() => {
    if (loading) return;
    if (!user && !publicPath) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
      return;
    }
    if (user && adminPath && !isAdmin) {
      router.replace("/dashboard");
    }
  }, [loading, user, publicPath, adminPath, isAdmin, pathname, router]);

  if (loading) return <FullPageSpinner />;
  if (!user && !publicPath) return <FullPageSpinner />;
  if (user && adminPath && !isAdmin) return <FullPageSpinner />;

  return <>{children}</>;
}

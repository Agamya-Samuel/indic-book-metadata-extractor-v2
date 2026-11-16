"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getPublicStatus, type MaintenanceStatus } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { Card } from "@/components/shared/card";
import { Button } from "@/components/shared/button";

const AUTH_PATHS = [
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
];

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function MaintenanceScreen({
  status,
  onRetry,
}: {
  status: MaintenanceStatus;
  onRetry: () => void;
}) {
  const { isAuthenticated } = useAuth();
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="flex min-h-dvh flex-col items-center justify-center bg-[var(--background)] px-4 py-12 focus:outline-none"
    >
      <div className="mb-8 flex items-center gap-3">
        <span aria-hidden="true" className="brand-mark">
          ಇ
        </span>
        <span className="flex flex-col leading-tight">
          <span className="text-[length:var(--text-sm)] font-semibold tracking-tight text-[var(--text)]">
            Indic Books
          </span>
          <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Maintained by OKI
          </span>
        </span>
      </div>

      <Card className="w-full max-w-lg text-center">
        <p className="text-[length:var(--text-xs)] font-medium uppercase tracking-[0.14em] text-[var(--warning-700)] dark:text-[var(--warning-300)]">
          Maintenance
        </p>
        <h1 className="mt-2 text-[length:var(--text-2xl)] font-semibold tracking-tight text-[var(--text)]">
          The service is paused for maintenance
        </h1>
        <p className="mx-auto mt-3 max-w-md text-[length:var(--text-sm)] text-[var(--text-muted)]">
          {status.message ||
            "We are making a few changes and will be back shortly."}
        </p>
        {status.until && (
          <p className="mt-3 text-[length:var(--text-xs)] tabular-nums text-[var(--text-muted)]">
            Expected back {new Date(status.until).toLocaleString()}
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <Button variant="outline" onClick={onRetry}>
            Check again
          </Button>
          {!isAuthenticated && (
            <Link
              href="/login"
              className="inline-flex min-h-10 items-center rounded-[var(--radius)] px-4 text-[length:var(--text-sm)] font-medium text-[var(--accent-text)] hover:bg-[var(--accent-soft)]"
            >
              Administrator sign in
            </Link>
          )}
        </div>
      </Card>

      <p className="mt-5 max-w-md text-center text-[length:var(--text-xs)] text-[var(--text-muted)]">
        Jobs that were already running continue in the background. Nothing is
        lost while the service is paused.
      </p>
    </main>
  );
}

/**
 * Full-block gate for maintenance mode. Admins and the auth screens stay
 * reachable so the switch can always be turned off.
 */
export default function MaintenanceGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { isAdmin } = useAuth();
  const { data, refetch } = useQuery({
    queryKey: ["public-status"],
    queryFn: getPublicStatus,
    staleTime: 15_000,
    refetchInterval: (query) => {
      if (typeof document !== "undefined" && document.hidden) return false;
      return query.state.data?.maintenance.enabled ? 10_000 : 30_000;
    },
    retry: 1,
  });

  const onAuthPath = AUTH_PATHS.some((path) => matchesPrefix(pathname, path));
  const maintenance = data?.maintenance;

  if (!maintenance?.enabled || isAdmin || onAuthPath) {
    return <>{children}</>;
  }

  return <MaintenanceScreen status={maintenance} onRetry={() => refetch()} />;
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationRow,
} from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import { Spinner } from "@/components/shared/spinner";

const POLL_MS = 30_000;

export function NotificationBell() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { data: unread = 0 } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: getUnreadNotificationCount,
    refetchInterval: POLL_MS,
    staleTime: 15_000,
  });

  const { data: recent, isLoading } = useQuery({
    queryKey: ["notifications", "recent"],
    queryFn: () => getNotifications({ page: 1, page_size: 8 }),
    enabled: open,
    staleTime: 10_000,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["notifications"] });

  const readOne = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: invalidate,
  });
  const readAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: invalidate,
  });

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onPointer = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        // Return the user to where they opened it.
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const handleOpen = (notification: NotificationRow) => {
    if (!notification.read_at) readOne.mutate(notification.id);
    setOpen(false);
    if (notification.link_url) router.push(notification.link_url);
    else invalidate();
  };

  return (
    <div ref={containerRef} className="relative ml-1">
      <button
        type="button"
        ref={triggerRef}
        onClick={() => setOpen((value) => !value)}
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
        }
        aria-expanded={open}
        aria-haspopup="true"
        className={cn(
          "relative inline-flex size-9 items-center justify-center rounded-[var(--radius)]",
          "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-sunken)]",
          "transition-colors duration-[var(--duration-fast)]",
          focusRing,
        )}
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="size-4" aria-hidden="true">
          <path d="M10 2a6 6 0 00-6 6v2.586l-1.293 1.293A1 1 0 003.414 14h13.172a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM8 16a2 2 0 104 0H8z" />
        </svg>
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent)] px-1 text-[10px] font-semibold leading-none text-white"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          tabIndex={-1}
          role="region"
          aria-label="Notifications"
          className="fixed inset-x-3 top-[calc(var(--nav-height)+0.5rem)] z-50 max-h-[70vh] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)] focus:outline-none sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:max-h-none sm:w-80"
        >
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
            <p className="text-[length:var(--text-sm)] font-semibold text-[var(--text)]">
              Notifications
            </p>
            <button
              type="button"
              onClick={() => readAll.mutate()}
              disabled={unread === 0 || readAll.isPending}
              className={cn(
                "rounded-[var(--radius-sm)] px-2 py-1 text-[length:var(--text-xs)] text-[var(--accent-text)]",
                "hover:bg-[var(--accent-soft)] disabled:opacity-50",
                focusRing,
              )}
            >
              Mark all read
            </button>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-6">
              <Spinner className="size-5 text-[var(--accent-text)]" />
            </div>
          ) : recent && recent.items.length > 0 ? (
            <ul className="max-h-96 overflow-y-auto">
              {recent.items.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => handleOpen(notification)}
                    className={cn(
                      "flex w-full gap-2.5 border-b border-[var(--border)] px-4 py-3 text-left last:border-b-0",
                      "hover:bg-[var(--surface-sunken)]",
                      focusRing,
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "mt-1.5 size-1.5 shrink-0 rounded-full",
                        notification.read_at
                          ? "bg-transparent"
                          : "bg-[var(--accent)]",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          "block truncate text-[length:var(--text-sm)]",
                          notification.read_at
                            ? "text-[var(--text-muted)]"
                            : "font-medium text-[var(--text)]",
                        )}
                      >
                        {notification.title}
                      </span>
                      <span className="mt-0.5 block truncate text-[length:var(--text-xs)] text-[var(--text-muted)]">
                        {notification.body}
                      </span>
                      <span className="mt-1 block text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                        {formatRelativeTime(notification.created_at)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-6 text-center text-[length:var(--text-sm)] text-[var(--text-muted)]">
              You&apos;re all caught up.
            </p>
          )}

          <button
            type="button"
            onClick={() => {
              setOpen(false);
              router.push("/notifications");
            }}
            className={cn(
              "block w-full border-t border-[var(--border)] px-4 py-2.5 text-center text-[length:var(--text-sm)]",
              "text-[var(--accent-text)] hover:bg-[var(--surface-sunken)]",
              focusRing,
            )}
          >
            View all notifications
          </button>
        </div>
      )}
    </div>
  );
}
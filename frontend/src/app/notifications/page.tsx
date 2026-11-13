"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getNotificationPreferences,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  setNotificationPreferences,
  type NotificationRow,
} from "@/lib/api";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
import Pagination from "@/components/shared/pagination";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/shared/skeleton";
import { Button } from "@/components/shared/button";
import { Switch } from "@/components/shared/switch";
import { Chip, type ChipTone } from "@/components/shared/chip";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { cn, formatRelativeTime } from "@/lib/utils";
import { focusRing } from "@/lib/focus-ring";
import { toast } from "sonner";
import { getErrorMessage } from "@/lib/error-handler";

const PAGE_SIZE = 20;

const TYPE_META: Record<
  NotificationRow["type"],
  { label: string; tone: ChipTone }
> = {
  job_completed: { label: "Job finished", tone: "success" },
  job_failed: { label: "Job failed", tone: "danger" },
  job_cancelled: { label: "Job cancelled", tone: "warning" },
  account_approved: { label: "Account", tone: "accent" },
  pending_registration: { label: "Registration", tone: "info" },
};

export default function NotificationsPage() {
  useDocumentTitle("Notifications");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);

  const list = useQuery({
    queryKey: ["notifications", "list", page],
    queryFn: () => getNotifications({ page, page_size: PAGE_SIZE }),
  });
  const preferences = useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: getNotificationPreferences,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["notifications"] });

  const readOne = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: invalidate,
  });
  const readAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      invalidate();
      toast.success("All notifications marked as read");
    },
  });
  const updatePreference = useMutation({
    mutationFn: setNotificationPreferences,
    onSuccess: (enabled) => {
      queryClient.setQueryData(["notifications", "preferences"], enabled);
      toast.success(
        enabled ? "Email alerts enabled" : "Email alerts disabled",
      );
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  const open = (notification: NotificationRow) => {
    if (!notification.read_at) readOne.mutate(notification.id);
    if (notification.link_url) router.push(notification.link_url);
  };

  const unread = list.data?.unread_count ?? 0;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Account"
        title="Notifications"
        description={
          unread > 0
            ? `${unread} unread notification${unread !== 1 ? "s" : ""}`
            : "You're all caught up."
        }
        actions={
          <Button
            variant="outline"
            onClick={() => readAll.mutate()}
            loading={readAll.isPending}
            disabled={unread === 0}
          >
            Mark all as read
          </Button>
        }
      />

      <Card className="mb-4" title="Email alerts">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-xl">
            <p className="text-[var(--text-sm)] text-[var(--text)]">
              Send these notifications to your email address as well.
            </p>
            <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">
              In-app notifications are always on and cannot be disabled.
            </p>
          </div>
          <Switch
            label="Email alerts"
            checked={preferences.data ?? true}
            disabled={preferences.isLoading || updatePreference.isPending}
            onCheckedChange={(enabled) => updatePreference.mutate(enabled)}
          />
        </div>
      </Card>

      <Card
        title="Recent activity"
        description="Job results, account decisions and registration requests."
      >
        {list.isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((row) => (
              <Skeleton key={row} className="h-14 w-full" />
            ))}
          </div>
        ) : list.data && list.data.items.length > 0 ? (
          <ul className="-mx-1">
            {list.data.items.map((notification) => {
              const meta = TYPE_META[notification.type];
              return (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => open(notification)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-[var(--radius)] px-3 py-3 text-left",
                      "hover:bg-[var(--surface-sunken)]",
                      focusRing,
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        notification.read_at
                          ? "bg-transparent"
                          : "bg-[var(--accent)]",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <Chip tone={meta.tone}>{meta.label}</Chip>
                        <span
                          className={cn(
                            "text-[var(--text-sm)]",
                            notification.read_at
                              ? "text-[var(--text-muted)]"
                              : "font-medium text-[var(--text)]",
                          )}
                        >
                          {notification.title}
                        </span>
                      </span>
                      <span className="mt-1 block text-[var(--text-sm)] text-[var(--text-muted)]">
                        {notification.body}
                      </span>
                      <span className="mt-1 block text-[var(--text-xs)] text-[var(--text-muted)]">
                        {formatRelativeTime(notification.created_at)}
                      </span>
                    </span>
                    {notification.link_url && (
                      <span
                        aria-hidden="true"
                        className="mt-1 shrink-0 text-[var(--text-muted)]"
                      >
                        <svg
                          viewBox="0 0 20 20"
                          fill="currentColor"
                          className="size-4"
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState
            title="No notifications yet"
            description="Job results and account decisions will appear here."
          />
        )}

        {list.data && (
          <Pagination
            page={page}
            totalPages={list.data.total_pages}
            onPageChange={setPage}
          />
        )}
      </Card>
    </PageContainer>
  );
}
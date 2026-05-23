"use client";

type BadgeStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<
  BadgeStatus,
  { bg: string; text: string; label: string; pulse?: boolean }
> = {
  queued: { bg: "bg-gray-100 dark:bg-gray-700", text: "text-gray-700 dark:text-gray-300", label: "Queued" },
  running: {
    bg: "bg-blue-100 dark:bg-blue-900/50",
    text: "text-blue-700 dark:text-blue-300",
    label: "Running",
    pulse: true,
  },
  completed: { bg: "bg-green-100 dark:bg-green-900/50", text: "text-green-700 dark:text-green-300", label: "Completed" },
  failed: { bg: "bg-red-100 dark:bg-red-900/50", text: "text-red-700 dark:text-red-300", label: "Failed" },
  cancelled: { bg: "bg-yellow-100 dark:bg-yellow-900/50", text: "text-yellow-700 dark:text-yellow-300", label: "Cancelled" },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status as BadgeStatus] ?? {
    bg: "bg-gray-100 dark:bg-gray-700",
    text: "text-gray-700 dark:text-gray-300",
    label: status,
  };

  return (
    <span
      role="status"
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded ${config.bg} ${config.text}`}
    >
      {config.pulse && (
        <span className="relative flex h-2 w-2" aria-hidden="true">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
        </span>
      )}
      {config.label}
    </span>
  );
}

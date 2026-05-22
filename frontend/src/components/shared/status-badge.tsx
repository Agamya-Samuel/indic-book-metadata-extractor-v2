"use client";

type BadgeStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<
  BadgeStatus,
  { bg: string; text: string; label: string; pulse?: boolean }
> = {
  queued: { bg: "bg-gray-100", text: "text-gray-700", label: "Queued" },
  running: {
    bg: "bg-blue-100",
    text: "text-blue-700",
    label: "Running",
    pulse: true,
  },
  completed: { bg: "bg-green-100", text: "text-green-700", label: "Completed" },
  failed: { bg: "bg-red-100", text: "text-red-700", label: "Failed" },
  cancelled: { bg: "bg-yellow-100", text: "text-yellow-700", label: "Cancelled" },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status as BadgeStatus] ?? {
    bg: "bg-gray-100",
    text: "text-gray-700",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded ${config.bg} ${config.text}`}
    >
      {config.pulse && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
        </span>
      )}
      {config.label}
    </span>
  );
}

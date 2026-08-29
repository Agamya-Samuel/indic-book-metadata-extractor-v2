"use client";

import { cn } from "@/lib/utils";

interface AdminStatsCardProps {
  label: string;
  value: React.ReactNode;
  sublabel?: React.ReactNode;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
  className?: string;
}

const toneAccent: Record<NonNullable<AdminStatsCardProps["tone"]>, string> = {
  neutral: "bg-[var(--text-muted)]",
  info: "bg-[var(--info-500)]",
  success: "bg-[var(--success-500)]",
  warning: "bg-[var(--warning-500)]",
  danger: "bg-[var(--danger-500)]",
};

export default function AdminStatsCard({
  label,
  value,
  sublabel,
  tone = "neutral",
  className,
}: AdminStatsCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]",
        "shadow-[var(--shadow-xs)] p-5",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("absolute inset-x-0 top-0 h-0.5", toneAccent[tone])}
      />
      <p className="text-[var(--text-xs)] font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-2 text-[var(--text-2xl)] font-semibold tabular-nums text-[var(--text)] leading-tight">
        {value}
      </p>
      {sublabel && (
        <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">
          {sublabel}
        </p>
      )}
    </div>
  );
}
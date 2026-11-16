"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getAdminSystemMetrics, type ServiceHealth } from "@/lib/api";
import MaintenanceCard from "@/components/admin/maintenance-card";
import { PageContainer, Card, PageHeader } from "@/components/shared/card";
import StatCard from "@/components/shared/stat-card";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Chip, type ChipTone } from "@/components/shared/chip";
import { Banner, ErrorState, EmptyState } from "@/components/shared/empty-state";
import { SkeletonTable } from "@/components/shared/skeleton";
import { Button } from "@/components/shared/button";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";

function fmtMb(value?: number | null): string {
  if (value == null) return "—";
  if (value >= 1024) return `${(value / 1024).toFixed(1)} GB`;
  return `${value.toFixed(0)} MB`;
}

function fmtGb(value?: number | null): string {
  if (value == null) return "—";
  return `${value.toFixed(1)} GB`;
}

function fmtPercent(value?: number | null): string {
  if (value == null) return "—";
  return `${value.toFixed(0)}%`;
}

function fmtUptime(seconds?: number | null): string {
  if (seconds == null) return "—";
  const totalMinutes = Math.floor(seconds / 60);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function usageTone(
  percent?: number | null,
): "neutral" | "info" | "warning" | "danger" {
  if (percent == null) return "neutral";
  if (percent >= 90) return "danger";
  if (percent >= 75) return "warning";
  return "info";
}

const SERVICE_TONE: Record<string, ChipTone> = {
  ok: "success",
  degraded: "warning",
  unreachable: "danger",
  unavailable: "danger",
};

function serviceDetail(service: ServiceHealth): React.ReactNode {
  const meta = service.meta ?? {};
  if (service.name === "Celery workers") {
    const workers = Array.isArray(meta.workers) ? meta.workers : [];
    const queues = Array.isArray(meta.queues) ? meta.queues : [];
    const active = typeof meta.active_tasks === "number" ? meta.active_tasks : null;
    return (
      <div className="flex flex-col gap-1">
        <span>{service.detail ?? "—"}</span>
        <span className="text-[10px] text-[var(--text-muted)]">
          {workers.length > 0 ? workers.join(", ") : "no workers"}
          {active != null ? ` · ${active} active` : ""}
          {queues.length > 0 ? ` · queues: ${queues.join(", ")}` : ""}
        </span>
      </div>
    );
  }
  if (service.name === "LLM (Ollama)") {
    const loaded = Array.isArray(meta.loaded) ? meta.loaded : [];
    return (
      <div className="flex flex-col gap-1">
        <span>{service.detail ?? "—"}</span>
        {loaded.map((model, index) => {
          const entry = model as { name?: string; size_mb?: number };
          return (
            <span key={`${entry.name ?? index}`} className="text-[10px] text-[var(--text-muted)]">
              {entry.name ?? "model"} · {fmtMb(entry.size_mb)}
            </span>
          );
        })}
      </div>
    );
  }
  return service.detail ?? "—";
}

const serviceColumns: DataTableColumn<ServiceHealth>[] = [
  {
    key: "service",
    header: "Service",
    cell: (service) => (
      <span className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
        {service.name}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    cell: (service) => (
      <Chip tone={SERVICE_TONE[service.status] ?? "neutral"} dot>
        {service.status}
      </Chip>
    ),
  },
  {
    key: "latency",
    header: "Latency",
    hideBelow: "sm",
    className: "tabular-nums text-[length:var(--text-xs)] text-[var(--text-muted)]",
    cell: (service) =>
      service.latency_ms != null ? `${service.latency_ms.toFixed(0)} ms` : "—",
  },
  {
    key: "detail",
    header: "Detail",
    hideBelow: "md",
    className: "text-[length:var(--text-xs)] text-[var(--text-muted)]",
    cell: (service) => serviceDetail(service),
  },
];

export default function AdminSystemPage() {
  useDocumentTitle("Admin · System");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["admin-system"],
    queryFn: getAdminSystemMetrics,
    staleTime: 9 * 1000,
    refetchInterval: () => {
      if (typeof document !== "undefined" && document.hidden) return false;
      return 10_000;
    },
  });

  const externalLinks = [
    { label: "Flower", href: process.env.NEXT_PUBLIC_FLOWER_URL },
    { label: "New Relic", href: process.env.NEXT_PUBLIC_NEW_RELIC_URL },
    { label: "Better Stack", href: process.env.NEXT_PUBLIC_BETTERSTACK_URL },
  ].filter((link): link is { label: string; href: string } => Boolean(link.href));

  const server = data?.server;
  const overall = data?.overall_status ?? "ok";
  const overallTone =
    overall === "critical" ? "danger" : overall === "degraded" ? "warning" : "success";

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Admin"
        title="System"
        description="Host resources, application service health, and queue activity."
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()} loading={isFetching}>
            Refresh
          </Button>
        }
      />

      <MaintenanceCard />

      {isError ? (
        <ErrorState
          title="Could not load system metrics"
          description={getErrorMessage(error)}
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Try again
            </Button>
          }
        />
      ) : isLoading || !data ? (
        <SkeletonTable rows={6} />
      ) : (
        <div className="space-y-4">
          <Banner tone={overallTone}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <strong className="font-semibold">System {overall}.</strong>{" "}
                {overall === "ok"
                  ? "All critical services responded."
                  : overall === "degraded"
                    ? "A service is cold or a resource is near its limit."
                    : "A critical service is unreachable."}
              </span>
              <span className="text-[length:var(--text-xs)] tabular-nums opacity-80">
                Updated {new Date(data.generated_at).toLocaleTimeString()}
              </span>
            </div>
          </Banner>

          <Card title="Server resources" description="Host-level CPU, memory, and disk">
            {server?.available === false ? (
              <EmptyState
                title="Host metrics unavailable"
                description="The psutil package is not installed in the backend image."
              />
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <StatCard
                  label="CPU"
                  value={fmtPercent(server?.cpu_percent)}
                  sublabel={server?.cpu_count ? `${server.cpu_count} cores` : undefined}
                  tone={usageTone(server?.cpu_percent)}
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
                <StatCard
                  label="Load average"
                  value={
                    server?.load_1 != null
                      ? server.load_1.toFixed(2)
                      : "—"
                  }
                  sublabel={
                    server?.load_5 != null && server?.load_15 != null
                      ? `${server.load_5.toFixed(2)} · ${server.load_15.toFixed(2)}`
                      : undefined
                  }
                  tone="neutral"
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
                <StatCard
                  label="Memory"
                  value={fmtPercent(server?.memory_percent)}
                  sublabel={`${fmtMb(server?.memory_used_mb)} of ${fmtMb(server?.memory_total_mb)}`}
                  tone={usageTone(server?.memory_percent)}
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
                <StatCard
                  label="Available RAM"
                  value={fmtMb(server?.memory_available_mb)}
                  sublabel={`swap ${fmtMb(server?.swap_used_mb)} used`}
                  tone="neutral"
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
                <StatCard
                  label="Disk"
                  value={fmtPercent(server?.disk_percent)}
                  sublabel={`${fmtGb(server?.disk_used_gb)} of ${fmtGb(server?.disk_total_gb)} · ${fmtGb(server?.disk_free_gb)} free`}
                  tone={usageTone(server?.disk_percent)}
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
                <StatCard
                  label="Uptime"
                  value={fmtUptime(server?.uptime_seconds)}
                  sublabel={
                    server?.storage_used_mb != null
                      ? `storage ${fmtMb(server.storage_used_mb)}`
                      : undefined
                  }
                  tone="neutral"
                  flush
                  className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                />
              </div>
            )}
          </Card>

          <Card title="Application services" description="Dependency reachability">
            <DataTable
              bare
              columns={serviceColumns}
              rows={data.services}
              rowKey={(service) => service.name}
              caption="Application service health"
              empty={
                <EmptyState
                  title="No services reported"
                  description="The backend did not return service health."
                />
              }
            />
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Queue activity" description="Broker depth versus database state">
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {data.queues.queues.map((queue) => (
                    <StatCard
                      key={queue.name}
                      label={`${queue.name} queue`}
                      value={queue.depth}
                      sublabel="messages in Redis"
                      tone={queue.depth > 0 ? "warning" : "neutral"}
                      flush
                      className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]/40"
                    />
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.queues.by_status).map(([status, count]) => (
                    <Chip key={status} dot tone={status === "failed" ? "danger" : status === "running" ? "info" : "neutral"}>
                      {status} {count}
                    </Chip>
                  ))}
                  {Object.entries(data.queues.by_type).map(([type, count]) => (
                    <Chip key={type} tone="neutral">
                      {type} {count}
                    </Chip>
                  ))}
                </div>
                <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                  {data.queues.completed_last_15m} job
                  {data.queues.completed_last_15m === 1 ? "" : "s"} completed in the last
                  15 minutes.
                </p>
              </div>
            </Card>

            <Card title="External monitoring" description="Long history and alerting">
              {externalLinks.length === 0 ? (
                <p className="text-[length:var(--text-sm)] text-[var(--text-muted)]">
                  No external monitoring links configured. Set
                  NEXT_PUBLIC_FLOWER_URL, NEXT_PUBLIC_NEW_RELIC_URL, or
                  NEXT_PUBLIC_BETTERSTACK_URL to surface them here.
                </p>
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {externalLinks.map((link) => (
                    <li key={link.label} className="py-2.5 first:pt-0 last:pb-0">
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[length:var(--text-sm)] font-medium text-[var(--accent-text)] hover:underline"
                      >
                        {link.label} →
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-[length:var(--text-xs)] text-[var(--text-muted)]">
                This page covers live host and service state. Alerting and long-term
                history live in the external providers.
              </p>
            </Card>
          </div>
        </div>
      )}
    </PageContainer>
  );
}

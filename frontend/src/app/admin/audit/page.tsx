"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getAuditLogs,
  getAuditActions,
  type AuditActionInfo,
  type AuditLogRow,
  type AuditSortColumn,
} from "@/lib/api";
import { PageContainer, Card } from "@/components/shared/card";
import { Field, Input, Select } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { EmptyState } from "@/components/shared/empty-state";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Chip, type ChipTone } from "@/components/shared/chip";
import Pagination from "@/components/shared/pagination";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "@/lib/pagination";
import { getErrorMessage } from "@/lib/error-handler";
import { cn } from "@/lib/utils";

const CATEGORY_TONE: Record<string, ChipTone> = {
  auth: "info",
  user: "accent",
  book: "neutral",
  processing: "neutral",
  job: "warning",
  export: "neutral",
  config: "warning",
  system: "danger",
};

const DATE_PRESETS = [
  { label: "24 hours", hours: 24 },
  { label: "7 days", hours: 24 * 7 },
  { label: "30 days", hours: 24 * 30 },
] as const;

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ActorCell({ row }: { row: AuditLogRow }) {
  const name = row.actor_display_name || row.actor_email || row.actor_type;
  return (
    <div className="min-w-40">
      <div className="truncate font-medium text-[var(--text)]">{name}</div>
      <div className="truncate text-xs text-[var(--text-muted)]">
        {row.actor_email && row.actor_display_name
          ? row.actor_email
          : row.actor_user_id
            ? row.actor_user_id.slice(0, 8)
            : "—"}
      </div>
    </div>
  );
}

function ResultBadge({ result }: { result: AuditLogRow["result"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ring-1 ring-inset",
        result === "success"
          ? "bg-[var(--success-50)] text-[var(--success-700)] ring-[var(--success-500)]/30 dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]"
          : "bg-[var(--danger-50)] text-[var(--danger-700)] ring-[var(--danger-500)]/30 dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]",
      )}
    >
      {result}
    </span>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  const [expanded, setExpanded] = React.useState(false);
  if (value === null || value === undefined) return null;
  const text = JSON.stringify(value, null, 2);
  const shown = expanded ? text : text.split("\n").slice(0, 12).join("\n");
  return (
    <div className="min-w-0">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {label}
        </span>
        {text.split("\n").length > 12 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-[var(--accent)] hover:underline"
          >
            {expanded ? "Collapse" : "Show full JSON"}
          </button>
        )}
      </div>
      <pre className="overflow-x-auto rounded-[var(--radius)] bg-[var(--surface-sunken)] p-2 text-xs text-[var(--text)]">
        {shown}
      </pre>
    </div>
  );
}

/** Only the changed keys, rendered as a compact from → to table. */
function DiffTable({ row }: { row: AuditLogRow }) {
  const before = row.before ?? {};
  const after = row.after ?? {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
  if (keys.length === 0) return null;
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left uppercase tracking-wider text-[var(--text-muted)]">
          <th className="py-1 pr-4 font-medium">Field</th>
          <th className="py-1 pr-4 font-medium">From</th>
          <th className="py-1 font-medium">To</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[var(--border)]">
        {keys.map((key) => (
          <tr key={key} className="align-top">
            <td className="py-1 pr-4 font-mono text-[var(--text)]">{key}</td>
            <td className="max-w-64 truncate py-1 pr-4 font-mono text-[var(--danger-700)] dark:text-[var(--danger-100)]">
              {JSON.stringify(before[key])}
            </td>
            <td className="max-w-64 truncate py-1 font-mono text-[var(--success-700)] dark:text-[var(--success-100)]">
              {JSON.stringify(after[key])}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AuditDetail({ row }: { row: AuditLogRow }) {
  return (
    <div className="space-y-3 text-sm">
      <DiffTable row={row} />
      {row.error_message && (
        <div className="rounded-[var(--radius)] bg-[var(--danger-50)] p-2 text-xs text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]">
          {row.error_message}
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        <JsonBlock label="Details" value={row.details} />
        <div className="space-y-1 text-xs text-[var(--text-muted)]">
          <div className="font-medium uppercase tracking-wider">Request</div>
          <div>IP: {row.ip_address ?? "—"}</div>
          <div>Request ID: {row.request_id ?? "—"}</div>
          <div className="break-all">User agent: {row.user_agent ?? "—"}</div>
          {row.subject_user_id && <div>Subject user: {row.subject_user_id}</div>}
          {row.truncated && <div className="text-[var(--warning-700)]">Values were truncated to fit this row.</div>}
        </div>
      </div>
    </div>
  );
}

function AuditLogsContent() {
  useDocumentTitle("Admin · Audit logs");

  const searchParams = useSearchParams();

  const readParam = (key: string): string => searchParams.get(key) ?? "";

  const [search, setSearch] = React.useState(readParam("q"));
  const [debouncedSearch, setDebouncedSearch] = React.useState(readParam("q"));
  const [category, setCategory] = React.useState(readParam("category"));
  const [action, setAction] = React.useState(readParam("action"));
  const [actor, setActor] = React.useState(readParam("actor"));
  const [role, setRole] = React.useState(readParam("actor_role"));
  const [result, setResult] = React.useState(readParam("result"));
  const [resourceType, setResourceType] = React.useState(readParam("resource_type"));
  const [datePreset, setDatePreset] = React.useState<string>(() => {
    const from = readParam("date_from");
    return from ? "custom" : "";
  });
  const [dateFrom, setDateFrom] = React.useState(readParam("date_from"));
  const [dateTo, setDateTo] = React.useState(readParam("date_to"));
  const [excludeMeta, setExcludeMeta] = React.useState(readParam("exclude_meta") === "true");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(DEFAULT_PAGE_SIZE);
  const [sort, setSort] = React.useState<AuditSortColumn>("created_at");
  const [order, setOrder] = React.useState<"asc" | "desc">("desc");
  const [expandedKey, setExpandedKey] = React.useState<string | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const actionsQuery = useQuery({
    queryKey: ["audit-actions"],
    queryFn: getAuditActions,
    staleTime: 5 * 60 * 1000,
  });

  const actions: AuditActionInfo[] = React.useMemo(
    () => actionsQuery.data ?? [],
    [actionsQuery.data],
  );
  const visibleActions = React.useMemo(
    () => (category ? actions.filter((a) => a.category === category) : actions),
    [actions, category],
  );
  const actionLabels = React.useMemo(
    () => new Map(actions.map((a) => [a.value, a.label])),
    [actions],
  );

  const query = React.useMemo(() => {
    const preset = DATE_PRESETS.find((p) => String(p.hours) === datePreset);
    return {
      q: debouncedSearch || undefined,
      category: category || undefined,
      action: action || undefined,
      actor_user_id: undefined as string | undefined,
      actor_role: role || undefined,
      actor_type: undefined as string | undefined,
      resource_type: resourceType || undefined,
      result: result || undefined,
      exclude_meta: excludeMeta || undefined,
      // Preset cutoffs are resolved in the query function: Date.now() during
      // render would make the memo unstable.
      date_preset_hours: preset ? preset.hours : undefined,
      date_from: preset ? undefined : dateFrom || undefined,
      date_to: dateTo || undefined,
      sort,
      order,
      page,
      page_size: pageSize,
    };
  }, [debouncedSearch, category, action, role, resourceType, result, excludeMeta, datePreset, dateFrom, dateTo, sort, order, page, pageSize]);

  // Actor filter: a UUID targets actor_user_id; anything else is folded into
  // the free-text search so the Search box keeps working.
  const actorFilter = React.useMemo(() => {
    const value = actor.trim();
    if (!value) return {};
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
    return isUuid ? { actor_user_id: value } : { actor_text: value };
  }, [actor]);

  const logsQuery = useQuery({
    queryKey: ["audit-logs", query, actorFilter],
    queryFn: () => {
      const { date_preset_hours: presetHours, ...rest } = query;
      const from = presetHours
        ? new Date(Date.now() - presetHours * 3600 * 1000).toISOString()
        : rest.date_from
          ? new Date(rest.date_from).toISOString()
          : undefined;
      const to = rest.date_to ? new Date(rest.date_to).toISOString() : undefined;
      const { actor_text, ...actorRest } = actorFilter;
      const q = [rest.q, actor_text].filter(Boolean).join(" ") || undefined;
      return getAuditLogs({ ...rest, ...actorRest, q, date_from: from, date_to: to });
    },
  });

  // Mirror the filters into the query string so a view is shareable.
  React.useEffect(() => {
    const params = new URLSearchParams();
    if (debouncedSearch) params.set("q", debouncedSearch);
    if (category) params.set("category", category);
    if (action) params.set("action", action);
    if (actor) params.set("actor", actor);
    if (role) params.set("actor_role", role);
    if (result) params.set("result", result);
    if (resourceType) params.set("resource_type", resourceType);
    if (excludeMeta) params.set("exclude_meta", "true");
    if (datePreset === "custom" && dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [debouncedSearch, category, action, actor, role, result, resourceType, excludeMeta, datePreset, dateFrom, dateTo]);

  const rows = logsQuery.data?.items ?? [];
  const total = logsQuery.data?.total ?? 0;
  const totalPages = logsQuery.data?.total_pages ?? 1;

  const onSort = (key: string) => {
    const column = key as AuditSortColumn;
    if (sort === column) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(column);
      setOrder("desc");
    }
    setPage(1);
  };

  const resetFilters = () => {
    setSearch("");
    setCategory("");
    setAction("");
    setActor("");
    setRole("");
    setResult("");
    setResourceType("");
    setDatePreset("");
    setDateFrom("");
    setDateTo("");
    setExcludeMeta(false);
    setPage(1);
  };

  const columns: DataTableColumn<AuditLogRow>[] = [
    {
      key: "expand",
      header: "",
      className: "w-8",
      cell: (row) => (
        <button
          type="button"
          onClick={() => setExpandedKey((k) => (k === row.id ? null : row.id))}
          aria-expanded={expandedKey === row.id}
          aria-label={expandedKey === row.id ? "Collapse details" : "Expand details"}
          className="inline-flex size-6 items-center justify-center rounded-[var(--radius-xs)] text-[var(--text-muted)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text)]"
        >
          <svg
            viewBox="0 0 10 12"
            className={cn("size-2.5 transition-transform", expandedKey === row.id && "rotate-90")}
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M2 1.5 8 6l-6 4.5z" />
          </svg>
        </button>
      ),
    },
    {
      key: "created_at",
      header: "When",
      sortKey: "created_at",
      cell: (row) => (
        <span className="whitespace-nowrap text-xs text-[var(--text-muted)]">
          {formatTimestamp(row.created_at)}
        </span>
      ),
    },
    {
      key: "actor",
      header: "Actor",
      sortKey: "actor",
      cell: (row) => <ActorCell row={row} />,
    },
    {
      key: "action",
      header: "Action",
      sortKey: "action",
      cell: (row) => (
        <div className="flex min-w-40 flex-col gap-0.5">
          <span className="font-medium text-[var(--text)]">
            {actionLabels.get(row.action) ?? row.action}
          </span>
          <div className="flex items-center gap-1">
            <Chip tone={CATEGORY_TONE[row.category] ?? "neutral"}>{row.category}</Chip>
            {row.result === "failure" && <Chip tone="danger">failure</Chip>}
          </div>
        </div>
      ),
    },
    {
      key: "description",
      header: "Description",
      cell: (row) => (
        <span className="block max-w-96 truncate text-[var(--text-muted)]" title={row.description}>
          {row.description}
        </span>
      ),
      hideBelow: "lg",
    },
    {
      key: "resource",
      header: "Resource",
      hideBelow: "md",
      cell: (row) => (
        <div className="min-w-32 text-xs">
          <div className="text-[var(--text)]">{row.resource_type ?? "—"}</div>
          <div className="truncate font-mono text-[var(--text-muted)]" title={row.resource_id ?? ""}>
            {row.resource_id ? row.resource_id.slice(0, 12) : "—"}
          </div>
        </div>
      ),
    },
    {
      key: "result",
      header: "Result",
      sortKey: "result",
      cell: (row) => <ResultBadge result={row.result} />,
    },
  ];

  return (
    <PageContainer>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text)]">Audit logs</h1>
            <p className="text-sm text-[var(--text-muted)]">
              {total.toLocaleString()} event{total === 1 ? "" : "s"}
              {logsQuery.isFetching ? " · refreshing…" : ""}
            </p>
          </div>
          <Button variant="ghost" onClick={resetFilters}>
            Reset filters
          </Button>
        </div>

        <Card className="p-3">
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
            <Field label="Search" className="md:col-span-1 xl:col-span-2">
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Description, actor, action…"
              />
            </Field>
            <Field label="Category">
              <Select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setAction("");
                  setPage(1);
                }}
              >
                <option value="">All categories</option>
                {Array.from(new Set(actions.map((a) => a.category))).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Action">
              <Select
                value={action}
                onChange={(e) => {
                  setAction(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All actions</option>
                {visibleActions.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                    {a.critical ? " (critical)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Actor (name, email or user id)">
              <Input
                value={actor}
                onChange={(e) => {
                  setActor(e.target.value);
                  setPage(1);
                }}
                placeholder="Any actor"
              />
            </Field>
            <Field label="Role">
              <Select
                value={role}
                onChange={(e) => {
                  setRole(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any role</option>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </Select>
            </Field>
            <Field label="Result">
              <Select
                value={result}
                onChange={(e) => {
                  setResult(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any result</option>
                <option value="success">success</option>
                <option value="failure">failure</option>
              </Select>
            </Field>
            <Field label="Resource type">
              <Select
                value={resourceType}
                onChange={(e) => {
                  setResourceType(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any resource</option>
                {["user", "book", "page", "job", "config", "bulk_import", "wikibase", "system", "audit_log"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Date range">
              <Select
                value={datePreset}
                onChange={(e) => {
                  setDatePreset(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All time</option>
                {DATE_PRESETS.map((p) => (
                  <option key={p.hours} value={String(p.hours)}>
                    Last {p.label}
                  </option>
                ))}
                <option value="custom">Custom…</option>
              </Select>
            </Field>
            {datePreset === "custom" && (
              <>
                <Field label="From">
                  <Input
                    type="datetime-local"
                    value={dateFrom}
                    onChange={(e) => {
                      setDateFrom(e.target.value);
                      setPage(1);
                    }}
                  />
                </Field>
                <Field label="To">
                  <Input
                    type="datetime-local"
                    value={dateTo}
                    onChange={(e) => {
                      setDateTo(e.target.value);
                      setPage(1);
                    }}
                  />
                </Field>
              </>
            )}
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm text-[var(--text-muted)]">
            <input
              type="checkbox"
              checked={excludeMeta}
              onChange={(e) => {
                setExcludeMeta(e.target.checked);
                setPage(1);
              }}
              className="size-4 rounded border-[var(--border)]"
            />
            Hide “audit log viewed” entries
          </label>
        </Card>

        {logsQuery.isError ? (
          <EmptyState
            title="Could not load the audit log"
            description={getErrorMessage(logsQuery.error)}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(row) => row.id}
            loading={logsQuery.isLoading}
            caption="Audit log entries"
            sortKey={sort}
            sortDirection={order}
            onSortChange={onSort}
            expandedRowKey={expandedKey}
            renderExpandedRow={(row) => <AuditDetail row={row} />}
            rowClassName={(row) =>
              expandedKey === row.id ? "bg-[var(--surface-sunken)]/40" : undefined
            }
            empty={
              <EmptyState
                title="No audit entries match"
                description="Try widening the filters or the date range."
              />
            }
          />
        )}

        <Pagination
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
          pageSize={pageSize}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          disabled={logsQuery.isFetching}
        />
      </div>
    </PageContainer>
  );
}

export default function AdminAuditPage() {
  return (
    <React.Suspense
      fallback={
        <PageContainer>
          <div className="text-sm text-[var(--text-muted)]">Loading audit logs…</div>
        </PageContainer>
      }
    >
      <AuditLogsContent />
    </React.Suspense>
  );
}
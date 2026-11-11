"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { getAdminUsers, type AdminUser } from "@/lib/api";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";

export interface OwnerSelection {
  id: string;
  label: string;
}

/**
 * Owner filter for the admin books/jobs tables: free-text user search that
 * resolves a display name / email to a user id, which the backend accepts as
 * the `owner_id` query parameter. Selection is shown as a removable chip.
 */
export default function OwnerFilter({
  value,
  onChange,
  id = "owner-filter",
}: {
  value: OwnerSelection | null;
  onChange: (value: OwnerSelection | null) => void;
  id?: string;
}) {
  const [query, setQuery] = React.useState("");
  const [debouncedQuery, setDebouncedQuery] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Close the suggestion list on any click outside the field.
  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const { data, isFetching } = useQuery({
    queryKey: ["owner-filter-users", debouncedQuery],
    queryFn: () =>
      getAdminUsers({ query: debouncedQuery, page_size: 10 }),
    enabled: debouncedQuery.length > 0 && !value,
    staleTime: 30 * 1000,
  });

  const results: AdminUser[] = data?.items ?? [];

  const pick = (user: AdminUser) => {
    onChange({ id: user.id, label: `${user.display_name} (${user.email})` });
    setQuery("");
    setOpen(false);
  };

  if (value) {
    return (
      <div className="w-56">
        <Field label="Owner" htmlFor={id}>
          <div className="flex items-center gap-1">
            <span className="inline-flex min-w-0 flex-1 items-center gap-1 h-10 rounded-[var(--radius)] border border-[var(--accent)]/40 bg-[var(--accent-soft)] px-2.5">
              <span className="truncate text-[var(--text-sm)] text-[var(--accent-soft-text)]">
                {value.label}
              </span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange(null)}
              aria-label="Clear owner filter"
            >
              Clear
            </Button>
          </div>
        </Field>
      </div>
    );
  }

  return (
    <div className="w-56 relative" ref={containerRef}>
      <Field label="Owner" htmlFor={id} hint="Filter by uploader">
        <Input
          id={id}
          type="text"
          placeholder="Search users…"
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
      </Field>
      {open && debouncedQuery && (
        <div className="absolute left-0 right-0 top-full z-40 mt-1 overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]">
          {isFetching ? (
            <div className="flex justify-center px-3 py-3">
              <Spinner className="size-4 text-[var(--accent)]" />
            </div>
          ) : results.length === 0 ? (
            <p className="px-3 py-3 text-[var(--text-xs)] text-[var(--text-muted)]">
              No users match &ldquo;{debouncedQuery}&rdquo;
            </p>
          ) : (
            <ul className="max-h-56 overflow-y-auto">
              {results.map((user) => (
                <li key={user.id}>
                  <button
                    type="button"
                    onClick={() => pick(user)}
                    className="block w-full px-3 py-2 text-left hover:bg-[var(--surface-sunken)] focus-visible:bg-[var(--surface-sunken)] focus:outline-none"
                  >
                    <span className="block truncate text-[var(--text-sm)] text-[var(--text)]">
                      {user.display_name}
                    </span>
                    <span className="block truncate text-[var(--text-xs)] text-[var(--text-muted)]">
                      {user.email}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

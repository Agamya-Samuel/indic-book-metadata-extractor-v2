"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminMaintenance,
  updateAdminMaintenance,
  type MaintenanceStatus,
} from "@/lib/api";
import { Card } from "@/components/shared/card";
import { Button } from "@/components/shared/button";
import { Field, Input, Textarea } from "@/components/shared/input";
import { Switch } from "@/components/shared/switch";
import { Banner } from "@/components/shared/empty-state";
import { SkeletonTable } from "@/components/shared/skeleton";
import { getErrorMessage } from "@/lib/error-handler";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function MaintenanceForm({ status }: { status: MaintenanceStatus }) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = React.useState(status.enabled);
  const [message, setMessage] = React.useState(status.message ?? "");
  const [until, setUntil] = React.useState(toLocalInput(status.until));

  const mutation = useMutation({
    mutationFn: () =>
      updateAdminMaintenance({
        enabled,
        message: message.trim() || null,
        until: enabled ? fromLocalInput(until) : null,
      }),
    onSuccess: (next) => {
      toast.success(
        next.enabled ? "Maintenance mode enabled" : "Maintenance mode disabled",
      );
      queryClient.invalidateQueries({ queryKey: ["admin-maintenance"] });
      queryClient.invalidateQueries({ queryKey: ["public-status"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error));
    },
  });

  return (
    <div className="space-y-4">
      {status.enabled && (
        <Banner tone="warning">
          Regular users are blocked right now. Admins keep access, and running
          jobs continue to completion.
        </Banner>
      )}

      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
            Maintenance mode
          </p>
          <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
            Blocks the app and API for everyone except admins. New uploads and
            job submissions are refused.
          </p>
        </div>
        <Switch
          label="Maintenance mode"
          checked={enabled}
          onCheckedChange={setEnabled}
        />
      </div>

      <Field
        label="Message"
        htmlFor="maintenance-message"
        hint="Shown on the maintenance screen. Leave blank for the default."
      >
        <Textarea
          id="maintenance-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={3}
          placeholder="The service is under maintenance. Please check back shortly."
        />
      </Field>

      <Field
        label="End automatically at"
        htmlFor="maintenance-until"
        hint="Optional. The service reopens after this time even if the switch is still on."
      >
        <Input
          id="maintenance-until"
          type="datetime-local"
          value={until}
          onChange={(event) => setUntil(event.target.value)}
          disabled={!enabled}
        />
      </Field>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-3">
        <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
          {status.updated_at
            ? `Last changed ${new Date(status.updated_at).toLocaleString()}${
                status.updated_by ? ` by ${status.updated_by}` : ""
              }`
            : "Never changed"}
        </span>
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
          Save maintenance settings
        </Button>
      </div>
    </div>
  );
}

export default function MaintenanceCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-maintenance"],
    queryFn: getAdminMaintenance,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return <SkeletonTable rows={2} />;
  }

  return (
    <Card
      title="Maintenance mode"
      description="Pause the service without stopping background jobs"
      className="mb-4"
    >
      <MaintenanceForm key={data.updated_at ?? "never"} status={data} />
    </Card>
  );
}

"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminSmtp,
  testAdminSmtp,
  updateAdminSmtp,
  type SmtpConfig,
} from "@/lib/api";
import { Card } from "@/components/shared/card";
import { Button } from "@/components/shared/button";
import { Field, Input } from "@/components/shared/input";
import { Switch } from "@/components/shared/switch";
import { Banner } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/shared/skeleton";
import { getErrorMessage } from "@/lib/error-handler";

interface FormState {
  enabled: boolean;
  host: string;
  port: string;
  username: string;
  password: string;
  from_email: string;
  from_name: string;
  use_tls: boolean;
  use_starttls: boolean;
}

function toForm(data: SmtpConfig): FormState {
  return {
    enabled: data.enabled,
    host: data.host,
    port: String(data.port),
    username: data.username,
    password: "",
    from_email: data.from_email,
    from_name: data.from_name,
    use_tls: data.use_tls,
    use_starttls: data.use_starttls,
  };
}

function SmtpForm({ data }: { data: SmtpConfig }) {
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState<FormState>(() => toForm(data));
  const [toEmail, setToEmail] = React.useState("");

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const payload = React.useMemo(
    () => ({
      enabled: form.enabled,
      host: form.host.trim(),
      port: Number(form.port) || 587,
      username: form.username.trim(),
      password: form.password,
      from_email: form.from_email.trim(),
      from_name: form.from_name.trim(),
      use_tls: form.use_tls,
      use_starttls: form.use_starttls,
    }),
    [form],
  );

  const save = useMutation({
    mutationFn: () => updateAdminSmtp(payload),
    onSuccess: (next) => {
      setForm(toForm(next));
      toast.success("SMTP settings saved");
      queryClient.invalidateQueries({ queryKey: ["admin-smtp"] });
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  const test = useMutation({
    mutationFn: () =>
      testAdminSmtp({
        to_email: toEmail.trim() || undefined,
        config: payload,
      }),
  });

  return (
    <div className="space-y-4">
      {data.source === "env" && (
        <Banner tone="info">
          No SMTP settings are stored yet; the server is using environment
          variables. Save your settings below to manage them here.
        </Banner>
      )}

      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
            Email delivery enabled
          </p>
          <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
            When off, transactional email is not sent (it is logged instead).
          </p>
        </div>
        <Switch
          label="Email delivery enabled"
          checked={form.enabled}
          onCheckedChange={(value) => update("enabled", value)}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Host" htmlFor="smtp-host" className="sm:col-span-2">
          <Input
            id="smtp-host"
            value={form.host}
            onChange={(event) => update("host", event.target.value)}
            placeholder="smtp.example.com"
            autoComplete="off"
          />
        </Field>
        <Field label="Port" htmlFor="smtp-port">
          <Input
            id="smtp-port"
            type="number"
            value={form.port}
            onChange={(event) => update("port", event.target.value)}
          />
        </Field>
        <Field label="Username" htmlFor="smtp-username">
          <Input
            id="smtp-username"
            value={form.username}
            onChange={(event) => update("username", event.target.value)}
            autoComplete="off"
          />
        </Field>
        <Field
          label="Password"
          htmlFor="smtp-password"
          hint={
            data.password_set
              ? "A password is stored. Leave blank to keep it."
              : "Not set."
          }
          className="sm:col-span-2"
        >
          <Input
            id="smtp-password"
            type="password"
            value={form.password}
            onChange={(event) => update("password", event.target.value)}
            autoComplete="new-password"
            placeholder={data.password_set ? "••••••••" : ""}
          />
        </Field>
        <Field label="Sender email" htmlFor="smtp-from-email">
          <Input
            id="smtp-from-email"
            type="email"
            value={form.from_email}
            onChange={(event) => update("from_email", event.target.value)}
            placeholder="noreply@example.com"
          />
        </Field>
        <Field
          label="Sender display name"
          htmlFor="smtp-from-name"
          className="sm:col-span-2"
        >
          <Input
            id="smtp-from-name"
            value={form.from_name}
            onChange={(event) => update("from_name", event.target.value)}
            placeholder="Open Book Map"
          />
        </Field>
      </div>

      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-[length:var(--text-sm)] text-[var(--text)]">
          <Switch
            label="Use STARTTLS"
            checked={form.use_starttls}
            onCheckedChange={(value) => update("use_starttls", value)}
          />
          STARTTLS
        </label>
        <label className="flex items-center gap-2 text-[length:var(--text-sm)] text-[var(--text)]">
          <Switch
            label="Use implicit TLS"
            checked={form.use_tls}
            onCheckedChange={(value) => update("use_tls", value)}
          />
          Implicit TLS (SMTPS)
        </label>
      </div>

      <div className="border-t border-[var(--border)] pt-4">
        <Field
          label="Send a test email"
          htmlFor="smtp-test-to"
          hint="Optional. Leave blank to only test the connection and login."
        >
          <Input
            id="smtp-test-to"
            type="email"
            value={toEmail}
            onChange={(event) => setToEmail(event.target.value)}
            placeholder="you@example.com"
          />
        </Field>
        {test.data && (
          <div className="mt-3">
            <Banner tone={test.data.ok ? "success" : "danger"}>
              {test.data.detail}
            </Banner>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-3">
        <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
          {data.updated_at
            ? `Last changed ${new Date(data.updated_at).toLocaleString()}${
                data.updated_by ? ` by ${data.updated_by}` : ""
              }`
            : "Never changed"}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => test.mutate()}
            loading={test.isPending}
          >
            Test configuration
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending}>
            Save SMTP settings
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SmtpCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-smtp"],
    queryFn: getAdminSmtp,
    staleTime: 10_000,
  });

  if (isLoading || !data) {
    return (
      <Card title="Email (SMTP)" description="Runtime mail server configuration">
        <Skeleton className="h-40 w-full" />
      </Card>
    );
  }

  return (
    <Card
      title="Email (SMTP)"
      description="Runtime mail server configuration"
      className="mb-4"
    >
      <SmtpForm key={`${data.source}:${data.updated_at ?? "never"}`} data={data} />
    </Card>
  );
}
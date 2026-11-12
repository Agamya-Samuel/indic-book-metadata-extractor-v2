"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { isApprovedStatus } from "@/lib/api";
import { AuthCard } from "@/components/auth/auth-card";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";
import { getErrorMessage } from "@/lib/error-handler";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const next = searchParams.get("next");
  const safeNext = next && next.startsWith("/") ? next : "/dashboard";

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const nextUser = await login(email, password);
      router.replace(
        isApprovedStatus(nextUser.account_status) ? safeNext : "/pending-approval",
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {error && (
        <p
          role="alert"
          className="rounded-[var(--radius)] border border-[var(--danger-500)]/30 bg-[var(--danger-50)] px-3 py-2 text-[var(--text-sm)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]"
        >
          {error}
        </p>
      )}
      <Field label="Email" htmlFor="email">
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </Field>
      <Field label="Password" htmlFor="password">
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? <Spinner className="size-4" /> : "Log in"}
      </Button>
      <div className="flex items-center justify-between text-[var(--text-xs)]">
        <Link
          href="/forgot-password"
          className="text-[var(--accent)] hover:underline"
        >
          Forgot password?
        </Link>
        <Link
          href="/register"
          className="text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          Create an account
        </Link>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthCard title="Log in" description="Access your books and dashboard.">
      <Suspense fallback={<Spinner className="size-5 text-[var(--accent)]" />}>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}

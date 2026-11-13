"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { resetPassword } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { AuthCard } from "@/components/auth/auth-card";
import { Banner } from "@/components/shared/empty-state";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";
import { getErrorMessage } from "@/lib/error-handler";

const MIN_PASSWORD_LENGTH = 10;

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshUser } = useAuth();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("This reset link is missing its token.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword(token, password);
      // A successful reset starts a session on the backend.
      await refreshUser();
      router.replace("/dashboard");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <AuthCard
        title="Reset link required"
        description="Open the link from your password reset email to choose a new password."
        footer={
          <Link href="/forgot-password" className="text-[var(--accent)] hover:underline">
            Request a new link
          </Link>
        }
      >
        <Link
          href="/login"
          className="text-[var(--text-sm)] text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          Back to log in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Choose a new password"
      description="Your other sessions will be signed out once the password changes."
      footer={
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Back to log in
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && <Banner tone="danger">{error}</Banner>}
        <Field
          label="New password"
          htmlFor="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Field label="Confirm password" htmlFor="confirm-new-password">
          <Input
            id="confirm-new-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Set new password
        </Button>
      </form>
    </AuthCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-10">
          <Spinner className="size-5 text-[var(--accent)]" />
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}

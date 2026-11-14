"use client";

import { useState } from "react";
import Link from "next/link";
import { requestPasswordReset } from "@/lib/api";
import { AuthCard } from "@/components/auth/auth-card";
import { Banner } from "@/components/shared/empty-state";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { getErrorMessage } from "@/lib/error-handler";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <AuthCard
        title="Check your email"
        description="If that address is registered, a password reset link has been sent."
        footer={
          <Link href="/login" className="text-[var(--accent-text)] hover:underline">
            Back to log in
          </Link>
        }
      >
        <div className="space-y-3 text-[length:var(--text-sm)] text-[var(--text-muted)]">
          <p>
            The link expires in one hour and can be used once. If it does not
            arrive, check your spam folder before requesting another.
          </p>
          <button
            type="button"
            onClick={() => setSent(false)}
            className="text-[var(--accent-text)] hover:underline"
          >
            Use a different email address
          </button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Forgot password"
      description="Enter your account email and we will send you a reset link."
      footer={
        <Link href="/login" className="text-[var(--accent-text)] hover:underline">
          Back to log in
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && <Banner tone="danger">{error}</Banner>}
        <Field label="Email" htmlFor="forgot-email">
          <Input
            id="forgot-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Send reset link
        </Button>
      </form>
    </AuthCard>
  );
}

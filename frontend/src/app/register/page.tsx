"use client";

import { useState } from "react";
import Link from "next/link";
import { register } from "@/lib/api";
import { AuthCard } from "@/components/auth/auth-card";
import { Alert } from "@/components/shared/alert";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { getErrorMessage } from "@/lib/error-handler";

const MIN_PASSWORD_LENGTH = 10;

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
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
      const result = await register({
        email,
        display_name: displayName,
        password,
      });
      setRegisteredEmail(result.email);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (registeredEmail) {
    return (
      <AuthCard
        title="Check your email"
        description={`We sent a verification link to ${registeredEmail}.`}
        footer={
          <Link href="/login" className="text-[var(--accent)] hover:underline">
            Back to log in
          </Link>
        }
      >
        <div className="space-y-3 text-[var(--text-sm)] text-[var(--text-muted)]">
          <p>
            Open the link in your inbox to verify your email address. The link
            expires in 24 hours.
          </p>
          <p>
            After you verify your email, an administrator reviews your account.
            You will get access once it is approved.
          </p>
          <p>
            Didn&apos;t receive it? Check your spam folder, or request another
            link from the verification page.
          </p>
          <Link
            href={`/verify-email?email=${encodeURIComponent(registeredEmail)}`}
            className="inline-block text-[var(--accent)] hover:underline"
          >
            Resend verification email
          </Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create an account"
      description="Upload books, run the OCR pipeline, and build your own library."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--accent)] hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <Field label="Display name" htmlFor="display-name">
          <Input
            id="display-name"
            autoComplete="name"
            required
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </Field>
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
        <Field
          label="Password"
          htmlFor="password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Field label="Confirm password" htmlFor="confirm-password">
          <Input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}

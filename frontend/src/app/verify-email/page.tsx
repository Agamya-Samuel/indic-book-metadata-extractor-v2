"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { resendVerification, verifyEmail } from "@/lib/api";
import { AuthCard } from "@/components/auth/auth-card";
import { Field, Input } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";
import { getErrorMessage } from "@/lib/error-handler";

type VerificationState = "idle" | "verifying" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const emailParam = searchParams.get("email") ?? "";

  const [state, setState] = useState<VerificationState>(
    token ? "verifying" : "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState(emailParam);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;
    verifyEmail(token)
      .then(() => setState("success"))
      .catch((err: unknown) => {
        setError(getErrorMessage(err));
        setState("error");
      });
  }, [token]);

  const handleResend = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setError(null);
      setResending(true);
      try {
        await resendVerification(email);
        setResent(true);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setResending(false);
      }
    },
    [email],
  );

  if (state === "verifying") {
    return (
      <AuthCard title="Verifying your email" description="One moment…">
        <div className="flex items-center justify-center py-6">
          <Spinner className="size-6 text-[var(--accent)]" />
        </div>
      </AuthCard>
    );
  }

  if (state === "success") {
    return (
      <AuthCard
        title="Email verified"
        description="Your account is active. You are now logged in."
        footer={
          <Link href="/library" className="text-[var(--accent)] hover:underline">
            Browse the library
          </Link>
        }
      >
        <div className="space-y-4">
          <p className="text-[var(--text-sm)] text-[var(--text-muted)]">
            Upload a book to start the OCR and metadata extraction pipeline, or
            open your dashboard to follow your jobs.
          </p>
          <LinkButton href="/dashboard" className="w-full">
            Go to dashboard
          </LinkButton>
        </div>
      </AuthCard>
    );
  }

  // "idle" and "error" both offer a resend form. The backend responds the same
  // way whether or not the address needs verification, so the UI never leaks
  // account existence.
  return (
    <AuthCard
      title={state === "error" ? "Link not valid" : "Verify your email"}
      description={
        state === "error"
          ? "This verification link is invalid or has expired. Request a new one below."
          : "Enter your email address and we will send you a new verification link."
      }
      footer={
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Back to log in
        </Link>
      }
    >
      <form onSubmit={handleResend} className="space-y-4" noValidate>
        {error && (
          <p
            role="alert"
            className="rounded-[var(--radius)] border border-[var(--danger-500)]/30 bg-[var(--danger-50)] px-3 py-2 text-[var(--text-sm)] text-[var(--danger-700)] dark:bg-[var(--danger-900)]/20 dark:text-[var(--danger-100)]"
          >
            {error}
          </p>
        )}
        {resent && (
          <p
            role="status"
            className="rounded-[var(--radius)] border border-[var(--success-500)]/30 bg-[var(--success-50)] px-3 py-2 text-[var(--text-sm)] text-[var(--success-700)] dark:bg-[var(--success-900)]/20 dark:text-[var(--success-100)]"
          >
            If that address needs verification, a new link is on its way. The
            link expires in 24 hours.
          </p>
        )}
        <Field label="Email" htmlFor="verify-email">
          <Input
            id="verify-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        <Button type="submit" className="w-full" loading={resending}>
          Resend verification email
        </Button>
      </form>
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-10">
          <Spinner className="size-5 text-[var(--accent)]" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}

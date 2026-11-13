"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  isApprovedStatus,
  resendVerification,
  verifyEmail,
  type AccountStatus,
} from "@/lib/api";
import { AuthCard } from "@/components/auth/auth-card";
import { Alert } from "@/components/shared/alert";
import { useAuth } from "@/components/auth/auth-provider";
import { Field, Input } from "@/components/shared/input";
import { Button, LinkButton } from "@/components/shared/button";
import { Spinner } from "@/components/shared/spinner";
import { getErrorMessage } from "@/lib/error-handler";

type VerificationState = "idle" | "verifying" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const emailParam = searchParams.get("email") ?? "";

  const { refreshUser } = useAuth();
  const [state, setState] = useState<VerificationState>(
    token ? "verifying" : "idle",
  );
  const [verifiedStatus, setVerifiedStatus] = useState<AccountStatus | null>(
    null,
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
      .then(async (verified) => {
        setVerifiedStatus(verified.account_status);
        // Hydrate the auth context so the holding screen (or dashboard) is
        // reachable without a second login.
        await refreshUser();
        setState("success");
      })
      .catch((err: unknown) => {
        setError(getErrorMessage(err));
        setState("error");
      });
  }, [token, refreshUser]);

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
    if (!isApprovedStatus(verifiedStatus)) {
      return (
        <AuthCard
          title="Email verified — awaiting approval"
          description="Your email is confirmed. An administrator will review your account."
          footer={
            <Link
              href="/login"
              className="text-[var(--accent)] hover:underline"
            >
              Back to log in
            </Link>
          }
        >
          <div className="space-y-4">
            <p className="text-[var(--text-sm)] text-[var(--text-muted)]">
              Your account is not active yet. Once an administrator approves it,
              you can upload and process books.
            </p>
            <LinkButton href="/pending-approval" className="w-full">
              Check approval status
            </LinkButton>
          </div>
        </AuthCard>
      );
    }
    return (
      <AuthCard
        title="Email verified"
        description="Your account is active. You are now logged in."
        footer={
          <Link
            href="/dashboard"
            className="text-[var(--accent)] hover:underline"
          >
            Go to your dashboard
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
        {error && <Alert>{error}</Alert>}
        {resent && (
          <Alert tone="success">
            If that address needs verification, a new link is on its way. The
            link expires in 24 hours.
          </Alert>
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

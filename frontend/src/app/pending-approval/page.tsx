"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/shared/button";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function PendingApprovalPage() {
  useDocumentTitle("Awaiting approval");
  const router = useRouter();
  const { user, accountStatus, logout } = useAuth();

  const rejected = accountStatus === "rejected";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <AuthCard
      title={rejected ? "Registration not approved" : "Awaiting approval"}
      description={
        rejected
          ? "An administrator reviewed your account and did not approve it."
          : "Your account is pending review."
      }
    >
      <div className="space-y-4 text-[length:var(--text-sm)] text-[var(--text-muted)]">
        {rejected ? (
          <>
            <p>
              You cannot access the application. If you believe this is a
              mistake, contact an administrator to have your account reviewed
              again.
            </p>
            {user?.rejection_reason && (
              <p className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-[var(--text)]">
                <span className="font-medium">Reason: </span>
                {user.rejection_reason}
              </p>
            )}
          </>
        ) : (
          <>
            <p>
              Thanks for signing up. A new account needs to be approved by an
              administrator before you can upload and process books.
            </p>
            <p>
              Your email is already verified. You will be able to use the app as
              soon as an administrator approves your account.
            </p>
            <p>
              This project is in its pilot phase and runs on limited resources,
              so signups are moderated: an administrator approves each account
              to keep out spam. As we grow and scale, registration will open to
              all users.
            </p>
          </>
        )}
        <Button
          type="button"
          variant="outline"
          className="w-full"
          onClick={handleLogout}
        >
          Log out
        </Button>
      </div>
    </AuthCard>
  );
}

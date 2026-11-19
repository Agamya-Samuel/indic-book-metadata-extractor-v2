"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  changePassword,
  getNotificationPreferences,
  requestEmailChange,
  setNotificationPreferences,
  updateProfile,
  type AuthUser,
} from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { PageContainer, PageHeader, Card } from "@/components/shared/card";
import { Field, Input } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { Switch } from "@/components/shared/switch";
import { Banner } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/shared/skeleton";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/error-handler";

function SettingsContent({
  user,
  refreshUser,
  logout,
}: {
  user: AuthUser | null;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [name, setName] = useState(user?.display_name ?? "");

  const preferences = useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: getNotificationPreferences,
  });

  const saveProfile = useMutation({
    mutationFn: () => updateProfile({ display_name: name.trim() }),
    onSuccess: async () => {
      await refreshUser();
      toast.success("Profile updated");
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  const [emailCurrent, setEmailCurrent] = useState("");
  const [emailNew, setEmailNew] = useState("");

  const sendEmailChange = useMutation({
    mutationFn: () => requestEmailChange(emailCurrent, emailNew.trim()),
    onSuccess: () => {
      setEmailCurrent("");
      setEmailNew("");
      toast.success("Verification email sent to your new address");
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const submitPassword = useMutation({
    mutationFn: () => {
      if (newPassword !== confirmPassword) {
        return Promise.reject(new Error("New passwords do not match"));
      }
      return changePassword(currentPassword, newPassword);
    },
    onSuccess: async () => {
      toast.success("Password changed. Please sign in again.");
      await logout();
      router.push("/login");
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  const updatePreference = useMutation({
    mutationFn: setNotificationPreferences,
    onSuccess: (enabled) => {
      queryClient.setQueryData(["notifications", "preferences"], enabled);
      toast.success(enabled ? "Email alerts enabled" : "Email alerts disabled");
    },
    onError: (error: unknown) => toast.error(getErrorMessage(error)),
  });

  return (
    <div className="space-y-4">
      <Card title="Profile" description="Your name and email address">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
                Email
              </p>
              <p className="text-[length:var(--text-sm)] text-[var(--text)]">
                {user?.email ?? "—"}
              </p>
            </div>
          </div>

          <Field label="Display name" htmlFor="settings-name">
            <Input
              id="settings-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
            />
          </Field>
          <div className="flex justify-end">
            <Button
              onClick={() => saveProfile.mutate()}
              loading={saveProfile.isPending}
              disabled={!name.trim() || name.trim() === user?.display_name}
            >
              Save name
            </Button>
          </div>

          <div className="border-t border-[var(--border)] pt-4">
            <p className="text-[length:var(--text-sm)] font-medium text-[var(--text)]">
              Change email
            </p>
            <p className="mt-1 text-[length:var(--text-xs)] text-[var(--text-muted)]">
              We will send a confirmation link to the new address. Your current
              email stays active until you confirm it.
            </p>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Current password" htmlFor="email-current">
                <Input
                  id="email-current"
                  type="password"
                  autoComplete="current-password"
                  value={emailCurrent}
                  onChange={(event) => setEmailCurrent(event.target.value)}
                />
              </Field>
              <Field label="New email" htmlFor="email-new">
                <Input
                  id="email-new"
                  type="email"
                  autoComplete="email"
                  value={emailNew}
                  onChange={(event) => setEmailNew(event.target.value)}
                />
              </Field>
            </div>
            <div className="mt-3 flex justify-end">
              <Button
                variant="outline"
                onClick={() => sendEmailChange.mutate()}
                loading={sendEmailChange.isPending}
                disabled={!emailCurrent || !emailNew.trim()}
              >
                Send verification
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card title="Security" description="Update your password">
        <div className="space-y-4">
          <Field label="Current password" htmlFor="current-password">
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </Field>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              label="New password"
              htmlFor="new-password"
              hint="At least 10 characters"
            >
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </Field>
            <Field label="Confirm new password" htmlFor="confirm-password">
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </Field>
          </div>
          {newPassword !== confirmPassword && confirmPassword.length > 0 && (
            <Banner tone="warning">New passwords do not match.</Banner>
          )}
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() => submitPassword.mutate()}
              loading={submitPassword.isPending}
              disabled={!currentPassword || !newPassword || !confirmPassword}
            >
              Change password
            </Button>
          </div>
          <p className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
            Changing your password signs you out of all sessions.
          </p>
        </div>
      </Card>

      <Card
        title="Email notifications"
        description="Receive job results and account decisions by email"
      >
        {preferences.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-xl">
              <p className="text-[length:var(--text-sm)] text-[var(--text)]">
                Send these notifications to your email address as well.
              </p>
              <p className="mt-1 text-[length:var(--text-xs)] text-[var(--text-muted)]">
                In-app notifications are always on and cannot be disabled.
              </p>
            </div>
            <Switch
              label="Email notifications"
              checked={preferences.data ?? false}
              disabled={preferences.isLoading || updatePreference.isPending}
              onCheckedChange={(enabled) => updatePreference.mutate(enabled)}
            />
          </div>
        )}
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  useDocumentTitle("Settings");
  const { user, refreshUser, logout } = useAuth();

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Account"
        title="Settings"
        description="Manage your profile, credentials and notification preferences."
      />
      {/* Remount when the display name changes so the field reflects the saved
          value without a setState-in-effect. */}
      <SettingsContent
        key={user?.display_name ?? "anon"}
        user={user}
        refreshUser={refreshUser}
        logout={logout}
      />
    </PageContainer>
  );
}
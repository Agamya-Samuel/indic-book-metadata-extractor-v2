"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getAdminUsers,
  createAdminUser,
  updateAdminUser,
  resetAdminUserPassword,
  deleteAdminUser,
  approveAdminUser,
  rejectAdminUser,
  type AdminUser,
  type AccountStatus,
} from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { ActionMenu, MenuButton, MenuSeparator } from "@/components/shared/action-menu";
import ConfirmDialog from "@/components/admin/confirm-dialog";
import Pagination from "@/components/shared/pagination";
import { PageContainer, Card } from "@/components/shared/card";
import { Field, Input, Select, Textarea } from "@/components/shared/input";
import { Button } from "@/components/shared/button";
import { EmptyState, Banner } from "@/components/shared/empty-state";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Chip } from "@/components/shared/chip";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { Spinner } from "@/components/shared/spinner";
import { getErrorMessage } from "@/lib/error-handler";
import { cn } from "@/lib/utils";

const MIN_PASSWORD_LENGTH = 10;

type PendingAction =
  | { type: "role"; user: AdminUser; role: "user" | "admin" }
  | { type: "active"; user: AdminUser; isActive: boolean }
  | { type: "delete"; user: AdminUser }
  | { type: "reset-password"; user: AdminUser }
  | { type: "approve"; user: AdminUser }
  | { type: "reject"; user: AdminUser }
  | null;

function RoleBadge({ role }: { role: "user" | "admin" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ring-1 ring-inset",
        role === "admin"
          ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)] ring-[var(--accent)]/30"
          : "bg-[var(--neutral-100)] dark:bg-[var(--neutral-800)] text-[var(--text-muted)] ring-[var(--border)]",
      )}
    >
      {role}
    </span>
  );
}

const STATUS_LABEL: Record<AccountStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

function AccountStatusBadge({ status }: { status: AccountStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        status === "approved" &&
          "bg-[var(--success-50)] dark:bg-[var(--success-900)]/20 text-[var(--success-700)] dark:text-[var(--success-100)] ring-[var(--success-500)]/30",
        status === "pending" &&
          "bg-[var(--warning-50)] dark:bg-[var(--warning-900)]/20 text-[var(--warning-700)] dark:text-[var(--warning-100)] ring-[var(--warning-500)]/30",
        status === "rejected" &&
          "bg-[var(--danger-50)] dark:bg-[var(--danger-900)]/20 text-[var(--danger-700)] dark:text-[var(--danger-100)] ring-[var(--danger-500)]/30",
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function AdminUsersContent() {
  useDocumentTitle("Admin · Users");

  const qc = useQueryClient();
  const { user: currentUser } = useAuth();
  const searchParams = useSearchParams();

  const [search, setSearch] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [roleFilter, setRoleFilter] = React.useState("");
  const [activeFilter, setActiveFilter] = React.useState("");
  // Deep links (e.g. the admin notification for a new registration) carry the
  // approval filter in the query string; seed the control from it once.
  const [statusFilter, setStatusFilter] = React.useState(() => {
    const status = searchParams.get("status");
    return status === "pending" || status === "approved" || status === "rejected"
      ? status
      : "";
  });
  const [page, setPage] = React.useState(1);
  const [pendingAction, setPendingAction] = React.useState<PendingAction>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const params = {
    query: debouncedSearch || undefined,
    role: (roleFilter || undefined) as "user" | "admin" | undefined,
    is_active:
      activeFilter === ""
        ? undefined
        : activeFilter === "true",
    account_status: (statusFilter || undefined) as AccountStatus | undefined,
    page,
    page_size: 50,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", params],
    queryFn: () => getAdminUsers(params),
    staleTime: 15 * 1000,
  });

  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 0;
  const total = data?.total ?? 0;

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-users"] });
    qc.invalidateQueries({ queryKey: ["admin-stats"] });
    qc.invalidateQueries({ queryKey: ["admin-pending-count"] });
  };

  const updateOne = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { display_name?: string; role?: "user" | "admin"; is_active?: boolean };
    }) => updateAdminUser(id, payload),
    onSuccess: (_data, variables) => {
      if (variables.payload.role) {
        toast.success(`Role changed to ${variables.payload.role}`);
      } else if (typeof variables.payload.is_active === "boolean") {
        toast.success(
          variables.payload.is_active ? "User activated" : "User deactivated",
        );
      }
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const deleteOne = useMutation({
    mutationFn: (id: string) => deleteAdminUser(id),
    onSuccess: () => {
      toast.success("User deleted");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const resetPassword = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      resetAdminUserPassword(id, password),
    onSuccess: () => {
      toast.success("Password reset — the user's other sessions were signed out");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const createOne = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      toast.success("User created");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const approveOne = useMutation({
    mutationFn: (id: string) => approveAdminUser(id),
    onSuccess: () => {
      toast.success("Account approved");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const rejectOne = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectAdminUser(id, reason || undefined),
    onSuccess: () => {
      toast.success("Account rejected");
      invalidate();
    },
    onError: (err: unknown) => toast.error(getErrorMessage(err)),
  });

  const handleConfirm = async () => {
    if (!pendingAction) return;
    switch (pendingAction.type) {
      case "role":
        await updateOne.mutateAsync({
          id: pendingAction.user.id,
          payload: { role: pendingAction.role },
        });
        break;
      case "active":
        await updateOne.mutateAsync({
          id: pendingAction.user.id,
          payload: { is_active: pendingAction.isActive },
        });
        break;
      case "delete":
        await deleteOne.mutateAsync(pendingAction.user.id);
        break;
      case "approve":
        await approveOne.mutateAsync(pendingAction.user.id);
        break;
      case "reject":
        // The reject dialog resolves its own mutation before closing.
        break;
      case "reset-password":
        // The dialog resolves the mutation itself before closing.
        break;
    }
    setPendingAction(null);
  };

  const isSelf = (user: AdminUser) => user.id === currentUser?.id;

  const columns: DataTableColumn<AdminUser>[] = [
    {
      key: "user",
      header: "User",
      cell: (user) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-[var(--text)]">
            {user.display_name}
            {isSelf(user) && (
              <span className="ml-2 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                (you)
              </span>
            )}
          </p>
          <p
            className="truncate text-[var(--text-xs)] text-[var(--text-muted)]"
            title={user.email}
          >
            {user.email}
          </p>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      cell: (user) => <RoleBadge role={user.role} />,
    },
    {
      key: "approval",
      header: "Approval",
      cell: (user) => <AccountStatusBadge status={user.account_status} />,
    },
    {
      key: "status",
      header: "Status",
      cell: (user) => (
        <Chip dot tone={user.is_active ? "success" : "danger"}>
          {user.is_active ? "Active" : "Deactivated"}
        </Chip>
      ),
    },
    {
      key: "verified",
      header: "Verified",
      hideBelow: "md",
      cell: (user) => (
        <span className="text-[var(--text-sm)] text-[var(--text-muted)]">
          {user.email_verified_at ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "lastLogin",
      header: "Last login",
      hideBelow: "lg",
      cell: (user) => (
        <span className="whitespace-nowrap text-[var(--text-xs)] tabular-nums text-[var(--text-muted)]">
          {user.last_login_at
            ? new Date(user.last_login_at).toLocaleString()
            : "—"}
        </span>
      ),
    },
    {
      key: "created",
      header: "Created",
      hideBelow: "lg",
      cell: (user) => (
        <span className="whitespace-nowrap text-[var(--text-xs)] tabular-nums text-[var(--text-muted)]">
          {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      headerClassName: "text-right",
      className: "text-right",
      cell: (user) => (
        <div className="flex justify-end">
          <ActionMenu
            ariaLabel={`Actions for ${user.display_name}`}
            label="Actions"
          >
            {user.account_status !== "approved" && (
              <MenuButton
                disabled={isSelf(user)}
                onClick={() => setPendingAction({ type: "approve", user })}
              >
                Approve account
              </MenuButton>
            )}
            {user.account_status !== "rejected" && (
              <MenuButton
                disabled={isSelf(user)}
                onClick={() => setPendingAction({ type: "reject", user })}
              >
                Reject account...
              </MenuButton>
            )}
            <MenuSeparator />
            {user.role === "admin" ? (
              <MenuButton
                disabled={isSelf(user)}
                onClick={() =>
                  setPendingAction({ type: "role", user, role: "user" })
                }
              >
                Change role to user
              </MenuButton>
            ) : (
              <MenuButton
                onClick={() =>
                  setPendingAction({ type: "role", user, role: "admin" })
                }
              >
                Change role to admin
              </MenuButton>
            )}
            {user.is_active ? (
              <MenuButton
                disabled={isSelf(user)}
                onClick={() =>
                  setPendingAction({ type: "active", user, isActive: false })
                }
              >
                Deactivate
              </MenuButton>
            ) : (
              <MenuButton
                onClick={() =>
                  setPendingAction({ type: "active", user, isActive: true })
                }
              >
                Activate
              </MenuButton>
            )}
            <MenuButton
              onClick={() => setPendingAction({ type: "reset-password", user })}
            >
              Reset password...
            </MenuButton>
            <MenuSeparator />
            <MenuButton
              danger
              disabled={isSelf(user)}
              onClick={() => setPendingAction({ type: "delete", user })}
            >
              Delete...
            </MenuButton>
          </ActionMenu>
        </div>
      ),
    },
  ];

  return (
    <PageContainer>
      <Card
        className="mb-4"
        title="Users"
        description={`${total} user${total !== 1 ? "s" : ""} registered`}
        headerAction={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            Add user
          </Button>
        }
      >
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[220px]">
            <Field label="Search" htmlFor="admin-user-search">
              <Input
                id="admin-user-search"
                type="text"
                placeholder="Name or email…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
              />
            </Field>
          </div>
          <div className="w-40">
            <Field label="Role" htmlFor="admin-user-role">
              <Select
                id="admin-user-role"
                value={roleFilter}
                onChange={(e) => {
                  setRoleFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All</option>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </Select>
            </Field>
          </div>
          <div className="w-40">
            <Field label="Status" htmlFor="admin-user-active">
              <Select
                id="admin-user-active"
                value={activeFilter}
                onChange={(e) => {
                  setActiveFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All</option>
                <option value="true">Active</option>
                <option value="false">Deactivated</option>
              </Select>
            </Field>
          </div>
          <div className="w-40">
            <Field label="Approval" htmlFor="admin-user-approval">
              <Select
                id="admin-user-approval"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </Select>
            </Field>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-sunken)] animate-pulse"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No users match your filters"
          description="Try adjusting the search or clearing filters."
        />
      ) : (
        <>

          <DataTable
            caption="Users"
            columns={columns}
            rows={items}
            rowKey={(user) => user.id}
            rowClassName={(user) => (!user.is_active ? "opacity-60" : undefined)}
          />

          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={async (payload) => {
          await createOne.mutateAsync(payload);
          setCreateOpen(false);
        }}
        loading={createOne.isPending}
      />

      {/* Role change */}
      <ConfirmDialog
        open={pendingAction?.type === "role"}
        onClose={() => setPendingAction(null)}
        onConfirm={handleConfirm}
        title={
          pendingAction?.type === "role" && pendingAction.role === "admin"
            ? "Grant admin access?"
            : "Revoke admin access?"
        }
        description={
          pendingAction?.type === "role" ? (
            <span>
              {pendingAction.role === "admin"
                ? `${pendingAction.user.display_name} will be able to manage all books, jobs, and users.`
                : `${pendingAction.user.display_name} will lose access to the admin area and global operations.`}
            </span>
          ) : null
        }
        confirmLabel={
          pendingAction?.type === "role" && pendingAction.role === "admin"
            ? "Make admin"
            : "Make user"
        }
        variant="warning"
        loading={updateOne.isPending}
      />

      {/* Activate / deactivate */}
      <ConfirmDialog
        open={pendingAction?.type === "active"}
        onClose={() => setPendingAction(null)}
        onConfirm={handleConfirm}
        title={
          pendingAction?.type === "active" && pendingAction.isActive
            ? "Activate this user?"
            : "Deactivate this user?"
        }
        description={
          pendingAction?.type === "active" ? (
            <span>
              {pendingAction.isActive
                ? `${pendingAction.user.display_name} will be able to log in again.`
                : `${pendingAction.user.display_name} will be signed out and unable to log in. Their books are kept.`}
            </span>
          ) : null
        }
        confirmLabel={
          pendingAction?.type === "active" && pendingAction.isActive
            ? "Activate"
            : "Deactivate"
        }
        variant="warning"
        loading={updateOne.isPending}
      />

      {/* Approve account */}
      <ConfirmDialog
        open={pendingAction?.type === "approve"}
        onClose={() => setPendingAction(null)}
        onConfirm={handleConfirm}
        title="Approve this account?"
        description={
          pendingAction?.type === "approve" ? (
            <span>
              <strong className="font-semibold text-[var(--text)]">
                {pendingAction.user.display_name}
              </strong>{" "}
              will be able to log in and use the application.
            </span>
          ) : null
        }
        confirmLabel="Approve"
        variant="warning"
        loading={approveOne.isPending}
      />

      {/* Reject account */}
      {pendingAction?.type === "reject" && (
        <RejectAccountDialog
          user={pendingAction.user}
          onClose={() => setPendingAction(null)}
          onSubmit={async (reason) => {
            await rejectOne.mutateAsync({ id: pendingAction.user.id, reason });
            setPendingAction(null);
          }}
          loading={rejectOne.isPending}
        />
      )}

      {/* Delete */}
      <ConfirmDialog
        open={pendingAction?.type === "delete"}
        onClose={() => setPendingAction(null)}
        onConfirm={handleConfirm}
        title="Delete this user?"
        description={
          pendingAction?.type === "delete" ? (
            <span>
              This permanently removes{" "}
              <strong className="font-semibold text-[var(--text)]">
                {pendingAction.user.display_name}
              </strong>{" "}
              and their sessions. Users who still own books cannot be deleted —
              delete or reassign their books first.
            </span>
          ) : null
        }
        confirmLabel="Delete user"
        requireTyped="delete"
        loading={deleteOne.isPending}
      />

      {/* Password reset */}
      {pendingAction?.type === "reset-password" && (
        <ResetPasswordDialog
          user={pendingAction.user}
          onClose={() => setPendingAction(null)}
          onSubmit={async (password) => {
            await resetPassword.mutateAsync({
              id: pendingAction.user.id,
              password,
            });
            setPendingAction(null);
          }}
          loading={resetPassword.isPending}
        />
      )}
    </PageContainer>
  );
}

// ---------------------------------------------------------------------------
// Create user dialog
// ---------------------------------------------------------------------------

function CreateUserDialog({
  open,
  onClose,
  onSubmit,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    email: string;
    display_name: string;
    password: string;
    role: "user" | "admin";
  }) => Promise<void>;
  loading: boolean;
}) {
  const ref = React.useRef<HTMLDialogElement | null>(null);
  const [email, setEmail] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [role, setRole] = React.useState<"user" | "admin">("user");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  const reset = () => {
    setEmail("");
    setDisplayName("");
    setPassword("");
    setRole("user");
    setError(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    try {
      await onSubmit({ email, display_name: displayName, password, role });
      reset();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !loading) onClose();
      }}
      className="m-auto w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/40 dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]"
    >
      <div className="px-6 pt-5 pb-2">
        <h2 className="text-md font-semibold text-[var(--text)]">Add user</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Admin-created accounts are email-verified immediately and can log in
          right away.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="px-6 pb-5 space-y-4" noValidate>
        {error && <Banner tone="danger">{error}</Banner>}
        <Field label="Display name" htmlFor="new-user-name">
          <Input
            id="new-user-name"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </Field>
        <Field label="Email" htmlFor="new-user-email">
          <Input
            id="new-user-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field
          label="Password"
          htmlFor="new-user-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="new-user-password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Field label="Role" htmlFor="new-user-role">
          <Select
            id="new-user-role"
            value={role}
            onChange={(e) => setRole(e.target.value as "user" | "admin")}
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
          </Select>
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Create user
          </Button>
        </div>
      </form>
    </dialog>
  );
}

// ---------------------------------------------------------------------------
// Password reset dialog
// ---------------------------------------------------------------------------

function ResetPasswordDialog({
  user,
  onClose,
  onSubmit,
  loading,
}: {
  user: AdminUser;
  onClose: () => void;
  onSubmit: (password: string) => Promise<void>;
  loading: boolean;
}) {
  const ref = React.useRef<HTMLDialogElement | null>(null);
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (el && !el.open) el.showModal();
    return () => el?.close();
  }, []);

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
    try {
      await onSubmit(password);
      setPassword("");
      setConfirm("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !loading) onClose();
      }}
      className="m-auto w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/40 dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]"
    >
      <div className="px-6 pt-5 pb-2">
        <h2 className="text-md font-semibold text-[var(--text)]">
          Reset password
        </h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Set a new password for {user.display_name}. All of their sessions
          will be signed out.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="px-6 pb-5 space-y-4" noValidate>
        {error && <Banner tone="danger">{error}</Banner>}
        <Field
          label="New password"
          htmlFor="reset-user-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="reset-user-password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Field label="Confirm password" htmlFor="reset-user-confirm">
          <Input
            id="reset-user-confirm"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Set password
          </Button>
        </div>
      </form>
    </dialog>
  );
}

// ---------------------------------------------------------------------------
// Reject account dialog
// ---------------------------------------------------------------------------

function RejectAccountDialog({
  user,
  onClose,
  onSubmit,
  loading,
}: {
  user: AdminUser;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
  loading: boolean;
}) {
  const ref = React.useRef<HTMLDialogElement | null>(null);
  const [reason, setReason] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (el && !el.open) el.showModal();
    return () => el?.close();
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await onSubmit(reason.trim());
      setReason("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !loading) onClose();
      }}
      className="m-auto w-full max-w-md rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-0 shadow-[var(--shadow-lg)] backdrop:bg-black/40 dark:bg-[var(--neutral-900)] dark:text-[var(--neutral-50)] dark:border-[var(--neutral-800)]"
    >
      <div className="px-6 pt-5 pb-2">
        <h2 className="text-md font-semibold text-[var(--text)]">
          Reject this account?
        </h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          {user.display_name} will be signed out and cannot use the application.
          They can still log in to see that their registration was not approved.
          An administrator can approve them later.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="px-6 pb-5 space-y-4" noValidate>
        {error && <Banner tone="danger">{error}</Banner>}
        <Field
          label="Reason (optional)"
          htmlFor="reject-user-reason"
          hint="Shown to the user on the registration-not-approved screen."
        >
          <Textarea
            id="reject-user-reason"
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" variant="danger" loading={loading}>
            Reject account
          </Button>
        </div>
      </form>
    </dialog>
  );
}

export default function AdminUsersPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex min-h-[50vh] items-center justify-center">
          <Spinner className="size-8 text-[var(--accent)]" />
        </div>
      }
    >
      <AdminUsersContent />
    </React.Suspense>
  );
}

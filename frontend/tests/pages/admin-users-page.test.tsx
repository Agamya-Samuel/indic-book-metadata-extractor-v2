import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import AdminUsersPage from "@/app/admin/users/page";
import { useAuth } from "@/components/auth/auth-provider";
import type { AdminUser, AdminUsersResponse } from "@/lib/api";

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    getAdminUsers: vi.fn(),
    createAdminUser: vi.fn(),
    updateAdminUser: vi.fn(),
    resetAdminUserPassword: vi.fn(),
    deleteAdminUser: vi.fn(),
  };
});

import {
  getAdminUsers,
  createAdminUser,
  updateAdminUser,
} from "@/lib/api";
const mockGetAdminUsers = vi.mocked(getAdminUsers);
const mockCreateAdminUser = vi.mocked(createAdminUser);
const mockUpdateAdminUser = vi.mocked(updateAdminUser);
const mockUseAuth = vi.mocked(useAuth);

function userRow(overrides: Partial<AdminUser>): AdminUser {
  return {
    id: "user-1",
    email: "ada@example.com",
    display_name: "Ada Lovelace",
    role: "user",
    is_active: true,
    email_verified_at: "2024-01-01T00:00:00Z",
    last_login_at: null,
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const mockUsers: AdminUsersResponse = {
  items: [
    userRow({ id: "admin-1", email: "root@example.com", display_name: "Root Admin", role: "admin" }),
    userRow({ id: "user-1" }),
    userRow({ id: "user-2", email: "off@example.com", display_name: "Off User", is_active: false }),
  ],
  total: 3,
  page: 1,
  page_size: 50,
  total_pages: 1,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("AdminUsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAdminUsers.mockResolvedValue(mockUsers);
    mockUpdateAdminUser.mockImplementation((_id, payload) =>
      Promise.resolve(userRow({ ...payload })),
    );
    mockUseAuth.mockReturnValue({
      user: userRow({ id: "admin-1", email: "root@example.com", display_name: "Root Admin", role: "admin" }),
      loading: false,
      isAuthenticated: true,
      isAdmin: true,
      login: vi.fn() as unknown as () => Promise<never>,
      logout: vi.fn() as unknown as () => Promise<void>,
      refreshUser: vi.fn() as unknown as () => Promise<void>,
    });
  });

  it("renders the users table with all rows", async () => {
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeDefined();
    });
    expect(screen.getByText("Off User")).toBeDefined();
    expect(screen.getByText("Root Admin")).toBeDefined();
  });

  it("marks the current admin's own row", async () => {
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("(you)")).toBeDefined();
    });
  });

  it("renders role badges", async () => {
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText("user").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("admin").length).toBeGreaterThan(0);
  });

  it("shows deactivated status for inactive users", async () => {
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Deactivated")).toBeDefined();
    });
  });

  it("opens the actions menu and changes a role after confirmation", async () => {
    const user = userEvent.setup();
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeDefined();
    });

    await user.click(
      screen.getByRole("button", { name: "Actions for Ada Lovelace" }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: "Change role to admin" }),
    );

    // Confirmation dialog appears; confirm it.
    await user.click(await screen.findByRole("button", { name: "Make admin" }));

    await waitFor(() => {
      expect(mockUpdateAdminUser).toHaveBeenCalledWith("user-1", {
        role: "admin",
      });
    });
  });

  it("opens the create-user dialog", async () => {
    const user = userEvent.setup();
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: "Add user" }));

    expect(await screen.findByLabelText("Display name")).toBeDefined();
    expect(screen.getByLabelText("Email")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
  });

  it("creates a user from the dialog", async () => {
    mockCreateAdminUser.mockResolvedValue(userRow({ id: "user-9" }));
    const user = userEvent.setup();
    render(<AdminUsersPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: "Add user" }));
    await user.type(await screen.findByLabelText("Display name"), "Grace Hopper");
    await user.type(screen.getByLabelText("Email"), "grace@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-123");
    await user.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() => {
      // react-query passes a second (context) argument to the mutationFn;
      // assert only on the payload.
      expect(mockCreateAdminUser.mock.calls[0]?.[0]).toEqual({
        email: "grace@example.com",
        display_name: "Grace Hopper",
        password: "long-enough-123",
        role: "user",
      });
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResetPasswordPage from "@/app/reset-password/page";

// The global setup mock returns empty search params. This file overrides it
// so the token branch can be exercised.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams("token=abc123def456"),
  usePathname: () => "/reset-password",
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    isAuthenticated: false,
    isAdmin: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    resetPassword: vi.fn(),
  };
});

import { resetPassword } from "@/lib/api";
const mockResetPassword = vi.mocked(resetPassword);

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResetPassword.mockResolvedValue({
      id: "u1",
      email: "user@example.com",
      display_name: "User",
      role: "user",
      is_active: true,
      email_verified_at: null,
      last_login_at: null,
      created_at: null,
    });
  });

  it("renders password fields when a token is present", () => {
    render(<ResetPasswordPage />);
    expect(screen.getByLabelText("New password")).toBeDefined();
    expect(screen.getByLabelText("Confirm password")).toBeDefined();
  });

  it("rejects passwords below the minimum length", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordPage />);

    await user.type(screen.getByLabelText("New password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "short");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByRole("alert").textContent).toMatch(/at least 10/i);
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("rejects mismatched passwords", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordPage />);

    await user.type(screen.getByLabelText("New password"), "long-enough-123");
    await user.type(screen.getByLabelText("Confirm password"), "different-456");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByRole("alert").textContent).toMatch(/do not match/i);
    expect(mockResetPassword).not.toHaveBeenCalled();
  });

  it("submits the token and new password", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordPage />);

    await user.type(screen.getByLabelText("New password"), "long-enough-123");
    await user.type(screen.getByLabelText("Confirm password"), "long-enough-123");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith("abc123def456", "long-enough-123");
    });
  });
});

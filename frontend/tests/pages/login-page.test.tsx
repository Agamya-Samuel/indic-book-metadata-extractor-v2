import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/login/page";
import { useAuth } from "@/components/auth/auth-provider";

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    login: vi.fn(),
  };
});

import { login } from "@/lib/api";
const mockLogin = vi.mocked(login);
const mockUseAuth = vi.mocked(useAuth);

function mockAuth(loginImpl: ReturnType<typeof vi.fn>) {
  mockUseAuth.mockReturnValue({
    user: null,
    loading: false,
    isAuthenticated: false,
    isAdmin: false,
    login: loginImpl as unknown as () => Promise<never>,
    logout: vi.fn() as unknown as () => Promise<void>,
    refreshUser: vi.fn() as unknown as () => Promise<void>,
  });
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth(vi.fn());
  });

  it("renders email and password fields", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
  });

  it("renders log in submit button", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: "Log in" })).toBeDefined();
  });

  it("links to forgot password and register", () => {
    render(<LoginPage />);
    expect(screen.getByText("Forgot password?")).toBeDefined();
    expect(screen.getByText("Create an account")).toBeDefined();
  });

  it("submits credentials to the login API", async () => {
    const loginImpl = vi.fn().mockResolvedValue({ id: "u1" });
    mockAuth(loginImpl);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => {
      expect(loginImpl).toHaveBeenCalledWith("reader@example.com", "correct horse");
    });
  });

  it("shows the backend error message on failure", async () => {
    const loginImpl = vi.fn().mockRejectedValue(
      new Error("Invalid email or password"),
    );
    mockAuth(loginImpl);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Email"), "reader@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
    expect(screen.getByRole("alert").textContent).toContain(
      "Invalid email or password",
    );
  });
});

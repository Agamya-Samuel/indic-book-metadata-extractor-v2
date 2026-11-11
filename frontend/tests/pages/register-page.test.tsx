import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "@/app/register/page";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    register: vi.fn(),
  };
});

import { register } from "@/lib/api";
const mockRegister = vi.mocked(register);

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRegister.mockResolvedValue({
      message: "Account created",
      email: "new@example.com",
    });
  });

  it("renders all registration fields", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText("Display name")).toBeDefined();
    expect(screen.getByLabelText("Email")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
    expect(screen.getByLabelText("Confirm password")).toBeDefined();
  });

  it("rejects passwords below the minimum length", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText("Display name"), "New User");
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByRole("alert").textContent).toMatch(/at least 10/i);
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("rejects mismatched passwords", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText("Display name"), "New User");
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-123");
    await user.type(screen.getByLabelText("Confirm password"), "different-123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.getByRole("alert").textContent).toMatch(/do not match/i);
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("submits the registration and shows the check-email step", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText("Display name"), "New User");
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-123");
    await user.type(screen.getByLabelText("Confirm password"), "long-enough-123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        email: "new@example.com",
        display_name: "New User",
        password: "long-enough-123",
      });
    });
    expect(await screen.findByText("Check your email")).toBeDefined();
  });

  it("shows a verification hint with the registered email", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText("Display name"), "New User");
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough-123");
    await user.type(screen.getByLabelText("Confirm password"), "long-enough-123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(screen.getByText(/new@example\.com/)).toBeDefined();
    });
  });
});

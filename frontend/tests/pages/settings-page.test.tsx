import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";

const auth = vi.hoisted(() => ({
  refreshUser: vi.fn(),
  logout: vi.fn(),
  user: {
    id: "u-1",
    email: "user@example.com",
    display_name: "Regular User",
    role: "user" as const,
    is_active: true,
    account_status: "approved" as const,
    rejection_reason: null,
    email_verified_at: "2024-01-01T00:00:00Z",
    last_login_at: null,
    created_at: "2024-01-01T00:00:00Z",
  },
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    user: auth.user,
    refreshUser: auth.refreshUser,
    logout: auth.logout,
    isAuthenticated: true,
    isAdmin: false,
    accountStatus: "approved",
    isApproved: true,
    login: vi.fn(),
  }),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/settings",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    updateProfile: vi.fn(),
    requestEmailChange: vi.fn(),
    changePassword: vi.fn(),
    getNotificationPreferences: vi.fn(),
    setNotificationPreferences: vi.fn(),
  };
});

import SettingsPage from "@/app/settings/page";
import {
  updateProfile,
  requestEmailChange,
  changePassword,
  getNotificationPreferences,
  setNotificationPreferences,
} from "@/lib/api";

const mockUpdateProfile = vi.mocked(updateProfile);
const mockRequestEmailChange = vi.mocked(requestEmailChange);
const mockChangePassword = vi.mocked(changePassword);
const mockGetPrefs = vi.mocked(getNotificationPreferences);
const mockSetPrefs = vi.mocked(setNotificationPreferences);

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

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPrefs.mockResolvedValue(false);
    mockSetPrefs.mockResolvedValue(true);
    mockUpdateProfile.mockResolvedValue(auth.user);
    mockRequestEmailChange.mockResolvedValue(undefined);
    mockChangePassword.mockResolvedValue(undefined);
    auth.refreshUser.mockResolvedValue(undefined);
    auth.logout.mockResolvedValue(undefined);
  });

  it("renders the current name and email", async () => {
    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(await screen.findByText("user@example.com")).toBeDefined();
    expect(
      (screen.getByLabelText("Display name") as HTMLInputElement).value,
    ).toBe("Regular User");
  });

  it("saves a new display name", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />, { wrapper: createWrapper() });

    const input = await screen.findByLabelText("Display name");
    await user.clear(input);
    await user.type(input, "Renamed User");
    await user.click(screen.getByRole("button", { name: "Save name" }));

    await waitFor(() =>
      expect(mockUpdateProfile).toHaveBeenCalledWith({
        display_name: "Renamed User",
      }),
    );
    await waitFor(() => expect(auth.refreshUser).toHaveBeenCalled());
  });

  it("toggles the email notification preference", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />, { wrapper: createWrapper() });

    const toggle = await screen.findByRole("switch", {
      name: "Email notifications",
    });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    await user.click(toggle);
    await waitFor(() => expect(mockSetPrefs).toHaveBeenCalled());
    expect(mockSetPrefs.mock.calls[0][0]).toBe(true);
  });

  it("changes the password and signs the user out", async () => {
    const user = userEvent.setup();
    const { container } = render(<SettingsPage />, { wrapper: createWrapper() });

    await user.type(
      container.querySelector("#current-password") as HTMLInputElement,
      "old password",
    );
    await user.type(
      container.querySelector("#new-password") as HTMLInputElement,
      "a brand new passphrase",
    );
    await user.type(
      container.querySelector("#confirm-password") as HTMLInputElement,
      "a brand new passphrase",
    );
    await user.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(mockChangePassword).toHaveBeenCalledWith(
        "old password",
        "a brand new passphrase",
      ),
    );
    await waitFor(() => expect(auth.logout).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });

  it("requests an email change", async () => {
    const user = userEvent.setup();
    const { container } = render(<SettingsPage />, { wrapper: createWrapper() });

    await user.type(
      container.querySelector("#email-current") as HTMLInputElement,
      "old password",
    );
    await user.type(
      container.querySelector("#email-new") as HTMLInputElement,
      "new@example.com",
    );
    await user.click(screen.getByRole("button", { name: "Send verification" }));

    await waitFor(() =>
      expect(mockRequestEmailChange).toHaveBeenCalledWith(
        "old password",
        "new@example.com",
      ),
    );
  });
});
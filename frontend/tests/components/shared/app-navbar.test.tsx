import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import AppNavbar from "@/components/shared/app-navbar";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ replace, push: vi.fn() }),
}));

const logout = vi.fn();
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    user: { id: "u1", display_name: "Ada Lovelace", email: "ada@example.com" },
    loading: false,
    isAuthenticated: true,
    isAdmin: false,
    isApproved: true,
    logout,
  }),
}));

vi.mock("@/components/shared/theme-provider", () => ({
  useTheme: () => ({ theme: "light", toggle: vi.fn() }),
}));

// The bell has its own suite; keep this one about the account menu.
vi.mock("@/components/notifications/notification-bell", () => ({
  NotificationBell: () => null,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, getPendingUserCount: vi.fn().mockResolvedValue(0) };
});

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

function menu(): HTMLDetailsElement {
  return screen.getByLabelText("Account menu").closest("details")!;
}

describe("AppNavbar account menu", () => {
  beforeEach(() => vi.clearAllMocks());

  it("closes when the pointer goes down outside it", async () => {
    const user = userEvent.setup();
    render(<AppNavbar />, { wrapper: createWrapper() });

    await user.click(screen.getByLabelText("Account menu"));
    expect(menu().open).toBe(true);

    await user.pointer({ keys: "[MouseLeft>]", target: document.body });
    await waitFor(() => expect(menu().open).toBe(false));
  });

  it("closes on Escape and returns focus to the summary", async () => {
    const user = userEvent.setup();
    render(<AppNavbar />, { wrapper: createWrapper() });

    const summary = screen.getByLabelText("Account menu");
    await user.click(summary);
    expect(menu().open).toBe(true);

    await user.keyboard("{Escape}");

    await waitFor(() => expect(menu().open).toBe(false));
    expect(document.activeElement).toBe(summary);
  });

  it("closes when one of its own links is chosen", async () => {
    const user = userEvent.setup();
    render(<AppNavbar />, { wrapper: createWrapper() });

    await user.click(screen.getByLabelText("Account menu"));
    await user.click(screen.getByRole("link", { name: "Dashboard" }));

    await waitFor(() => expect(menu().open).toBe(false));
  });
});
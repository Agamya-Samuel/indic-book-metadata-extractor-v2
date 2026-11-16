import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import MaintenanceCard from "@/components/admin/maintenance-card";
import {
  getAdminMaintenance,
  updateAdminMaintenance,
  type MaintenanceStatus,
} from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getAdminMaintenance: vi.fn(),
    updateAdminMaintenance: vi.fn(),
  };
});

const mockGetAdminMaintenance = vi.mocked(getAdminMaintenance);
const mockUpdateAdminMaintenance = vi.mocked(updateAdminMaintenance);

function status(overrides: Partial<MaintenanceStatus> = {}): MaintenanceStatus {
  return {
    enabled: false,
    message: null,
    until: null,
    updated_at: null,
    updated_by: null,
    ...overrides,
  };
}

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

describe("MaintenanceCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAdminMaintenance.mockResolvedValue(status());
    mockUpdateAdminMaintenance.mockResolvedValue(
      status({ enabled: true, message: "Upgrading" }),
    );
  });

  it("renders the current disabled state", async () => {
    render(<MaintenanceCard />, { wrapper: createWrapper() });

    const toggle = await screen.findByRole("switch", {
      name: "Maintenance mode",
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Never changed")).toBeDefined();
  });

  it("saves the enabled state and message", async () => {
    const user = userEvent.setup();
    render(<MaintenanceCard />, { wrapper: createWrapper() });

    const toggle = await screen.findByRole("switch", {
      name: "Maintenance mode",
    });
    await user.click(toggle);
    await user.type(screen.getByLabelText("Message"), "Upgrading");
    await user.click(
      screen.getByRole("button", { name: "Save maintenance settings" }),
    );

    await waitFor(() => {
      expect(mockUpdateAdminMaintenance).toHaveBeenCalledWith({
        enabled: true,
        message: "Upgrading",
        until: null,
      });
    });
  });

  it("shows an enabled banner and the last editor", async () => {
    mockGetAdminMaintenance.mockResolvedValue(
      status({
        enabled: true,
        message: "Patching",
        updated_at: "2024-01-01T10:00:00Z",
        updated_by: "Admin User",
      }),
    );

    render(<MaintenanceCard />, { wrapper: createWrapper() });

    expect(
      await screen.findByText(/Regular users are blocked right now/i),
    ).toBeDefined();
    expect(screen.getByText(/by Admin User/)).toBeDefined();
  });
});

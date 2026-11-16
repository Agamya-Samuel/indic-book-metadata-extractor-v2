import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import MaintenanceGate from "@/components/auth/maintenance-gate";
import { getPublicStatus, type MaintenanceStatus } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";

let mockPathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, getPublicStatus: vi.fn() };
});

const mockGetPublicStatus = vi.mocked(getPublicStatus);
const mockUseAuth = vi.mocked(useAuth);

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

function renderGate() {
  return render(
    <MaintenanceGate>
      <div>App content</div>
    </MaintenanceGate>,
    { wrapper: createWrapper() },
  );
}

describe("MaintenanceGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname = "/dashboard";
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: false,
      isAdmin: false,
      accountStatus: null,
      isApproved: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
  });

  it("renders the app when maintenance is off", async () => {
    mockGetPublicStatus.mockResolvedValue({ maintenance: status() });
    renderGate();

    expect(await screen.findByText("App content")).toBeDefined();
  });

  it("blocks regular users when maintenance is on", async () => {
    mockGetPublicStatus.mockResolvedValue({
      maintenance: status({ enabled: true, message: "Upgrading the database" }),
    });
    renderGate();

    expect(
      await screen.findByText("The service is paused for maintenance"),
    ).toBeDefined();
    expect(screen.getByText("Upgrading the database")).toBeDefined();
    expect(screen.queryByText("App content")).toBeNull();
  });

  it("lets admins through", async () => {
    mockGetPublicStatus.mockResolvedValue({
      maintenance: status({ enabled: true }),
    });
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: true,
      isAdmin: true,
      accountStatus: "approved",
      isApproved: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);

    renderGate();

    expect(await screen.findByText("App content")).toBeDefined();
  });

  it("keeps the auth screens reachable", async () => {
    mockPathname = "/login";
    mockGetPublicStatus.mockResolvedValue({
      maintenance: status({ enabled: true }),
    });

    renderGate();

    expect(await screen.findByText("App content")).toBeDefined();
  });
});

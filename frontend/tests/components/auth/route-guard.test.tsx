import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";

const replace = vi.fn();
let pathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({
    replace,
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: vi.fn(),
}));

const mockUseAuth = vi.mocked(useAuth);

function authValue(overrides: Record<string, unknown>) {
  return {
    user: null,
    loading: false,
    isAuthenticated: false,
    isAdmin: false,
    accountStatus: null,
    isApproved: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useAuth>;
}

function renderGuard() {
  return render(
    <RouteGuard>
      <div>protected content</div>
    </RouteGuard>,
  );
}

describe("RouteGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathname = "/dashboard";
  });

  it("redirects anonymous users to login with a next param", () => {
    mockUseAuth.mockReturnValue(authValue({}));
    renderGuard();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fdashboard");
    expect(screen.queryByText("protected content")).toBeNull();
  });

  it("redirects unapproved accounts to the holding screen", () => {
    mockUseAuth.mockReturnValue(
      authValue({ user: { id: "u1" }, isAuthenticated: true, isApproved: false }),
    );
    renderGuard();
    expect(replace).toHaveBeenCalledWith("/pending-approval");
    expect(screen.queryByText("protected content")).toBeNull();
  });

  it("renders the holding screen for unapproved accounts", () => {
    pathname = "/pending-approval";
    mockUseAuth.mockReturnValue(
      authValue({ user: { id: "u1" }, isAuthenticated: true, isApproved: false }),
    );
    renderGuard();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("protected content")).toBeDefined();
  });

  it("hides the admin-only books page from approved non-admins", () => {
    pathname = "/admin/books";
    mockUseAuth.mockReturnValue(
      authValue({
        user: { id: "u1" },
        isAuthenticated: true,
        isApproved: true,
        isAdmin: false,
      }),
    );
    renderGuard();
    expect(replace).toHaveBeenCalledWith("/dashboard");
    expect(screen.queryByText("protected content")).toBeNull();
  });

  it("allows an approved admin into the admin books page", () => {
    pathname = "/admin/books";
    mockUseAuth.mockReturnValue(
      authValue({
        user: { id: "a1" },
        isAuthenticated: true,
        isApproved: true,
        isAdmin: true,
      }),
    );
    renderGuard();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("protected content")).toBeDefined();
  });

  it("lets an approved owner open their own book under /books/<id>", () => {
    pathname = "/books/3f2504e0-4f89-11d3-9a0c-0305e82c3301";
    mockUseAuth.mockReturnValue(
      authValue({
        user: { id: "u1" },
        isAuthenticated: true,
        isApproved: true,
        isAdmin: false,
      }),
    );
    renderGuard();
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("protected content")).toBeDefined();
  });
});

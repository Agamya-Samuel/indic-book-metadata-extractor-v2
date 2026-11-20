import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import AdminSystemPage from "@/app/admin/system/page";
import {
  getAdminSystemMetrics,
  getAdminMaintenance,
  updateAdminMaintenance,
  getAdminSmtp,
  updateAdminSmtp,
  testAdminSmtp,
  type SystemMetricsResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getAdminSystemMetrics: vi.fn(),
    getAdminMaintenance: vi.fn(),
    updateAdminMaintenance: vi.fn(),
    getAdminSmtp: vi.fn(),
    updateAdminSmtp: vi.fn(),
    testAdminSmtp: vi.fn(),
  };
});

const mockGetAdminSystemMetrics = vi.mocked(getAdminSystemMetrics);
const mockGetAdminMaintenance = vi.mocked(getAdminMaintenance);
const mockUpdateAdminMaintenance = vi.mocked(updateAdminMaintenance);
const mockGetAdminSmtp = vi.mocked(getAdminSmtp);
const mockUpdateAdminSmtp = vi.mocked(updateAdminSmtp);
const mockTestAdminSmtp = vi.mocked(testAdminSmtp);

const metrics: SystemMetricsResponse = {
  generated_at: "2024-01-01T10:00:00Z",
  overall_status: "ok",
  server: {
    available: true,
    cpu_percent: 40,
    cpu_count: 4,
    load_1: 1.2,
    load_5: 1.0,
    load_15: 0.8,
    memory_total_mb: 16000,
    memory_used_mb: 8000,
    memory_available_mb: 8000,
    memory_percent: 50,
    swap_total_mb: 0,
    swap_used_mb: 0,
    disk_total_gb: 100,
    disk_used_gb: 40,
    disk_free_gb: 60,
    disk_percent: 40,
    storage_total_gb: 100,
    storage_used_mb: 1200,
    uptime_seconds: 90_000,
  },
  services: [
    { name: "Backend API", status: "ok", detail: "Serving requests" },
    { name: "PostgreSQL", status: "ok", latency_ms: 1.2 },
    { name: "Redis", status: "ok", latency_ms: 0.5 },
    {
      name: "Celery workers",
      status: "ok",
      detail: "1 worker(s), 0 active task(s)",
      meta: { workers: ["celery@host"], active_tasks: 0, queues: ["ocr", "llm"] },
    },
    {
      name: "LLM (Ollama)",
      status: "degraded",
      detail: "No model loaded (cold start)",
      meta: { loaded: [] },
    },
    { name: "OCR (Tesseract)", status: "ok", detail: "tesseract 5.3" },
  ],
  queues: {
    queues: [
      { name: "default", depth: 0 },
      { name: "llm", depth: 1 },
      { name: "ocr", depth: 2 },
    ],
    by_status: { queued: 3, running: 1 },
    by_type: { ocr: 2, llm: 1 },
    completed_last_15m: 4,
  },
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

describe("AdminSystemPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAdminSystemMetrics.mockResolvedValue(metrics);
    mockGetAdminMaintenance.mockResolvedValue({
      enabled: false,
      message: null,
      until: null,
      updated_at: null,
      updated_by: null,
    });
    mockUpdateAdminMaintenance.mockResolvedValue({
      enabled: true,
      message: "Upgrading",
      until: null,
      updated_at: "2024-01-01T10:00:00Z",
      updated_by: "Admin User",
    });
    mockGetAdminSmtp.mockResolvedValue({
      enabled: true,
      host: "smtp.example.com",
      port: 587,
      username: "mailer",
      password_set: true,
      from_email: "noreply@example.com",
      from_name: "Open Book Map",
      use_tls: false,
      use_starttls: true,
      source: "db",
      updated_at: "2024-01-01T10:00:00Z",
      updated_by: "Admin User",
    });
    mockUpdateAdminSmtp.mockResolvedValue({
      enabled: true,
      host: "smtp.example.com",
      port: 587,
      username: "mailer",
      password_set: true,
      from_email: "noreply@example.com",
      from_name: "Open Book Map",
      use_tls: false,
      use_starttls: true,
      source: "db",
      updated_at: "2024-01-01T10:00:00Z",
      updated_by: "Admin User",
    });
    mockTestAdminSmtp.mockResolvedValue({
      ok: true,
      detail: "Connected and authenticated successfully",
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("explains how to configure external monitoring when no links are set", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETTERSTACK_URL", "");
    vi.stubEnv("NEXT_PUBLIC_NEW_RELIC_URL", "");
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    expect(
      await screen.findByText(/No external monitoring links configured/),
    ).toBeDefined();
    expect(screen.getByText(/rebuild the frontend/)).toBeDefined();
  });

  it("links to a configured external monitoring provider", async () => {
    vi.stubEnv("NEXT_PUBLIC_BETTERSTACK_URL", "");
    vi.stubEnv("NEXT_PUBLIC_NEW_RELIC_URL", "https://newrelic.example.com");
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    const link = await screen.findByRole("link", { name: /New Relic/ });
    expect(link.getAttribute("href")).toBe("https://newrelic.example.com");
    expect(
      screen.queryByText(/No external monitoring links configured/),
    ).toBeNull();
  });

  it("renders host resource cards", async () => {
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    expect(await screen.findByText("Server resources")).toBeDefined();
    expect(screen.getByText("CPU")).toBeDefined();
    expect(screen.getByText("Load average")).toBeDefined();
    expect(screen.getByText("Memory")).toBeDefined();
    expect(screen.getByText("Disk")).toBeDefined();
    expect(screen.getByText("Uptime")).toBeDefined();
    expect(screen.getAllByText("40%").length).toBeGreaterThan(0);
  });

  it("lists every application service and queue depth", async () => {
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    expect(await screen.findByText("Application services")).toBeDefined();
    for (const name of [
      "Backend API",
      "PostgreSQL",
      "Redis",
      "Celery workers",
      "LLM (Ollama)",
      "OCR (Tesseract)",
    ]) {
      expect(screen.getByText(name)).toBeDefined();
    }
    expect(screen.getByText("ocr queue")).toBeDefined();
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getByText(/completed in the last/)).toBeDefined();
  });

  it("shows a degraded banner when a service needs attention", async () => {
    mockGetAdminSystemMetrics.mockResolvedValue({
      ...metrics,
      overall_status: "degraded",
    });
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    expect(await screen.findByText(/System degraded/i)).toBeDefined();
  });

  it("shows an error state when the metrics request fails", async () => {
    mockGetAdminSystemMetrics.mockRejectedValue(new Error("backend offline"));
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Could not load system metrics")).toBeDefined();
    });
    expect(screen.getByText("backend offline")).toBeDefined();
  });

  it("renders the SMTP configuration card without exposing the password", async () => {
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    expect(await screen.findByText("Email (SMTP)")).toBeDefined();
    expect(await screen.findByLabelText("Host")).toBeDefined();
    expect((screen.getByLabelText("Host") as HTMLInputElement).value).toBe(
      "smtp.example.com",
    );
    // The password field is never prefilled with the stored secret.
    expect((screen.getByLabelText("Password") as HTMLInputElement).value).toBe("");
  });

  it("saves and tests SMTP settings", async () => {
    const user = userEvent.setup();
    render(<AdminSystemPage />, { wrapper: createWrapper() });

    await user.click(await screen.findByRole("button", { name: "Test configuration" }));
    await waitFor(() => expect(mockTestAdminSmtp).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: "Save SMTP settings" }));
    await waitFor(() => expect(mockUpdateAdminSmtp).toHaveBeenCalled());
  });
});

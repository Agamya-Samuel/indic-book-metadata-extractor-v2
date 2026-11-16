import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import AdminSystemPage from "@/app/admin/system/page";
import {
  getAdminSystemMetrics,
  getAdminMaintenance,
  updateAdminMaintenance,
  type SystemMetricsResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getAdminSystemMetrics: vi.fn(),
    getAdminMaintenance: vi.fn(),
    updateAdminMaintenance: vi.fn(),
  };
});

const mockGetAdminSystemMetrics = vi.mocked(getAdminSystemMetrics);
const mockGetAdminMaintenance = vi.mocked(getAdminMaintenance);
const mockUpdateAdminMaintenance = vi.mocked(updateAdminMaintenance);

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
});

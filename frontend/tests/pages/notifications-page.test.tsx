import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import NotificationsPage from "@/app/notifications/page";
import type { NotificationListResponse } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/notifications",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getNotifications: vi.fn(),
    getNotificationPreferences: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
    setNotificationPreferences: vi.fn(),
  };
});

import {
  getNotifications,
  getNotificationPreferences,
  markNotificationRead,
  markAllNotificationsRead,
  setNotificationPreferences,
} from "@/lib/api";

const mockList = vi.mocked(getNotifications);
const mockPrefs = vi.mocked(getNotificationPreferences);
const mockRead = vi.mocked(markNotificationRead);
const mockReadAll = vi.mocked(markAllNotificationsRead);
const mockSetPrefs = vi.mocked(setNotificationPreferences);

const response: NotificationListResponse = {
  items: [
    {
      id: "n-1",
      type: "job_completed",
      title: "OCR finished: My Book",
      body: "OCR finished for “My Book”.",
      link_url: "/books/abc/ocr-review",
      book_id: "abc",
      read_at: null,
      created_at: new Date().toISOString(),
    },
    {
      id: "n-2",
      type: "pending_registration",
      title: "New registration: Asha",
      body: "Asha (asha@example.com) registered.",
      link_url: "/admin/users?status=pending",
      book_id: null,
      read_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    },
  ],
  total: 2,
  unread_count: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
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

describe("NotificationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue(response);
    mockPrefs.mockResolvedValue(true);
    mockRead.mockResolvedValue({ ...response.items[0], read_at: "now" });
    mockReadAll.mockResolvedValue(1);
    mockSetPrefs.mockResolvedValue(false);
  });

  it("renders the list and unread count", async () => {
    render(<NotificationsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("OCR finished: My Book")).toBeDefined();
    });
    expect(screen.getByText("1 unread notification")).toBeDefined();
    expect(screen.getByText("Job finished")).toBeDefined();
    expect(screen.getByText("Registration")).toBeDefined();
  });

  it("marks a notification read and follows its link", async () => {
    const user = userEvent.setup();
    render(<NotificationsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("OCR finished: My Book")).toBeDefined();
    });

    await user.click(screen.getByText("OCR finished: My Book"));
    expect(mockRead).toHaveBeenCalledWith("n-1", expect.anything());
    expect(push).toHaveBeenCalledWith("/books/abc/ocr-review");
  });

  it("marks all as read", async () => {
    const user = userEvent.setup();
    render(<NotificationsPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(mockReadAll).toHaveBeenCalled();
  });

  it("toggles the email preference", async () => {
    const user = userEvent.setup();
    render(<NotificationsPage />, { wrapper: createWrapper() });
    const toggle = await screen.findByRole("switch", { name: "Email alerts" });
    expect(toggle.getAttribute("aria-checked")).toBe("true");

    await user.click(toggle);
    expect(mockSetPrefs).toHaveBeenCalledWith(false, expect.anything());
  });
});
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { NotificationBell } from "@/components/notifications/notification-bell";
import type { NotificationListResponse } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getUnreadNotificationCount: vi.fn(),
    getNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  };
});

import {
  getUnreadNotificationCount,
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from "@/lib/api";

const mockUnread = vi.mocked(getUnreadNotificationCount);
const mockList = vi.mocked(getNotifications);
const mockRead = vi.mocked(markNotificationRead);
const mockReadAll = vi.mocked(markAllNotificationsRead);

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
  ],
  total: 1,
  unread_count: 1,
  page: 1,
  page_size: 8,
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

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUnread.mockResolvedValue(3);
    mockList.mockResolvedValue(response);
    mockRead.mockResolvedValue({ ...response.items[0], read_at: "now" });
    mockReadAll.mockResolvedValue(3);
  });

  it("shows the unread count on the bell", async () => {
    render(<NotificationBell />, { wrapper: createWrapper() });
    const bell = await screen.findByRole("button", {
      name: "Notifications, 3 unread",
    });
    expect(bell.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens the dropdown with recent notifications", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />, { wrapper: createWrapper() });
    await user.click(
      await screen.findByRole("button", { name: "Notifications, 3 unread" }),
    );

    expect(await screen.findByRole("region", { name: "Notifications" })).toBeDefined();
    expect(await screen.findByText("OCR finished: My Book")).toBeDefined();
  });

  it("marks read and navigates when an item is chosen", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />, { wrapper: createWrapper() });
    await user.click(
      await screen.findByRole("button", { name: "Notifications, 3 unread" }),
    );
    await user.click(await screen.findByText("OCR finished: My Book"));

    expect(mockRead).toHaveBeenCalledWith("n-1", expect.anything());
    expect(push).toHaveBeenCalledWith("/books/abc/ocr-review");
  });

  it("marks all read from the dropdown", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />, { wrapper: createWrapper() });
    await user.click(
      await screen.findByRole("button", { name: "Notifications, 3 unread" }),
    );
    await user.click(await screen.findByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(mockReadAll).toHaveBeenCalled());
  });

  it("moves focus into the panel on open", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />, { wrapper: createWrapper() });
    await user.click(
      await screen.findByRole("button", { name: "Notifications, 3 unread" }),
    );

    const panel = await screen.findByRole("region", { name: "Notifications" });
    await waitFor(() => expect(document.activeElement).toBe(panel));
  });

  it("returns focus to the bell on Escape", async () => {
    const user = userEvent.setup();
    render(<NotificationBell />, { wrapper: createWrapper() });
    const bell = await screen.findByRole("button", {
      name: "Notifications, 3 unread",
    });
    await user.click(bell);
    await screen.findByRole("region", { name: "Notifications" });

    await user.keyboard("{Escape}");

    await waitFor(() => expect(document.activeElement).toBe(bell));
    expect(screen.queryByRole("region", { name: "Notifications" })).toBeNull();
  });
});
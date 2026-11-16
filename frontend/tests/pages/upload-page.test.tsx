import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import UploadPage from "@/app/upload/page";

vi.mock("@/lib/api", () => ({
  uploadBook: vi.fn(),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload form with heading", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/Upload a book/)).toBeDefined();
  });

  it("renders dropzone area", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/or drag and drop/)).toBeDefined();
  });

  it("starts with no language selected", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("");
    expect(screen.getByText("Select a language")).toBeDefined();
  });

  it("renders language selector with Hindi option", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const select = screen.getByRole("combobox");
    expect(select).toBeDefined();
    expect(screen.getByText("Hindi")).toBeDefined();
  });

  it("renders title input", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText(/Kaviraj Margamu/);
    expect(input).toBeDefined();
  });

  it("renders Upload and continue button", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/Upload and continue/)).toBeDefined();
  });

  it("disables upload until a language is chosen", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const btn = screen.getByText(/Upload and continue/).closest("button")!;
    expect(btn.disabled).toBe(true);

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "hin" } });

    expect(btn.disabled).toBe(false);
  });

  it("shows file size limit", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText(/PDF up to 200 MB/)).toBeDefined();
  });

  it("can change language to Hindi", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "hin" } });
    expect((select as HTMLSelectElement).value).toBe("hin");
  });
});

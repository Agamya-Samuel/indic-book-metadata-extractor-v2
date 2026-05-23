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
    expect(screen.getByText("Upload Book")).toBeDefined();
  });

  it("renders dropzone area", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Upload a file")).toBeDefined();
    expect(screen.getByText(/or drag and drop/)).toBeDefined();
  });

  it("renders language selector with default Telugu", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const select = screen.getByDisplayValue("Telugu");
    expect(select).toBeDefined();
  });

  it("renders language selector with Hindi option", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const select = screen.getByRole("combobox");
    expect(select).toBeDefined();
    expect(screen.getByText("Hindi")).toBeDefined();
  });

  it("renders title input", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const input = screen.getByPlaceholderText("Enter book title");
    expect(input).toBeDefined();
  });

  it("renders Upload button", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Upload")).toBeDefined();
  });

  it("disables upload button when no file selected", () => {
    render(<UploadPage />, { wrapper: createWrapper() });
    const btn = screen.getByText("Upload").closest("button")!;
    expect(btn.disabled).toBe(true);
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

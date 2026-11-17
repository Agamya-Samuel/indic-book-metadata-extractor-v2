import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ExportDialog } from "@/components/export/export-dialog";
import { exportMetadata } from "@/lib/api";
import { downloadBlob } from "@/lib/download";

vi.mock("@/lib/api", () => ({
  exportMetadata: vi.fn(),
}));

vi.mock("@/lib/download", () => ({
  downloadBlob: vi.fn(),
  filenameFromDisposition: vi.fn((_header: string | null, fallback: string) => fallback),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockExport = vi.mocked(exportMetadata);
const mockDownload = vi.mocked(downloadBlob);

function renderDialog(overrides: Partial<Parameters<typeof ExportDialog>[0]> = {}) {
  const onClose = vi.fn();
  render(
    <ExportDialog
      open
      onClose={onClose}
      scope={{ bookIds: ["b1"] }}
      bookCount={1}
      {...overrides}
    />,
  );
  return { onClose };
}

describe("ExportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockExport.mockResolvedValue({
      blob: new Blob(["data"]),
      filename: 'attachment; filename="indic-books_book-b1.csv"',
    });
  });

  it("offers all six formats", () => {
    renderDialog();
    const radios = Array.from(
      document.querySelectorAll<HTMLInputElement>('input[name="export-format"]'),
    );
    expect(radios.map((radio) => radio.value)).toEqual([
      "csv",
      "xlsx",
      "json",
      "jsonl",
      "wikibase",
      "openrefine",
    ]);
    expect(screen.getByText("Excel (XLSX)")).toBeDefined();
    expect(screen.getByText("OpenRefine CSV")).toBeDefined();
  });

  it("exports the chosen format with the details toggle", async () => {
    const { onClose } = renderDialog({
      bookCount: 2,
      scope: { bookIds: ["b1", "b2"] },
    });

    fireEvent.click(
      document.querySelector<HTMLInputElement>('input[value="jsonl"]')!,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Export 2 books" }));

    await waitFor(() => {
      expect(mockExport).toHaveBeenCalledWith({
        format: "jsonl",
        include_details: true,
        book_ids: ["b1", "b2"],
        language: undefined,
        status: undefined,
        owner_id: undefined,
      });
    });
    expect(mockDownload).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("hides the details toggle for Wikibase and sends it false", async () => {
    renderDialog();

    fireEvent.click(
      document.querySelector<HTMLInputElement>('input[value="wikibase"]')!,
    );
    expect(screen.queryByRole("checkbox")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Export 1 book" }));
    await waitFor(() => {
      expect(mockExport).toHaveBeenCalledWith(
        expect.objectContaining({ format: "wikibase", include_details: false }),
      );
    });
  });

  it("disables export when no book is eligible", () => {
    renderDialog({ bookCount: 0 });
    const button = screen.getByRole("button", { name: "Export 0 books" });
    expect(button).toHaveProperty("disabled", true);
    expect(
      screen.getByText("No selected book has reviewed metadata yet."),
    ).toBeDefined();
  });
});

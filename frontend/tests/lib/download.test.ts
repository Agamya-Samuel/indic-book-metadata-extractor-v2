import { describe, expect, it, vi } from "vitest";

import { downloadBlob, filenameFromDisposition } from "@/lib/download";

describe("filenameFromDisposition", () => {
  it("reads a quoted filename", () => {
    expect(
      filenameFromDisposition('attachment; filename="indic-books_2-books.csv"', "fallback.csv"),
    ).toBe("indic-books_2-books.csv");
  });

  it("reads an unquoted filename", () => {
    expect(filenameFromDisposition("attachment; filename=export.json", "fallback.json")).toBe(
      "export.json",
    );
  });

  it("prefers the RFC 5987 UTF-8 form", () => {
    expect(
      filenameFromDisposition(
        "attachment; filename=\"fallback.csv\"; filename*=UTF-8''indic%20books.csv",
        "fallback.csv",
      ),
    ).toBe("indic books.csv");
  });

  it("falls back when the header is absent", () => {
    expect(filenameFromDisposition(null, "fallback.csv")).toBe("fallback.csv");
  });
});

describe("downloadBlob", () => {
  it("clicks a temporary anchor and revokes the URL", () => {
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const element = originalCreateElement(tag);
      if (tag === "a") element.click = click;
      return element;
    });

    const blob = new Blob(["csv"], { type: "text/csv" });
    downloadBlob(blob, "export.csv");

    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });
});

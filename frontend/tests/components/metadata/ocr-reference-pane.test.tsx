import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ComponentProps } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import OcrReferencePane from "@/components/metadata/ocr-reference-pane";
import type { OcrCorpusPage } from "@/lib/ocr-corpus";

vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const pages: OcrCorpusPage[] = [
  {
    id: "page-1",
    pageNumber: 1,
    text: "The title page\nAndhra Mahabharata",
    confidence: 92,
    imageUrl: null,
  },
  {
    id: "page-2",
    pageNumber: 2,
    text: "Another title mention",
    confidence: 55,
    imageUrl: null,
  },
  {
    id: "page-3",
    pageNumber: 3,
    text: "",
    confidence: null,
    imageUrl: null,
  },
];

function renderPane(
  overrides: Partial<ComponentProps<typeof OcrReferencePane>> = {},
) {
  const onPageNumberChange = vi.fn();
  const utils = render(
    <OcrReferencePane
      bookId="book-1"
      pages={pages}
      pageNumber={1}
      onPageNumberChange={onPageNumberChange}
      {...overrides}
    />,
  );
  return { ...utils, onPageNumberChange };
}

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe("OcrReferencePane", () => {
  it("renders the selected page text and confidence", () => {
    renderPane();
    expect(screen.getByTestId("ocr-pane-text").textContent).toContain(
      "The title page",
    );
    expect(screen.getByText("92% confidence")).toBeDefined();
  });

  it("navigates pages", () => {
    const { onPageNumberChange } = renderPane({ pageNumber: 2 });

    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onPageNumberChange).toHaveBeenLastCalledWith(1);

    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageNumberChange).toHaveBeenLastCalledWith(3);
  });

  it("searches the corpus and highlights matches on the current page", async () => {
    const { container } = renderPane();

    fireEvent.change(screen.getByLabelText("Search OCR text"), {
      target: { value: "title" },
    });

    await waitFor(() => {
      expect(screen.getByText("2 matches on 2 pages")).toBeDefined();
    });

    expect(container.querySelectorAll("mark")).toHaveLength(1);
    expect(
      screen.getByRole("button", { name: /page 2/ }),
    ).toBeDefined();
  });

  it("copies the page text when nothing is selected", async () => {
    renderPane();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "The title page\nAndhra Mahabharata",
      );
    });
  });

  it("appends a captured selection to the focused field", () => {
    const onAppend = vi.fn();
    const onRequestCloseSheet = vi.fn();
    renderPane({
      focusedField: "title",
      focusedFieldLabel: "Title",
      canAppend: true,
      onAppend,
      onRequestCloseSheet,
    });

    const text = screen.getByTestId("ocr-pane-text");
    const range = document.createRange();
    range.selectNodeContents(text);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    fireEvent.mouseUp(text);

    fireEvent.click(screen.getByRole("button", { name: "Append to Title" }));

    expect(onAppend).toHaveBeenCalledWith(
      "The title page\nAndhra Mahabharata",
    );
    expect(onRequestCloseSheet).toHaveBeenCalled();
  });

  it("renders evidence context for the focused field", () => {
    renderPane({
      focusedField: "title",
      focusedFieldLabel: "Title",
      evidence: {
        confidence: 0.42,
        extraction_method: "llm",
        source_page_number: 4,
        source_text_snippet: "Title from the cover",
      },
    });

    expect(screen.getByText("42% confidence")).toBeDefined();
    expect(screen.getByText("llm")).toBeDefined();
    expect(screen.getByText("page 4")).toBeDefined();
    expect(screen.getByText(/Title from the cover/)).toBeDefined();
  });

  it("hints at pages where an unattributed value appears", () => {
    const { onPageNumberChange } = renderPane({
      focusedField: "title",
      focusedFieldLabel: "Title",
      focusedValue: "Andhra Mahabharata",
    });

    expect(
      screen.getByText(/No source page was recorded for this field/),
    ).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "page 1" }));
    expect(onPageNumberChange).toHaveBeenCalledWith(1);
  });

  it("shows an empty state when the book has no OCR text", () => {
    renderPane({
      pages: pages.map((page) => ({ ...page, text: "" })),
    });
    expect(screen.getByText("No OCR text yet")).toBeDefined();
  });

  it("shows an empty state when the book has no pages", () => {
    renderPane({ pages: [] });
    expect(screen.getByText("No pages in this book")).toBeDefined();
  });

  it("shows a skeleton while the corpus loads", () => {
    renderPane({ pages: undefined, isLoading: true });
    expect(screen.getByLabelText("Loading OCR text")).toBeDefined();
  });

  it("shows an error with retry", () => {
    const onRetry = vi.fn();
    renderPane({ pages: undefined, error: new Error("boom"), onRetry });

    expect(screen.getByText("Could not load OCR text")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("switches to the page image tab", () => {
    const { container } = renderPane();
    fireEvent.click(screen.getByRole("tab", { name: "Page image" }));
    const image = container.querySelector("img");
    expect(image).not.toBeNull();
    expect(image?.getAttribute("src")).toContain("/pages/page-1/image");
  });
});

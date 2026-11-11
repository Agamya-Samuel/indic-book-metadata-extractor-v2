import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OcrTextEditor from "@/components/ocr/text-editor";
import type { OcrWord } from "@/lib/api";

const mockWords: OcrWord[] = [
  {
    text: "Hello",
    confidence: 95,
    bbox: { x: 10, y: 10, w: 50, h: 20 },
    block_num: 1,
    line_num: 1,
    word_num: 1,
  },
  {
    text: "World",
    confidence: 88,
    bbox: { x: 70, y: 10, w: 50, h: 20 },
    block_num: 1,
    line_num: 1,
    word_num: 2,
  },
  {
    text: "LowConf",
    confidence: 30,
    bbox: { x: 10, y: 40, w: 60, h: 20 },
    block_num: 1,
    line_num: 2,
    word_num: 3,
  },
];

describe("OcrTextEditor", () => {
  const defaultProps = {
    words: mockWords,
    rawText: "Hello World LowConf",
    correctedText: null,
    selectedIndex: undefined,
    onWordClick: vi.fn(),
    onSave: vi.fn(),
    isSaving: false,
  };

  it("renders word count", () => {
    render(<OcrTextEditor {...defaultProps} />);
    expect(screen.getByText(/3\s*words/)).toBeDefined();
  });

  it("renders all words in structured mode", () => {
    render(<OcrTextEditor {...defaultProps} />);
    expect(screen.getByText("Hello")).toBeDefined();
    expect(screen.getByText("World")).toBeDefined();
    expect(screen.getByText("LowConf")).toBeDefined();
  });

  it("fires onWordClick when word is clicked", () => {
    const onWordClick = vi.fn();
    render(<OcrTextEditor {...defaultProps} onWordClick={onWordClick} />);

    fireEvent.click(screen.getByText("Hello"));
    expect(onWordClick).toHaveBeenCalledWith(0);
  });

  it("renders OCR text header", () => {
    render(<OcrTextEditor {...defaultProps} />);
    expect(screen.getByText(/OCR text/i)).toBeDefined();
  });

  it("shows the read-only boxes notice", () => {
    render(<OcrTextEditor {...defaultProps} />);
    expect(
      screen.getByText(/not updated by text edits/i),
    ).toBeDefined();
  });

  it("toggles to edit mode", () => {
    render(<OcrTextEditor {...defaultProps} />);

    fireEvent.click(screen.getByText(/^Edit text$/));

    expect(screen.getByText(/^Cancel$/)).toBeDefined();
  });

  it("shows textarea in edit mode", () => {
    render(<OcrTextEditor {...defaultProps} />);

    fireEvent.click(screen.getByText(/^Edit text$/));

    const textarea = document.querySelector("textarea");
    expect(textarea).toBeDefined();
    expect(textarea?.value).toBe("Hello World LowConf");
  });

  it("disables save when there are no edits", () => {
    render(<OcrTextEditor {...defaultProps} />);
    const save = screen.getByRole("button", {
      name: /save corrections/i,
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });

  it("calls onSave with edited text", () => {
    const onSave = vi.fn();
    render(<OcrTextEditor {...defaultProps} onSave={onSave} />);

    fireEvent.click(screen.getByText(/^Edit text$/));
    const textarea = document.querySelector("textarea")!;
    fireEvent.change(textarea, { target: { value: "Edited text" } });
    fireEvent.click(screen.getByText(/^Save corrections$/));

    expect(onSave).toHaveBeenCalledWith("Edited text");
  });

  it("allows clearing text to empty and saving it", () => {
    const onSave = vi.fn();
    render(<OcrTextEditor {...defaultProps} onSave={onSave} />);

    fireEvent.click(screen.getByText(/^Edit text$/));
    const textarea = document.querySelector("textarea")!;
    fireEvent.change(textarea, { target: { value: "" } });
    expect(textarea.value).toBe("");
    fireEvent.click(screen.getByText(/^Save corrections$/));

    expect(onSave).toHaveBeenCalledWith("");
  });

  it("notifies the parent when dirty state changes", () => {
    const onDirtyChange = vi.fn();
    render(
      <OcrTextEditor {...defaultProps} onDirtyChange={onDirtyChange} />,
    );

    fireEvent.click(screen.getByText(/^Edit text$/));
    const textarea = document.querySelector("textarea")!;
    fireEvent.change(textarea, { target: { value: "Changed" } });

    expect(onDirtyChange).toHaveBeenCalledWith(true);
  });

  it("shows Edited badge when correctedText differs from rawText", () => {
    render(<OcrTextEditor {...defaultProps} correctedText="Corrected text" />);
    expect(screen.getByText("Edited")).toBeDefined();
  });

  it("does not show Edited badge when no corrections", () => {
    render(<OcrTextEditor {...defaultProps} />);
    expect(screen.queryByText("Edited")).toBeNull();
  });

  it("shows Saving when isSaving", () => {
    render(<OcrTextEditor {...defaultProps} isSaving={true} />);
    expect(screen.getByText("Saving")).toBeDefined();
  });

  it("returns from edit mode on Cancel", () => {
    render(<OcrTextEditor {...defaultProps} />);

    fireEvent.click(screen.getByText(/^Edit text$/));
    expect(screen.getByText(/^Cancel$/)).toBeDefined();

    fireEvent.click(screen.getByText(/^Cancel$/));
    expect(screen.getByText(/^Edit text$/)).toBeDefined();
    expect(screen.getByText("Hello")).toBeDefined();
  });

  it("shows an empty-OCR hint when there is no text", () => {
    render(
      <OcrTextEditor
        {...defaultProps}
        words={[]}
        rawText={null}
        correctedText={null}
      />,
    );
    expect(screen.getByText(/No OCR text was detected/i)).toBeDefined();
  });
});
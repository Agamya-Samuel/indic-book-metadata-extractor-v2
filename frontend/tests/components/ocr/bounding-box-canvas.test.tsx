import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BoundingBoxCanvas, { scaleBox } from "@/components/ocr/bounding-box-canvas";
import type { OcrWord } from "@/lib/api";

describe("scaleBox", () => {
  it("scales box coordinates proportionally", () => {
    const result = scaleBox(
      { x: 100, y: 50, w: 200, h: 100 },
      1000,
      500,
      500,
      250
    );
    expect(result).toEqual({ x: 50, y: 25, w: 100, h: 50 });
  });

  it("returns same coords when canvas matches image size", () => {
    const box = { x: 10, y: 20, w: 30, h: 40 };
    const result = scaleBox(box, 800, 600, 800, 600);
    expect(result).toEqual(box);
  });

  it("handles zero image dimensions (division by zero)", () => {
    const result = scaleBox(
      { x: 100, y: 100, w: 100, h: 100 },
      0,
      0,
      800,
      600
    );
    expect(result.x).toBe(Infinity);
    expect(result.y).toBe(Infinity);
    expect(result.w).toBe(Infinity);
    expect(result.h).toBe(Infinity);
  });
});

describe("BoundingBoxCanvas", () => {
  const mockBoxes: OcrWord[] = [
    {
      text: "Hello",
      confidence: 90,
      bbox: { x: 10, y: 10, w: 50, h: 20 },
      block_num: 1,
      line_num: 1,
      word_num: 1,
    },
    {
      text: "World",
      confidence: 50,
      bbox: { x: 70, y: 10, w: 50, h: 20 },
      block_num: 1,
      line_num: 1,
      word_num: 2,
    },
  ];

  it("renders word count and zoom info", () => {
    render(
      <BoundingBoxCanvas imageUrl="http://test/image.png" boxes={mockBoxes} />
    );
    expect(screen.getByText(/2 words/)).toBeDefined();
    expect(screen.getByText(/Zoom: 100%/)).toBeDefined();
  });

  it("renders confidence legend", () => {
    render(
      <BoundingBoxCanvas imageUrl="http://test/image.png" boxes={mockBoxes} />
    );
    expect(screen.getByText("High")).toBeDefined();
    expect(screen.getByText("Medium")).toBeDefined();
    expect(screen.getByText("Low")).toBeDefined();
  });

  it("renders Reset View button", () => {
    render(
      <BoundingBoxCanvas imageUrl="http://test/image.png" boxes={mockBoxes} />
    );
    expect(screen.getByText("Reset View")).toBeDefined();
  });

  it("renders with empty boxes array", () => {
    render(
      <BoundingBoxCanvas imageUrl="http://test/image.png" boxes={[]} />
    );
    expect(screen.getByText(/0 words/)).toBeDefined();
  });
});

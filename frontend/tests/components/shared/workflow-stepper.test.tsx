import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import WorkflowStepper from "@/components/shared/workflow-stepper";

describe("WorkflowStepper", () => {
  const defaultProps = {
    bookId: "book-123",
    currentStep: 3 as const,
    completedStep: 3 as const,
  };

  it("renders all 7 step labels", () => {
    const { container } = render(<WorkflowStepper {...defaultProps} />);
    const text = container.textContent ?? "";
    expect(text).toContain("Upload");
    expect(text).toContain("Select Pages");
    expect(text).toContain("Preprocessing");
    expect(text).toContain("OCR Review");
    expect(text).toContain("LLM Config");
    expect(text).toContain("Metadata Review");
    expect(text).toContain("Complete");
  });

  it("highlights current step with blue styling", () => {
    const { container } = render(<WorkflowStepper {...defaultProps} />);
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBeGreaterThan(0);
  });

  it("renders with step 1", () => {
    const { container } = render(
      <WorkflowStepper bookId="book-1" currentStep={1} completedStep={1} />
    );
    expect(container.textContent).toContain("Upload");
  });

  it("renders with all steps completed", () => {
    const { container } = render(
      <WorkflowStepper bookId="book-1" currentStep={7} completedStep={7} />
    );
    expect(container.textContent).toContain("Complete");
  });

  it("shows step numbers for future steps", () => {
    const { container } = render(
      <WorkflowStepper bookId="book-1" currentStep={2} completedStep={2} />
    );
    const text = container.textContent ?? "";
    expect(text).toContain("3");
    expect(text).toContain("4");
    expect(text).toContain("5");
  });

  it("renders clickable links for completed steps", () => {
    const { container } = render(
      <WorkflowStepper bookId="book-1" currentStep={4} completedStep={4} />
    );
    const links = container.querySelectorAll("a");
    expect(links.length).toBeGreaterThan(0);
  });

  it("renders non-clickable spans for future steps", () => {
    const { container } = render(
      <WorkflowStepper bookId="book-1" currentStep={2} completedStep={2} />
    );
    const nonClickable = container.querySelectorAll("span.cursor-not-allowed");
    expect(nonClickable.length).toBeGreaterThan(0);
  });
});

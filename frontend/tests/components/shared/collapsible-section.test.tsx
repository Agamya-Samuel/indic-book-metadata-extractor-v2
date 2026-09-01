import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CollapsibleSection from "@/components/shared/collapsible-section";

describe("CollapsibleSection", () => {
  it("renders title", () => {
    render(
      <CollapsibleSection title="Test Section">Content here</CollapsibleSection>
    );
    expect(screen.getByText("Test Section")).toBeDefined();
  });

  it("shows children when defaultOpen is true", () => {
    render(
      <CollapsibleSection title="Test" defaultOpen={true}>
        <div>Visible content</div>
      </CollapsibleSection>
    );
    expect(screen.getByText("Visible content")).toBeDefined();
  });

  it("hides children when defaultOpen is false", () => {
    render(
      <CollapsibleSection title="Test" defaultOpen={false}>
        <div>Hidden content</div>
      </CollapsibleSection>
    );
    // The panel is rendered but collapsed via grid-rows + aria-hidden.
    const button = screen.getByRole("button", { name: /Test/ });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    const panel = button.getAttribute("aria-controls");
    expect(panel).toBeTruthy();
  });

  it("toggles visibility on click", () => {
    render(
      <CollapsibleSection title="Test" defaultOpen={true}>
        <div>Toggle content</div>
      </CollapsibleSection>
    );

    expect(screen.getByText("Toggle content")).toBeDefined();

    const button = screen.getByRole("button", { name: /Test/ });
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
  });

  it("shows count badge when count is provided", () => {
    render(
      <CollapsibleSection title="Test" count={5} defaultOpen={true}>
        <div>Content</div>
      </CollapsibleSection>
    );
    expect(screen.getByText(/5\s+fields/)).toBeDefined();
  });

  it("does not show count badge when count is not provided", () => {
    render(
      <CollapsibleSection title="Test" defaultOpen={true}>
        <div>Content</div>
      </CollapsibleSection>
    );
    expect(screen.queryByText(/fields/)).toBeNull();
  });
});

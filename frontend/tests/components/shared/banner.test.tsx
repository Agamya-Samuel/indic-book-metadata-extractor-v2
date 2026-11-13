import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Banner } from "@/components/shared/empty-state";

describe("Banner", () => {
  it("announces the danger tone as an alert", () => {
    render(<Banner tone="danger">Something broke</Banner>);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("Something broke");
    expect(alert.getAttribute("data-tone")).toBe("danger");
  });

  it("announces non-error tones as status", () => {
    render(<Banner tone="success">Saved</Banner>);
    const status = screen.getByRole("status");
    expect(status.getAttribute("data-tone")).toBe("success");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("stays silent for the neutral tone and merges a className", () => {
    render(<Banner className="mt-3">Heads up</Banner>);
    const banner = screen.getByText("Heads up");
    expect(banner.getAttribute("role")).toBeNull();
    expect(banner.getAttribute("data-tone")).toBe("neutral");
    expect(banner.className).toContain("mt-3");
  });
});
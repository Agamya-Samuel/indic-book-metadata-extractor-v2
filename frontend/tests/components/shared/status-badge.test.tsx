import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import StatusBadge from "@/components/shared/status-badge";

describe("StatusBadge", () => {
  it("renders queued status", () => {
    const { container } = render(<StatusBadge status="queued" />);
    expect(container.textContent).toContain("Queued");
    expect(container.querySelector("span")?.className).toContain("bg-[var(--neutral-100)]");
  });

  it("renders running status with ping indicator", () => {
    const { container } = render(<StatusBadge status="running" />);
    expect(container.textContent).toContain("Running");
    expect(container.querySelector("span")?.className).toContain("bg-[var(--info-50)]");
    expect(container.querySelector(".animate-ping")).toBeTruthy();
  });

  it("renders completed status", () => {
    const { container } = render(<StatusBadge status="completed" />);
    expect(container.textContent).toContain("Completed");
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[var(--success-50)]");
  });

  it("renders failed status", () => {
    const { container } = render(<StatusBadge status="failed" />);
    expect(container.textContent).toContain("Failed");
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[var(--danger-50)]");
  });

  it("renders cancelled status", () => {
    const { container } = render(<StatusBadge status="cancelled" />);
    expect(container.textContent).toContain("Cancelled");
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("bg-[var(--warning-50)]");
  });

  it("renders unknown status with fallback", () => {
    const { container } = render(<StatusBadge status="custom_status" />);
    expect(container.textContent).toContain("custom_status");
  });
});

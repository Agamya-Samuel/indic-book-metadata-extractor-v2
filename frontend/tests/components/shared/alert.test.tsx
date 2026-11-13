import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert } from "@/components/shared/alert";

describe("Alert", () => {
  it("defaults to an error alert", () => {
    render(<Alert>Something broke</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("Something broke");
    expect(alert.getAttribute("data-tone")).toBe("error");
  });

  it("announces non-error tones as status", () => {
    render(<Alert tone="success">Saved</Alert>);
    const status = screen.getByRole("status");
    expect(status.getAttribute("data-tone")).toBe("success");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("lets the caller override the role and merge a className", () => {
    render(
      <Alert tone="info" role="alert" className="mt-3">
        Heads up
      </Alert>,
    );
    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("mt-3");
    expect(alert.getAttribute("data-tone")).toBe("info");
  });
});
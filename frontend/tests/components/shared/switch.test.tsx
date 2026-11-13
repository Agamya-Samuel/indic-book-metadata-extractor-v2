import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Switch } from "@/components/shared/switch";
import { formatRelativeTime } from "@/lib/utils";

describe("Switch", () => {
  it("exposes a switch role with its checked state", () => {
    render(
      <Switch checked label="Email alerts" onCheckedChange={() => {}} />,
    );
    const toggle = screen.getByRole("switch", { name: "Email alerts" });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("reports the opposite value when clicked", async () => {
    const onChange = vi.fn();
    render(
      <Switch checked={false} label="Email alerts" onCheckedChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("does not fire while disabled", async () => {
    const onChange = vi.fn();
    render(
      <Switch
        checked
        disabled
        label="Email alerts"
        onCheckedChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole("switch"));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("formatRelativeTime", () => {
  it("formats recent timestamps", () => {
    const now = Date.now();
    expect(formatRelativeTime(new Date(now - 5_000).toISOString())).toBe(
      "just now",
    );
    expect(formatRelativeTime(new Date(now - 5 * 60_000).toISOString())).toBe(
      "5m ago",
    );
    expect(
      formatRelativeTime(new Date(now - 3 * 3_600_000).toISOString()),
    ).toBe("3h ago");
    expect(
      formatRelativeTime(new Date(now - 2 * 86_400_000).toISOString()),
    ).toBe("2d ago");
  });

  it("returns an empty string for a missing timestamp", () => {
    expect(formatRelativeTime(null)).toBe("");
  });
});